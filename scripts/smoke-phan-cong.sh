#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử màn phân công của web điều phối (#61) qua API Gateway, đúng các lời gọi web gửi đi:
# GraphQL hàng đợi/chi tiết (đọc NGUYÊN VĂN query từ apps/cuu-tro/web/utils/phan-cong.ts) và REST /workflow/*.
# (1) đường SPA /phan-cong, /phan-cong/<id> qua gateway trả 200 HTML;
# (2) dieu-phoi tạo tin khan_cap → workflow tự giao Đội xung kích thôn 1; hàng đợi của dieu-phoi có tin, đội,
#     lần giao cho_nhan còn hạn, KHÔNG có SĐT; chi tiết của dieu-phoi có SĐT;
# (3) vai sai: tinh-nguyen không đọc được hàng đợi, xem/nhận workflow → 403; cuu-ho đội khác không thấy tin,
#     xem/nhận → 403;
# (4) dieu-phoi đổi đội (signal từ chối thay đội) → workflow giao Đội ca nô (đội của cuuho01), lịch sử ghi
#     tu_choi bởi dieuphoi01 kèm ghi chú;
# (5) đăng nhập vai cuu-ho → thấy nhiệm vụ trong hàng đợi (chỉ lần giao của đội mình) và SĐT ở chi tiết →
#     nhận nhiệm vụ → tin dang_cuu; nhận lần hai → 409; cuu-ho hủy → 403; dieu-phoi hủy sau khi đội nhận → 409;
#     xác nhận đã cứu → workflow da_dong, tin dong, đội san_sang; xác nhận lần hai → 409; tin rời hàng đợi.
# Tin tạo ra bị xóa, đội và thành viên đội về trạng thái seed khi kết thúc.
# Dùng: make up && make seed && bash scripts/smoke-phan-cong.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

KC="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-disaster}"
GW="http://localhost:${APISIX_PORT:-9080}"
TEAM_GAN=a0000000-0000-4000-8000-000000000001  # Đội xung kích thôn 1: sẵn sàng, gần nhất
TEAM_CANO=a0000000-0000-4000-8000-000000000002 # Đội ca nô: đội của cuuho01 trong seed, gần nhì
TS_FILE=apps/cuu-tro/web/utils/phan-cong.ts
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
# api <token|-> <METHOD> <đường dẫn sau /workflow> [body JSON]: in "<mã HTTP> <body>"
api() {
  local tok=$1 method=$2 path=$3 body=${4:-} out code
  out=$(mktemp)
  local args=(-s -o "$out" -w '%{http_code}' -X "$method" -H 'Content-Type: application/json')
  [ -n "$body" ] && args+=(-d "$body")
  if [ "$tok" = - ]; then code=$(curl "${args[@]}" "$GW/workflow$path")
  else code=$(curl -K <(printf 'header = "Authorization: Bearer %s"\n' "$tok") "${args[@]}" "$GW/workflow$path"); fi
  printf '%s %s\n' "$code" "$(cat "$out")"
  rm -f "$out"
}
http_code() { printf '%s' "${1%% *}"; }
jf() { python3 -c 'import sys,json; d=json.loads(sys.stdin.read().split(" ", 1)[1]); print(eval(sys.argv[1], {"d": d}))' "$1"; }
sql() { docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -q -v ON_ERROR_STOP=1'; }
temporal_cli() { docker compose exec -T temporal sh -c "temporal $* --address temporal:7233"; }

# Query GraphQL của web: dựng lại từ mã TS (TRUONG_TIN + Q_HANG_PHAN_CONG / queryTinPhanCong) để không lệch
web_query() { # web_query hang | chi-tiet | chi-tiet-lien-he
  python3 - "$TS_FILE" "$1" <<'PY'
import re, sys
src = open(sys.argv[1], encoding="utf-8").read()
truong = re.search(r"const TRUONG_TIN = `(.*?)`", src, re.S).group(1)
if sys.argv[2] == "hang":
    q = re.search(r"export const Q_HANG_PHAN_CONG = `(.*?)`", src, re.S).group(1)
    print(q.replace("${TRUONG_TIN}", truong))
else:
    q = re.search(r"return `(query TinPhanCong.*?)`", src, re.S).group(1)
    lien_he = re.search(r"\? '( reporter_phone reporter_name)'", src).group(1) if sys.argv[2] == "chi-tiet-lien-he" else ""
    print(q.replace("${TRUONG_TIN}", truong).replace("${lienHe}", lien_he))
PY
}
# gql <token> <vai> <hang|chi-tiet|chi-tiet-lien-he> → body JSON của Hasura
gql() {
  local q body
  q=$(web_query "$3")
  if [ "$3" = hang ]; then
    body=$(python3 -c 'import json,sys; print(json.dumps({"query": sys.argv[1], "variables": {"trangThai": ["tiep_nhan", "phan_cong", "dang_cuu"]}}))' "$q")
  else
    body=$(python3 -c 'import json,sys; print(json.dumps({"query": sys.argv[1], "variables": {"id": sys.argv[2]}}))' "$q" "$NEW")
  fi
  curl -s -K <(printf 'header = "Authorization: Bearer %s"\n' "$1") -H 'Content-Type: application/json' \
    -H "X-Hasura-Role: $2" -d "$body" "$GW/graphql"
}
# trong_hang <body hàng đợi>: "<có tin NEW>|<status>|<số lần giao thấy được>|<kết quả lần cuối>|<có SĐT>"
trong_hang() {
  python3 -c '
import sys, json
d = json.loads(sys.argv[1]); ds = (d.get("data") or {}).get("incidents") or []
t = next((x for x in ds if x["id"] == sys.argv[2]), None)
if t is None: print("khong"); sys.exit()
g = t["assignments"]
print("co|%s|%d|%s|%s" % (t["status"], len(g), g[-1]["result"] if g else "-", "reporter_phone" in t))' "$1" "$NEW"
}
cho_wf() { # cho_wf <token> <workflow_id> <biểu thức python trên d>: chờ tối đa 30 giây
  local out=""
  for _ in $(seq 1 30); do
    out=$(api "$1" GET "/$2")
    [ "$(jf "$3" <<<"$out" 2>/dev/null || true)" = True ] && break
    sleep 1
  done
  printf '%s' "$out"
}
lich_su_giao() {
  sql <<<"SELECT coalesce(string_agg(team_id || ':' || result || ':' || coalesce(responded_by, '-'), ',' ORDER BY assigned_at, attempt_no), '') FROM cuu_tro.incident_assignments WHERE incident_id = '$1'"
}

D=$(get_token dieuphoi01); C=$(get_token cuuho01); T=$(get_token tinhnguyen01)
C_SUB=$(sub_of "$C")
NEW=''
reset() {
  local xoa=""
  if [ -n "$NEW" ]; then
    temporal_cli workflow terminate -w "phan-cong-$NEW" --reason smoke-reset >/dev/null 2>&1 || true
    xoa="DELETE FROM cuu_tro.incidents WHERE id = '$NEW';"
  fi
  sql >/dev/null <<SQL
$xoa
UPDATE cuu_tro.rescue_teams SET status = 'san_sang' WHERE id IN ('$TEAM_GAN', '$TEAM_CANO');
INSERT INTO cuu_tro.team_members (user_id, team_id, username) VALUES ('$C_SUB', '$TEAM_CANO', 'cuuho01')
  ON CONFLICT (user_id) DO UPDATE SET team_id = EXCLUDED.team_id;
SQL
}
reset
trap reset EXIT

# ---------- (1) đường SPA ----------
for p in /phan-cong /phan-cong/b0000000-0000-4000-8000-000000000004; do
  check "GET $p (đường SPA) qua gateway" 200 "$(curl -s -o /dev/null -w '%{http_code}' "$GW$p")"
done

# ---------- (2) tin mới, tự giao đội gần nhất; hàng đợi của điều phối ----------
PHONE="0967$(date +%H%M%S | cut -c1-6)"
# shellcheck disable=SC2016 # $o là biến GraphQL
body=$(python3 -c 'import json,sys; print(json.dumps({"query": "mutation($o: incidents_insert_input!) { insert_incidents_one(object: $o) { id } }", "variables": {"o": {"description": "[smoke #61] nuoc len nhanh, 2 nguoi gia tren gac", "location": {"type": "Point", "coordinates": [108.1003, 15.8528]}, "urgency": "khan_cap", "people_count": 2, "reporter_phone": sys.argv[1], "source": "web"}}}))' "$PHONE")
out=$(curl -s -K <(printf 'header = "Authorization: Bearer %s"\n' "$D") -H 'Content-Type: application/json' -H 'X-Hasura-Role: dieu-phoi' -d "$body" "$GW/graphql")
NEW=$(python3 -c 'import sys,json; print(json.load(sys.stdin)["data"]["insert_incidents_one"]["id"])' <<<"$out" 2>/dev/null || true)
check "dieu-phoi tạo tin khan_cap" True "$([[ $NEW =~ ^[0-9a-f-]{36}$ ]] && echo True || echo "$out")"
WF="phan-cong-$NEW"
out=$(cho_wf "$D" "$WF" 'd["chi_tiet"]["buoc"] == "cho_nhan"')
check "workflow tự giao Đội xung kích thôn 1, chờ nhận" "cho_nhan $TEAM_GAN" "$(jf 'd["chi_tiet"]["buoc"] + " " + str(d["chi_tiet"]["doi_id"])' <<<"$out")"
h=$(gql "$D" dieu-phoi hang)
check "hàng đợi dieu-phoi: tin phan_cong, 1 lần giao cho_nhan, không có SĐT" "co|phan_cong|1|cho_nhan|False" "$(trong_hang "$h")"
check "hàng đợi dieu-phoi: đội hiện tại + hạn nhận còn trong tương lai" "Đội xung kích thôn 1 True" "$(python3 -c '
import sys, json, datetime as dt
t = next(x for x in json.loads(sys.argv[1])["data"]["incidents"] if x["id"] == sys.argv[2])
g = t["assignments"][-1]
print(t["assigned_team"]["name"], dt.datetime.fromisoformat(g["deadline_at"]) > dt.datetime.now(dt.timezone.utc))' "$h" "$NEW")"
check "chi tiết dieu-phoi có SĐT người báo" "$PHONE" "$(python3 -c 'import sys,json; print(json.loads(sys.argv[1])["data"]["incidents_by_pk"]["reporter_phone"])' "$(gql "$D" dieu-phoi chi-tiet-lien-he)")"

# ---------- (3) vai sai ----------
check "tinh-nguyen đọc hàng đợi phân công → Hasura báo lỗi quyền" True \
  "$(python3 -c 'import sys,json; print(bool(json.loads(sys.argv[1]).get("errors")))' "$(gql "$T" tinh-nguyen hang)")"
check "tinh-nguyen xem workflow" 403 "$(http_code "$(api "$T" GET "/$WF")")"
check "tinh-nguyen nhận nhiệm vụ" 403 "$(http_code "$(api "$T" POST "/$WF/nhan" '{}')")"
check "cuu-ho đội khác: hàng đợi không có tin" khong "$(trong_hang "$(gql "$C" cuu-ho hang)")"
check "cuu-ho đội khác xem workflow" 403 "$(http_code "$(api "$C" GET "/$WF")")"
check "cuu-ho đội khác nhận nhiệm vụ" 403 "$(http_code "$(api "$C" POST "/$WF/nhan" '{}')")"
check "cuu-ho đổi đội (signal từ chối) cho đội khác" 403 "$(http_code "$(api "$C" POST "/$WF/tu-choi" '{"ghi_chu":"x"}')")"
check "không token xem workflow (APISIX chặn)" 401 "$(http_code "$(api - GET "/$WF")")"

# ---------- (4) điều phối đổi đội ----------
check "dieu-phoi đổi đội" 202 "$(http_code "$(api "$D" POST "/$WF/tu-choi" '{"ghi_chu":"Điều phối đổi đội: smoke"}')")"
out=$(cho_wf "$D" "$WF" 'd["chi_tiet"]["buoc"] == "cho_nhan" and d["chi_tiet"]["doi_id"] == "'"$TEAM_CANO"'"')
check "workflow giao Đội ca nô (gần nhì), lần giao 2" "cho_nhan $TEAM_CANO 2" \
  "$(jf 'd["chi_tiet"]["buoc"] + " " + str(d["chi_tiet"]["doi_id"]) + " " + str(len(d["chi_tiet"]["giao"]))' <<<"$out")"
check "DB: lịch sử tu_choi bởi dieuphoi01 kèm ghi chú, rồi cho_nhan" "$TEAM_GAN:tu_choi:dieuphoi01,$TEAM_CANO:cho_nhan:-|Điều phối đổi đội: smoke" \
  "$(lich_su_giao "$NEW")|$(sql <<<"SELECT note FROM cuu_tro.incident_assignments WHERE incident_id = '$NEW' AND attempt_no = 1")"

# ---------- (5) vai cuu-ho: nhận → đang cứu → đã cứu ----------
check "hàng đợi cuu-ho: thấy nhiệm vụ, chỉ lần giao của đội mình, không SĐT" "co|phan_cong|1|cho_nhan|False" "$(trong_hang "$(gql "$C" cuu-ho hang)")"
check "chi tiết cuu-ho có SĐT người báo (để liên lạc)" "$PHONE" "$(python3 -c 'import sys,json; print(json.loads(sys.argv[1])["data"]["incidents_by_pk"]["reporter_phone"])' "$(gql "$C" cuu-ho chi-tiet-lien-he)")"
check "cuu-ho xem workflow của đội mình" "200 cho_nhan" "$(out=$(api "$C" GET "/$WF"); echo "$(http_code "$out") $(jf 'd["chi_tiet"]["buoc"]' <<<"$out")")"
check "cuu-ho hủy (chỉ dieu-phoi)" 403 "$(http_code "$(api "$C" POST "/$WF/huy" '{}')")"
check "cuu-ho nhận nhiệm vụ" 202 "$(http_code "$(api "$C" POST "/$WF/nhan" '{"ghi_chu":"dang den bang ca no"}')")"
out=$(cho_wf "$C" "$WF" 'd["chi_tiet"]["buoc"] == "cho_xac_nhan"')
check "workflow sang chờ xác nhận đã cứu" cho_xac_nhan "$(jf 'd["chi_tiet"]["buoc"]' <<<"$out")"
check "DB: tin dang_cuu; lần giao 2 da_nhan bởi cuuho01" "dang_cuu|$TEAM_CANO:da_nhan:cuuho01" \
  "$(sql <<<"SELECT status FROM cuu_tro.incidents WHERE id = '$NEW'")|$(lich_su_giao "$NEW" | cut -d, -f2)"
check "cuu-ho nhận lần hai (đã sang bước khác)" 409 "$(http_code "$(api "$C" POST "/$WF/nhan" '{}')")"
check "dieu-phoi hủy khi đội đã nhận" 409 "$(http_code "$(api "$D" POST "/$WF/huy" '{"ly_do":"smoke"}')")"
check "hàng đợi cuu-ho: tin dang_cuu" "co|dang_cuu|1|da_nhan|False" "$(trong_hang "$(gql "$C" cuu-ho hang)")"
check "cuu-ho xác nhận đã cứu" 202 "$(http_code "$(api "$C" POST "/$WF/xac-nhan" '{"ghi_chu":"da dua 2 nguoi len diem so tan"}')")"
out=$(cho_wf "$C" "$WF" 'd["trang_thai"] == "COMPLETED"')
check "workflow kết thúc da_dong, người xác nhận cuuho01" "COMPLETED da_dong cuuho01" \
  "$(jf 'd["trang_thai"] + " " + str(d["chi_tiet"]["ket_qua"]) + " " + d["chi_tiet"]["xac_nhan"]["nguoi"]' <<<"$out")"
check "DB: tin dong, Đội ca nô san_sang" "dong|san_sang" \
  "$(sql <<<"SELECT i.status || '|' || t.status FROM cuu_tro.incidents i JOIN cuu_tro.rescue_teams t ON t.id = i.assigned_team_id WHERE i.id = '$NEW'")"
check "cuu-ho xác nhận lần hai" 409 "$(http_code "$(api "$C" POST "/$WF/xac-nhan" '{}')")"
check "tin đã đóng rời hàng đợi của dieu-phoi" khong "$(trong_hang "$(gql "$D" dieu-phoi hang)")"

if [ "$fail" -ne 0 ]; then echo "CÓ LỖI: xem các dòng FAIL"; exit 1; fi
echo "OK: smoke màn phân công (#61) qua gateway đạt"
