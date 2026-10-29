#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Smoke riêng của module mẫu muon-thiet-bi (#110), gọi THẬT qua APISIX bằng token realm `thiet-bi`:
# (1) lõi chạy với module: realm, Hasura metadata, schema muon_thiet_bi, role <schema>_app/_bi do lõi tạo,
#     không có dịch vụ/bảng nào của apps/cuu-tro; không token → 401;
# (2) phân quyền theo vai: quan-ly thêm/sửa thiết bị, đọc mọi lượt mượn; nguoi-muon chỉ đọc thiết bị, mượn cho
#     chính mình (borrower_sub gán từ JWT, không giả mạo được), chỉ thấy lượt của mình, không sửa/xóa;
# (3) Poka-yoke trong CSDL qua GraphQL: thiết bị đang có người mượn, thiết bị hỏng, hạn trả quá 30 ngày → lỗi;
#     hai người mượn cùng một thiết bị cùng lúc → đúng một lượt; trả xong mượn lại được.
# Dùng (từ gốc repo, .env có các biến trong apps/muon-thiet-bi/module.env): make up && make seed && make smoke-app
# shellcheck disable=SC2016 # biến GraphQL ($d, $h) và biến của psql trong container cố ý nằm trong nháy đơn
set -euo pipefail
cd "$(dirname "$0")/../../.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

KC="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-thiet-bi}"
GW="http://localhost:${APISIX_PORT:-9080}"
[ "${DXOS_APP:-}" = muon-thiet-bi ] || { echo "Cần DXOS_APP=muon-thiet-bi (apps/muon-thiet-bi/module.env)"; exit 2; }
fail=0
check() { if [ "$2" = "$3" ]; then echo "PASS  $1 → $3"; else echo "FAIL  $1 → $3 (mong đợi $2)"; fail=1; fi; }
token() {
  curl -s -m 20 -X POST "$KC/realms/$REALM/protocol/openid-connect/token" -d grant_type=password -d client_id=dxos-dev-cli \
    -d scope=openid -d username="$1" --data-urlencode password="${KC_DEMO_USER_PASSWORD:?}" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])'
}
# gql <token> <query> [biến JSON] → JSON
gql() {
  local body
  body=$(python3 -c 'import sys,json; print(json.dumps({"query": sys.argv[1], "variables": json.loads(sys.argv[2])}))' "$2" "${3:-{\}}")
  curl -s -m 30 -K <(printf 'header = "Authorization: Bearer %s"\n' "$1") -H 'Content-Type: application/json' -d "$body" "$GW/graphql"
}
# jq_py <biểu thức trên d>: lỗi GraphQL → "ERR:<code>"
jq_py() {
  python3 -c '
import sys, json
d = json.load(sys.stdin)
if "errors" in d:
    print("ERR:" + d["errors"][0].get("extensions", {}).get("code", "?")); sys.exit()
print(eval(sys.argv[1], {"d": d}))' "$1"
}
# loi_gql: thông điệp lỗi GraphQL đầu tiên (Hasura báo vi phạm CHECK bằng mã permission-error, kèm thông điệp)
loi_gql() { python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["errors"][0]["message"] if "errors" in d else "KHONG_LOI")'; }
sql() { timeout 60 docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -q -v ON_ERROR_STOP=1'; }
reset() { sql >/dev/null <<<"DELETE FROM muon_thiet_bi.loans WHERE purpose LIKE '[smoke]%'; DELETE FROM muon_thiet_bi.devices WHERE code LIKE 'SMOKE-%';" || true; }
reset
trap reset EXIT

QL=$(token quanly01); M1=$(token nguoimuon01); M2=$(token nguoimuon02)
M1_SUB=$(python3 -c 'import sys,json,base64; p=sys.argv[1].split(".")[1]; p+="="*(-len(p)%4); print(json.loads(base64.urlsafe_b64decode(p))["sub"])' "$M1")
HAN=$(python3 -c 'import datetime; print((datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=3)).isoformat())')
HAN_XA=$(python3 -c 'import datetime; print((datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=40)).isoformat())')

# ---------- (1) Lõi chạy với module ----------
check "không token → 401 ở gateway" 401 \
  "$(curl -s -m 20 -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' -d '{"query":"{ devices { id } }"}' "$GW/graphql")"
check "schema muon_thiet_bi do cơ chế migration của lõi tạo, có lịch sử" "t 1" \
  "$(sql <<<"SELECT EXISTS (SELECT FROM pg_namespace WHERE nspname = 'muon_thiet_bi')::text, (SELECT count(*) FROM dxos_meta.app_migrations WHERE app = 'muon-thiet-bi')" | tr '|' ' ' | sed 's/true/t/')"
check "role dịch vụ và role chỉ đọc theo quy ước tên của lõi" "muon_thiet_bi_app muon_thiet_bi_bi muon_thiet_bi_owner" \
  "$(sql <<<"SELECT string_agg(rolname, ' ' ORDER BY rolname) FROM pg_roles WHERE rolname LIKE 'muon_thiet_bi_%'")"
check "không có schema hay dịch vụ của apps/cuu-tro" "f 0" \
  "$(sql <<<"SELECT EXISTS (SELECT FROM pg_namespace WHERE nspname = 'cuu_tro')" | sed 's/false/f/') $(docker compose ps --format '{{.Name}}' | grep -c cuu-tro || true)"
check "module không có backend: / và /workflow/* trả 503, gateway vẫn khỏe (/healthz 200)" "503 503 200" \
  "$(curl -s -m 20 -o /dev/null -w '%{http_code}' "$GW/") $(curl -s -m 20 -o /dev/null -w '%{http_code}' -X POST \
      -K <(printf 'header = "Authorization: Bearer %s"\n' "$QL") "$GW/workflow/hello") $(curl -s -m 20 -o /dev/null -w '%{http_code}' "$GW/healthz")"
check "quan-ly thấy 4 thiết bị mẫu" 4 "$(gql "$QL" '{ devices_aggregate { aggregate { count } } }' | jq_py 'd["data"]["devices_aggregate"]["aggregate"]["count"]')"

# ---------- (2) Phân quyền theo vai ----------
DEV=$(gql "$QL" 'mutation { insert_devices_one(object: {code: "SMOKE-01", name: "[smoke] máy cắt cỏ", kind: "dung_cu"}) { id } }' | jq_py 'd["data"]["insert_devices_one"]["id"]')
check "quan-ly thêm thiết bị" True "$(python3 -c 'import sys,uuid; uuid.UUID(sys.argv[1]); print(True)' "$DEV" 2>/dev/null || echo "$DEV")"
check "nguoi-muon không thêm thiết bị" ERR:validation-failed \
  "$(gql "$M1" 'mutation { insert_devices_one(object: {code: "SMOKE-02", name: "x", kind: "khac"}) { id } }' | jq_py d)"
check "nguoi-muon không đọc ghi chú nội bộ của thiết bị" ERR:validation-failed "$(gql "$M1" '{ devices { note } }' | jq_py d)"
L1=$(gql "$M1" 'mutation($d: uuid!, $h: timestamptz!) { insert_loans_one(object: {device_id: $d, due_at: $h, purpose: "[smoke] cắt cỏ sân chung"}) { id } }' \
  "{\"d\": \"$DEV\", \"h\": \"$HAN\"}" | jq_py 'd["data"]["insert_loans_one"]["id"]')
check "nguoimuon01 mượn thiết bị → người mượn = sub trong JWT" "$M1_SUB" \
  "$(sql <<<"SELECT borrower_sub FROM muon_thiet_bi.loans WHERE id = '$L1'")"
check "nguoi-muon không tự đặt người mượn (giả mạo borrower_sub)" ERR:validation-failed \
  "$(gql "$M2" 'mutation($d: uuid!, $h: timestamptz!) { insert_loans_one(object: {device_id: $d, due_at: $h, borrower_sub: "nguoi-khac"}) { id } }' \
      "{\"d\": \"d0000000-0000-4000-8000-000000000002\", \"h\": \"$HAN\"}" | jq_py d)"
check "nguoimuon02 không thấy lượt mượn của nguoimuon01" 0 \
  "$(gql "$M2" '{ loans { id } }' | jq_py 'len(d["data"]["loans"])')"
check "quan-ly thấy lượt mượn của mọi người" True \
  "$(gql "$QL" "{ loans(where: {id: {_eq: \"$L1\"}}) { borrower_sub } }" | jq_py "d['data']['loans'][0]['borrower_sub'] == '$M1_SUB'")"
check "nguoi-muon không tự ghi nhận đã trả" ERR:validation-failed \
  "$(gql "$M1" "mutation { update_loans_by_pk(pk_columns: {id: \"$L1\"}, _set: {returned_at: \"now()\"}) { id } }" | jq_py d)"
check "không vai trò nào xóa được lượt mượn" "ERR:validation-failed ERR:validation-failed" \
  "$(gql "$QL" "mutation { delete_loans_by_pk(id: \"$L1\") { id } }" | jq_py d) $(gql "$M1" "mutation { delete_loans_by_pk(id: \"$L1\") { id } }" | jq_py d)"

# ---------- (3) Poka-yoke trong CSDL qua GraphQL ----------
check "mượn thiết bị đang có người mượn → chỉ mục loans_one_open_per_device" "co-loi" \
  "$(gql "$M2" 'mutation($d: uuid!, $h: timestamptz!) { insert_loans_one(object: {device_id: $d, due_at: $h, purpose: "[smoke] trùng"}) { id } }' \
      "{\"d\": \"$DEV\", \"h\": \"$HAN\"}" | loi_gql | grep -q 'loans_one_open_per_device' && echo co-loi || echo khong)"
check "mượn thiết bị hỏng (máy chiếu MC-01) → trigger loans_guard chặn" "co-loi" \
  "$(gql "$M2" 'mutation($h: timestamptz!) { insert_loans_one(object: {device_id: "d0000000-0000-4000-8000-000000000004", due_at: $h, purpose: "[smoke] hỏng"}) { id } }' \
      "{\"h\": \"$HAN\"}" | loi_gql | grep -q 'đang hong, không cho mượn' && echo co-loi || echo khong)"
check "hạn trả quá 30 ngày → ràng buộc loans_max_30_days" "co-loi" \
  "$(gql "$M2" 'mutation($h: timestamptz!) { insert_loans_one(object: {device_id: "d0000000-0000-4000-8000-000000000002", due_at: $h, purpose: "[smoke] lâu"}) { id } }' \
      "{\"h\": \"$HAN_XA\"}" | loi_gql | grep -q 'loans_max_30_days' && echo co-loi || echo khong)"
TMP=$(mktemp -d)
for t in "$M1" "$M2"; do
  gql "$t" 'mutation($h: timestamptz!) { insert_loans_one(object: {device_id: "d0000000-0000-4000-8000-000000000002", due_at: $h, purpose: "[smoke] đồng thời"}) { id } }' \
    "{\"h\": \"$HAN\"}" >"$TMP/$RANDOM.json" &
done
wait
check "hai người mượn máy bơm cùng lúc → đúng 1 lượt mở" 1 \
  "$(sql <<<"SELECT count(*) FROM muon_thiet_bi.loans WHERE device_id = 'd0000000-0000-4000-8000-000000000002' AND returned_at IS NULL")"
rm -rf "$TMP"
check "quan-ly ghi nhận đã trả" "$L1" \
  "$(gql "$QL" "mutation { update_loans_by_pk(pk_columns: {id: \"$L1\"}, _set: {returned_at: \"now()\", return_note: \"[smoke] đủ đồ\"}) { id } }" | jq_py 'd["data"]["update_loans_by_pk"]["id"]')"
check "trả xong thì người khác mượn được" True \
  "$(gql "$M2" 'mutation($d: uuid!, $h: timestamptz!) { insert_loans_one(object: {device_id: $d, due_at: $h, purpose: "[smoke] lượt hai"}) { id } }' \
      "{\"d\": \"$DEV\", \"h\": \"$HAN\"}" | jq_py '"id" in d["data"]["insert_loans_one"]')"
check "lượt đã trả không sửa được nữa (kể cả quan-ly)" "co-loi" \
  "$(gql "$QL" "mutation { update_loans_by_pk(pk_columns: {id: \"$L1\"}, _set: {return_note: \"sửa\"}) { id } }" | loi_gql | grep -q 'đã trả, không sửa được' && echo co-loi || echo khong)"

if [ "$fail" -eq 0 ]; then echo "OK: smoke module muon-thiet-bi đạt"; else echo "CÓ LỖI: xem các dòng FAIL"; exit 1; fi
