#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử phân quyền GraphQL theo vai trò JWT (#26), gọi THẬT qua APISIX /graphql bằng token
# Keycloak của 3 user mẫu (dieuphoi01, cuuho01, tinhnguyen01):
# (1) không token → 401 ở gateway; anonymous gọi thẳng Hasura không thấy bảng nào;
# (2) dieu-phoi đọc mọi tin, tạo/phân công, gán thành viên đội, không xóa tin, không sửa tồn kho trực tiếp;
# (3) cuu-ho chỉ thấy/cập nhật status tin của đội mình, không thấy đội khác, không đổi nội dung;
# (4) tinh-nguyen tạo tin, không đọc SĐT người báo, chỉ thấy tin mình tạo, không sửa/xóa, chặn tin trùng;
# (5) truy vấn vị trí PostGIS _st_d_within; xin vai trò ngoài allowed-roles bị chặn.
# Dữ liệu thử có mô tả bắt đầu "[smoke]", xóa (bằng admin secret, cổng 127.0.0.1) trước và sau khi chạy.
# Dùng: make up && make seed && bash scripts/smoke-hasura.sh
# shellcheck disable=SC2016 # biến GraphQL ($o, $id, $p…) cố ý nằm trong nháy đơn, không phải biến shell
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

ADDR="http://127.0.0.1:${OPENBAO_PORT:-8200}"
DIR="${OPENBAO_LOCAL_DIR:-./.data/openbao}"
KC="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-disaster}"
GW="http://localhost:${APISIX_PORT:-9080}"
HS="http://127.0.0.1:${HASURA_PORT:-8081}"
TEAM_CANO=a0000000-0000-4000-8000-000000000002   # đội của cuuho01 (seed)
TEAM_KHAC=a0000000-0000-4000-8000-000000000003   # đội khác
fail=0

check() { # check <tên> <mong đợi> <thực tế>
  if [ "$2" = "$3" ]; then echo "PASS  $1 → $3"; else echo "FAIL  $1 → $3 (mong đợi $2)"; fail=1; fi
}
get_token() { # get_token <username>
  curl -s -X POST "$KC/realms/$REALM/protocol/openid-connect/token" \
    -d grant_type=password -d client_id=dxos-dev-cli -d scope=openid \
    -d username="$1" --data-urlencode password="${KC_DEMO_USER_PASSWORD:?}" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])'
}
sub_of() { python3 -c 'import sys,json,base64; p=sys.argv[1].split(".")[1]; p+="="*(-len(p)%4); print(json.loads(base64.urlsafe_b64decode(p))["sub"])' "$1"; }
# gql <token> <query> [biến JSON] [header thêm]: POST qua gateway, in body JSON
gql() {
  local body
  body=$(python3 -c 'import sys,json; print(json.dumps({"query": sys.argv[1], "variables": json.loads(sys.argv[2])}))' "$2" "${3:-{\}}")
  curl -s -K <(printf 'header = "Authorization: Bearer %s"\n' "$1") ${4:+-H "$4"} \
    -H 'Content-Type: application/json' -d "$body" "$GW/graphql"
}
# jq_py <biểu thức python trên d> [raw]: đọc JSON từ stdin; lỗi GraphQL → in "ERR:<code>" (trừ khi raw)
jq_py() {
  python3 -c '
import sys, json
d = json.load(sys.stdin)
if "errors" in d and not sys.argv[2:]:
    print("ERR:" + d["errors"][0].get("extensions", {}).get("code", "?")); sys.exit()
print(eval(sys.argv[1], {"d": d, "json": json}))' "$@"
}
admin_secret() {
  curl -s -K <(printf 'header = "X-Vault-Token: %s"\n' "$(cat "$DIR/root.token")") "$ADDR/v1/secret/data/core/hasura" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["data"]["data"]["admin_secret"])'
}
ADMIN=$(admin_secret)
cleanup() {
  curl -s -o /dev/null -K <(printf 'header = "X-Hasura-Admin-Secret: %s"\n' "$ADMIN") -H 'Content-Type: application/json' \
    -d '{"type":"run_sql","args":{"source":"default","sql":"DELETE FROM cuu_tro.incidents WHERE description LIKE '"'"'[smoke]%'"'"'"}}' \
    "$HS/v2/query"
}
cleanup
trap cleanup EXIT

D=$(get_token dieuphoi01); C=$(get_token cuuho01); T=$(get_token tinhnguyen01)
C_SUB=$(sub_of "$C")
PT='{"type":"Point","coordinates":[108.1035,15.8502]}'
# Tin tiep_nhan mới tự khởi chạy phân công (#67): đặt ngoài bán kính mọi đội seed (~55 km) để kiểm
# quyền GraphQL mà không làm đội seed bị giao nhiệm vụ
PT_XA='{"type":"Point","coordinates":[107.6035,15.6502]}'

# ---------- (1) Không token, anonymous ----------
code=$(curl -s -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' -d '{"query":"{ incidents { id } }"}' "$GW/graphql")
check "không token: POST /graphql incidents bị APISIX chặn" 401 "$code"
check "anonymous (gọi thẳng Hasura, không JWT) không thấy bảng incidents" validation-failed \
  "$(curl -s -H 'Content-Type: application/json' -d '{"query":"{ incidents { id } }"}' "$HS/v1/graphql" \
     | jq_py 'd["errors"][0]["extensions"]["code"]' raw)"

# ---------- (2) dieu-phoi ----------
check "dieu-phoi: đọc mọi tin kêu cứu kèm SĐT (seed ≥ 5)" True \
  "$(gql "$D" '{ incidents_aggregate { aggregate { count } } incidents(limit: 1) { reporter_phone } }' | jq_py 'd["data"]["incidents_aggregate"]["aggregate"]["count"] >= 5 and bool(d["data"]["incidents"][0]["reporter_phone"])')"
check "dieu-phoi: gán cuuho01 vào đội ca nô (upsert team_members)" "$TEAM_CANO" \
  "$(gql "$D" 'mutation($u: String!, $t: uuid!) { insert_team_members_one(object: {user_id: $u, team_id: $t, username: "cuuho01"},
      on_conflict: {constraint: team_members_pkey, update_columns: [team_id, username]}) { team_id } }' \
      "{\"u\":\"$C_SUB\",\"t\":\"$TEAM_CANO\"}" | jq_py 'd["data"]["insert_team_members_one"]["team_id"]')"
NEW_INC='mutation($o: incidents_insert_input!) { insert_incidents_one(object: $o) { id status created_by } }'
# Chỉ trả id: dùng cho vai trò không được đọc created_by, để lỗi nếu có là do quyền ghi
NEW_INC_ID='mutation($o: incidents_insert_input!) { insert_incidents_one(object: $o) { id } }'
out=$(gql "$D" "$NEW_INC" "{\"o\":{\"description\":\"[smoke] tin của đội ca nô\",\"location\":$PT,\"reporter_phone\":\"0961000010\",\"status\":\"phan_cong\",\"assigned_team_id\":\"$TEAM_CANO\"}}")
INC_A=$(jq_py 'd["data"]["insert_incidents_one"]["id"]' <<<"$out")
check "dieu-phoi: tạo tin và phân công đội ca nô (created_by gán từ token)" "phan_cong $(sub_of "$D")" \
  "$(jq_py 'd["data"]["insert_incidents_one"]["status"] + " " + d["data"]["insert_incidents_one"]["created_by"]' <<<"$out")"
INC_B=$(gql "$D" "$NEW_INC" "{\"o\":{\"description\":\"[smoke] tin của đội khác\",\"location\":$PT,\"reporter_phone\":\"0961000020\",\"status\":\"phan_cong\",\"assigned_team_id\":\"$TEAM_KHAC\"}}" \
  | jq_py 'd["data"]["insert_incidents_one"]["id"]')
check "dieu-phoi: tạo tin phân công cho đội khác" True "$([[ $INC_B =~ ^[0-9a-f-]{36}$ ]] && echo True || echo "$INC_B")"
check "dieu-phoi: không có quyền xóa tin (đóng bằng status)" ERR:validation-failed \
  "$(gql "$D" 'mutation($id: uuid!) { delete_incidents_by_pk(id: $id) { id } }' "{\"id\":\"$INC_A\"}" | jq_py '')"
check "dieu-phoi: không sửa trực tiếp tồn kho supplies.quantity" ERR:validation-failed \
  "$(gql "$D" 'mutation { update_supplies(where: {}, _set: {quantity: 1}) { affected_rows } }' | jq_py '')"
check "dieu-phoi: cập nhật điểm trú ẩn" 1 \
  "$(gql "$D" 'mutation { update_shelters_by_pk(pk_columns: {id: "c0000000-0000-4000-8000-000000000003"}, _set: {status: "mo"}) { id } }' \
     | jq_py '1 if d["data"]["update_shelters_by_pk"] else 0')"
check "dieu-phoi: không thấy bảng cấu hình nội bộ incident_dedup_config" ERR:validation-failed \
  "$(gql "$D" '{ incident_dedup_config { radius_m } }' | jq_py '')"

# ---------- (3) cuu-ho ----------
out=$(gql "$C" '{ incidents { id assigned_team_id reporter_phone } }')
check "cuu-ho: thấy tin của đội mình (kèm SĐT để liên lạc)" True \
  "$(jq_py "any(i['id'] == '$INC_A' and i['reporter_phone'] for i in d['data']['incidents'])" <<<"$out")"
check "cuu-ho: không thấy tin của đội khác" True \
  "$(jq_py "all(i['assigned_team_id'] == '$TEAM_CANO' for i in d['data']['incidents']) and '$INC_B' not in [i['id'] for i in d['data']['incidents']]" <<<"$out")"
SET_STATUS='mutation($id: uuid!, $s: String!) { update_incidents(where: {id: {_eq: $id}}, _set: {status: $s}) { affected_rows } }'
check "cuu-ho: cập nhật status tin của đội mình phan_cong → dang_cuu" 1 \
  "$(gql "$C" "$SET_STATUS" "{\"id\":\"$INC_A\",\"s\":\"dang_cuu\"}" | jq_py 'd["data"]["update_incidents"]["affected_rows"]')"
check "cuu-ho: cập nhật tin của đội khác không ảnh hưởng dòng nào" 0 \
  "$(gql "$C" "$SET_STATUS" "{\"id\":\"$INC_B\",\"s\":\"dang_cuu\"}" | jq_py 'd["data"]["update_incidents"]["affected_rows"]')"
check "cuu-ho: không được đóng tin (status dong chỉ của điều phối)" ERR:permission-error \
  "$(gql "$C" "$SET_STATUS" "{\"id\":\"$INC_A\",\"s\":\"dong\"}" | jq_py '')"
check "cuu-ho: không sửa nội dung tin (chỉ cột status)" ERR:validation-failed \
  "$(gql "$C" 'mutation($id: uuid!) { update_incidents(where: {id: {_eq: $id}}, _set: {description: "x"}) { affected_rows } }' "{\"id\":\"$INC_A\"}" | jq_py '')"
check "cuu-ho: không tạo tin kêu cứu" ERR:validation-failed \
  "$(gql "$C" "$NEW_INC_ID" "{\"o\":{\"description\":\"[smoke] x\",\"location\":$PT,\"reporter_phone\":\"0961000030\"}}" | jq_py '')"
check "cuu-ho: đọc điểm trú ẩn" True "$(gql "$C" '{ shelters { name } }' | jq_py 'len(d["data"]["shelters"]) >= 3')"
check "cuu-ho: chỉ thấy đội của mình" "$TEAM_CANO" "$(gql "$C" '{ rescue_teams { id } }' | jq_py '",".join(t["id"] for t in d["data"]["rescue_teams"])')"
check "cuu-ho: không đọc kho hàng supplies" ERR:validation-failed "$(gql "$C" '{ supplies { item_name } }' | jq_py '')"

# ---------- (4) tinh-nguyen ----------
PHONE="097$(date +%S%M%H | cut -c1-6)0"
out=$(gql "$T" "mutation(\$o: incidents_insert_input!) { insert_incidents_one(object: \$o) { id status } }" \
  "{\"o\":{\"description\":\"[smoke] tình nguyện viên báo\",\"location\":$PT_XA,\"reporter_phone\":\"$PHONE\",\"people_count\":2,\"source\":\"app\"}}")
INC_T=$(jq_py 'd["data"]["insert_incidents_one"]["id"]' <<<"$out")
check "tinh-nguyen: tạo tin kêu cứu (trạng thái tiep_nhan)" tiep_nhan "$(jq_py 'd["data"]["insert_incidents_one"]["status"]' <<<"$out")"
check "tinh-nguyen: không tự đặt status/đội khi tạo tin" ERR:validation-failed \
  "$(gql "$T" "$NEW_INC_ID" "{\"o\":{\"description\":\"[smoke] x\",\"location\":$PT,\"reporter_phone\":\"0961000040\",\"status\":\"dong\"}}" | jq_py '')"
check "tinh-nguyen: không đọc được SĐT người báo (column-level)" ERR:validation-failed \
  "$(gql "$T" '{ incidents { id reporter_phone } }' | jq_py '')"
check "tinh-nguyen: chỉ thấy tin mình tạo" "$INC_T" "$(gql "$T" '{ incidents { id } }' | jq_py '",".join(i["id"] for i in d["data"]["incidents"])')"
check "tinh-nguyen: không sửa tin" ERR:validation-failed \
  "$(gql "$T" "$SET_STATUS" "{\"id\":\"$INC_T\",\"s\":\"dong\"}" | jq_py '')"
check "tinh-nguyen: không xóa tin" ERR:validation-failed \
  "$(gql "$T" 'mutation($id: uuid!) { delete_incidents_by_pk(id: $id) { id } }' "{\"id\":\"$INC_T\"}" | jq_py '')"
check "tinh-nguyen: báo trùng (cùng SĐT, cùng chỗ) bị chặn" "constraint-violation True" \
  "$(gql "$T" "$NEW_INC_ID" "{\"o\":{\"description\":\"[smoke] báo lại\",\"location\":$PT_XA,\"reporter_phone\":\"$PHONE\"}}" \
     | jq_py '"%s %s" % (d["errors"][0]["extensions"]["code"], "trùng" in d["errors"][0]["message"])' raw)"
check "tinh-nguyen: đọc điểm trú ẩn và kho hàng" True \
  "$(gql "$T" '{ shelters { name } supplies { item_name quantity } }' | jq_py 'len(d["data"]["shelters"]) >= 3 and len(d["data"]["supplies"]) >= 4')"
check "tinh-nguyen: không thấy đội cứu hộ, thành viên đội" ERR:validation-failed "$(gql "$T" '{ rescue_teams { id } }' | jq_py '')"
check "tinh-nguyen: xin vai trò dieu-phoi (ngoài allowed-roles) bị chặn" ERR:access-denied \
  "$(gql "$T" '{ incidents { id } }' '{}' 'X-Hasura-Role: dieu-phoi' | jq_py '')"
check "tinh-nguyen: không thấy lịch sử giao nhiệm vụ (#67)" ERR:validation-failed \
  "$(gql "$T" '{ incident_assignments { id } }' | jq_py '')"
check "dieu-phoi: đọc lịch sử giao nhiệm vụ, không có mutation thêm (#67)" "True ERR:validation-failed" \
  "$(gql "$D" '{ incident_assignments_aggregate { aggregate { count } } }' | jq_py '"data" in d') $(gql "$D" 'mutation { insert_incident_assignments_one(object: {}) { id } }' | jq_py '')"
check "dieu-phoi: không thấy hàng đợi nội bộ assignment_queue" ERR:validation-failed \
  "$(gql "$D" '{ assignment_queue { incident_id } }' | jq_py '')"

# ---------- (5) Truy vấn vị trí PostGIS ----------
NEAR='query($p: geography!, $r: Float!) { incidents(where: {location: {_st_d_within: {from: $p, distance: $r}}}) { id } }'
check "dieu-phoi: _st_d_within 300 m quanh thôn 1 có tin seed b…01" True \
  "$(gql "$D" "$NEAR" "{\"p\":$PT,\"r\":300}" | jq_py '"b0000000-0000-4000-8000-000000000001" in [i["id"] for i in d["data"]["incidents"]]')"
check "dieu-phoi: _st_d_within 300 m không gồm tin ở thôn 3 (~1,5 km)" True \
  "$(gql "$D" "$NEAR" "{\"p\":$PT,\"r\":300}" | jq_py '"b0000000-0000-4000-8000-000000000003" not in [i["id"] for i in d["data"]["incidents"]]')"
check "tinh-nguyen: điểm trú ẩn trong 1 km (lọc vị trí kèm quyền vai trò)" True \
  "$(gql "$T" 'query($p: geography!) { shelters(where: {location: {_st_d_within: {from: $p, distance: 1000}}}) { name } }' \
     "{\"p\":$PT}" | jq_py 'len(d["data"]["shelters"]) >= 1')"

if [ "$fail" -ne 0 ]; then echo "CÓ CA FAIL"; exit 1; fi
echo "OK: phân quyền GraphQL theo vai trò qua gateway đạt"
