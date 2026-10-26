#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử hàng chờ duyệt tin do AI bóc tách (#104, HITL), gọi THẬT qua APISIX bằng token Keycloak của user mẫu
# (chế độ LLM_PROVIDER đang cấu hình, mặc định gia-lap):
# (1) tinh-nguyen đưa tin vào hàng chờ (POST /workflow/ai/boc-tach, vao_hang_cho) → dòng cho_duyet trong CSDL,
#     đúng người gửi, CHƯA tạo tin kêu cứu;
# (2) quyền đọc qua /graphql: dieu-phoi thấy văn bản gốc + đề xuất; tinh-nguyen chỉ thấy trạng thái tin mình gửi,
#     không thấy văn bản; cuu-ho không thấy bảng; không vai trò nào thêm/sửa qua GraphQL;
# (3) duyệt: không token 401, tinh-nguyen/cuu-ho 403; dieu-phoi duyệt nguyên đề xuất → 201, tin kêu cứu thật có
#     created_by = người gửi, vào hàng phân công tự động, vết duyệt (người duyệt, thời điểm, trường sửa rỗng);
#     tinh-nguyen thấy tin mình chuyển; duyệt/hủy lại → 409;
# (4) tin thiếu tọa độ: duyệt nguyên đề xuất → 422 lat/lon, không tạo tin; sửa (chọn vị trí, đổi số người) →
#     201, vết ghi giá trị AI → giá trị người duyệt;
# (5) tin trùng: đề xuất báo trùng, duyệt → 409 kèm mã tin đang mở, mục vẫn chờ duyệt; hủy có lý do → da_huy,
#     không tạo tin;
# (6) hai người duyệt cùng lúc → đúng 1 × 201 + 1 × 409, đúng 1 tin;
# (7) vết không sửa được (trigger chặn cả superuser); tin có vết duyệt không xóa được;
# (8) đầu vào sai: lý do > 500 ký tự 422, mã không có 404, mã sai dạng 422; WAF chặn XSS;
# (9) log cuu-tro-api và APISIX không có SĐT hay nội dung tin; web /hang-cho mở được qua gateway.
# SĐT giả 0900104xxx, tọa độ giả ở Hà Nội (xa đội mẫu); dữ liệu thử bị xóa khi kết thúc.
# Dùng: make up && make seed && bash scripts/smoke-hang-cho.sh
# shellcheck disable=SC2016 # biến GraphQL ($id) cố ý nằm trong nháy đơn, không phải biến shell
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

KC="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-disaster}"
GW="http://localhost:${APISIX_PORT:-9080}"
fail=0

check() { # check <tên> <mong đợi> <thực tế>
  if [ "$2" = "$3" ]; then echo "PASS  $1 → $3"; else echo "FAIL  $1 → $3 (mong đợi $2)"; fail=1; fi
}
get_token() { # get_token <username>
  curl -s -m 20 -X POST "$KC/realms/$REALM/protocol/openid-connect/token" \
    -d grant_type=password -d client_id=dxos-dev-cli -d scope=openid \
    -d username="$1" --data-urlencode password="${KC_DEMO_USER_PASSWORD:?}" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])'
}
sub_of() { python3 -c 'import sys,json,base64; p=sys.argv[1].split(".")[1]; p+="="*(-len(p)%4); print(json.loads(base64.urlsafe_b64decode(p))["sub"])' "$1"; }
# post <đường dẫn> <token|-> <body>: in "<mã HTTP> <body>"
post() {
  local path=$1 tok=$2 body=$3 out code
  out=$(mktemp)
  local args=(-s -m 60 -o "$out" -w '%{http_code}' -X POST -H 'Content-Type: application/json' --data-binary "$body")
  if [ "$tok" = - ]; then code=$(curl "${args[@]}" "$GW$path")
  else code=$(curl -K <(printf 'header = "Authorization: Bearer %s"\n' "$tok") "${args[@]}" "$GW$path"); fi
  printf '%s %s\n' "$code" "$(cat "$out")"
  rm -f "$out"
}
http_code() { printf '%s' "${1%% *}"; }
# jf <biểu thức python trên d>: đọc phần body JSON (sau mã HTTP) từ stdin
jf() { python3 -c 'import sys,json; d=json.loads(sys.stdin.read().split(" ", 1)[1]); print(eval(sys.argv[1], {"d": d}))' "$1"; }
jv() { python3 -c 'import sys,json; d=json.loads(sys.stdin.read().split(" ", 1)[1]); print(*(eval(e, {"d": d}) for e in sys.argv[1:]))' "$@"; }
# vao <token> <văn bản> [nguồn]: đưa tin vào hàng chờ, in "<mã HTTP> <body>"
vao() {
  post /workflow/ai/boc-tach "$1" "$(python3 -c 'import sys,json; print(json.dumps({"van_ban": sys.argv[1], "nguon": sys.argv[2], "vao_hang_cho": True}, ensure_ascii=False))' "$2" "${3:-sms}")"
}
# gql <token> <vai> <query> [biến JSON]: in "<body JSON>" (lỗi GraphQL → ERR:<code>) qua jq_gql
gql() {
  local body
  body=$(python3 -c 'import sys,json; print(json.dumps({"query": sys.argv[1], "variables": json.loads(sys.argv[2])}))' "$3" "${4:-{\}}")
  curl -s -m 20 -K <(printf 'header = "Authorization: Bearer %s"\n' "$1") -H "X-Hasura-Role: $2" \
    -H 'Content-Type: application/json' -d "$body" "$GW/graphql"
}
jq_gql() {
  python3 -c '
import sys, json
d = json.load(sys.stdin)
if "errors" in d:
    print("ERR:" + d["errors"][0].get("extensions", {}).get("code", "?")); sys.exit()
print(eval(sys.argv[1], {"d": d}))' "$1"
}
sql() { timeout 60 docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -q -v ON_ERROR_STOP=1'; }
temporal_cli() { timeout 30 docker compose exec -T temporal sh -c "temporal $* --address temporal:7233"; }
dem_tin() { sql <<<"SELECT count(*) FROM cuu_tro.incidents WHERE reporter_phone LIKE '0900104%'"; }

reset() {
  local id
  for id in $(sql <<<"SELECT id FROM cuu_tro.incidents WHERE reporter_phone LIKE '0900104%'"); do
    temporal_cli workflow terminate -w "phan-cong-$id" --reason smoke-reset >/dev/null 2>&1 || true
  done
  # Vết duyệt trỏ tới tin (FK): xóa vết trước (superuser; không vai trò nào khác có DELETE)
  sql >/dev/null <<<"DELETE FROM cuu_tro.ai_intake_reviews WHERE raw_text LIKE '%0900 104%';
DELETE FROM cuu_tro.incidents WHERE reporter_phone LIKE '0900104%';" || true
}
reset
trap reset EXIT

D=$(get_token dieuphoi01); C=$(get_token cuuho01); T=$(get_token tinhnguyen01)
T_SUB=$(sub_of "$T")
Q_MUC='query($id: uuid!) { ai_intake_reviews_by_pk(id: $id) { status raw_text submitted_role ai_result } }'

# ---------- (1) Đưa vào hàng chờ ----------
TIN1='Cuu voi!! Nha toi o thon 2 xa Phu Dong, nuoc ngap toi mai, co 5 nguoi. Vi tri 21.0301, 105.8001. SDT 0900 104 001'
out=$(vao "$T" "$TIN1")
check "tinh-nguyen đưa tin vào hàng chờ → 200 + mã hàng chờ, cho_duyet" "200 cho_duyet" \
  "$(http_code "$out") $(jf 'd["hang_cho"]["trang_thai"]' <<<"$out")"
M1=$(jf 'd["hang_cho"]["id"]' <<<"$out")
check "đề xuất hợp lệ (đủ SĐT, tọa độ), không trùng" "True 0900104001" \
  "$(jv 'd["poka_yoke"]["hop_le"]' 'd["tin_keu_cuu"]["reporter_phone"]' <<<"$out")"
check "CSDL: dòng cho_duyet, người gửi = sub tinhnguyen01, vai tinh-nguyen, đề xuất khẩn cấp" \
  "cho_duyet|$T_SUB|tinh-nguyen|khan_cap|gia-lap" \
  "$(sql <<<"SELECT status||'|'||submitted_by||'|'||submitted_role||'|'||ai_urgency||'|'||ai_provider FROM cuu_tro.ai_intake_reviews WHERE id = '$M1'")"
check "đưa vào hàng chờ CHƯA tạo tin kêu cứu" 0 "$(dem_tin)"
check "cuu-ho không đưa tin vào hàng chờ → 403" 403 "$(http_code "$(vao "$C" "$TIN1")")"
check "vao_hang_cho sai kiểu → 422" 422 \
  "$(http_code "$(post /workflow/ai/boc-tach "$T" '{"van_ban": "cứu", "vao_hang_cho": "co"}')")"

# ---------- (2) Quyền đọc qua GraphQL ----------
check "dieu-phoi đọc văn bản gốc + đề xuất (SĐT trong đề xuất)" "cho_duyet True 0900104001" \
  "$(gql "$D" dieu-phoi "$Q_MUC" "{\"id\": \"$M1\"}" | jq_gql 'd["data"]["ai_intake_reviews_by_pk"]["status"], "0900 104 001" in d["data"]["ai_intake_reviews_by_pk"]["raw_text"], d["data"]["ai_intake_reviews_by_pk"]["ai_result"]["tin_keu_cuu"]["reporter_phone"]' | tr -d "(),'")"
check "tinh-nguyen thấy trạng thái tin mình gửi" "[{'id': '$M1', 'status': 'cho_duyet'}]" \
  "$(gql "$T" tinh-nguyen '{ ai_intake_reviews { id status } }' | jq_gql 'd["data"]["ai_intake_reviews"]')"
check "tinh-nguyen KHÔNG đọc được văn bản gốc" ERR:validation-failed \
  "$(gql "$T" tinh-nguyen '{ ai_intake_reviews { raw_text } }' | jq_gql 'd')"
check "tinh-nguyen KHÔNG đọc được đề xuất / người duyệt" ERR:validation-failed \
  "$(gql "$T" tinh-nguyen '{ ai_intake_reviews { ai_result reviewed_by_name } }' | jq_gql 'd')"
check "cuu-ho không thấy bảng hàng chờ" ERR:validation-failed \
  "$(gql "$C" cuu-ho '{ ai_intake_reviews { id } }' | jq_gql 'd')"
check "dieu-phoi không tự thêm dòng qua GraphQL (đề xuất do API tạo)" ERR:validation-failed \
  "$(gql "$D" dieu-phoi 'mutation { insert_ai_intake_reviews_one(object: {raw_text: "x"}) { id } }' | jq_gql 'd')"
check "dieu-phoi không tự đánh dấu đã duyệt qua GraphQL" ERR:validation-failed \
  "$(gql "$D" dieu-phoi "mutation { update_ai_intake_reviews_by_pk(pk_columns: {id: \"$M1\"}, _set: {status: \"da_duyet\"}) { id } }" | jq_gql 'd')"

# ---------- (3) Duyệt nguyên đề xuất ----------
check "duyệt không token → 401 (APISIX)" 401 "$(http_code "$(post "/workflow/hang-cho/$M1/duyet" - '{}')")"
check "tinh-nguyen duyệt → 403" 403 "$(http_code "$(post "/workflow/hang-cho/$M1/duyet" "$T" '{}')")"
check "cuu-ho duyệt → 403" 403 "$(http_code "$(post "/workflow/hang-cho/$M1/duyet" "$C" '{}')")"
check "cuu-ho hủy → 403" 403 "$(http_code "$(post "/workflow/hang-cho/$M1/huy" "$C" '{}')")"
out=$(post "/workflow/hang-cho/$M1/duyet" "$D" '{}')
check "dieu-phoi duyệt nguyên đề xuất → 201, không trường nào sửa, phân công tự động" "201 da_duyet [] tu_dong" \
  "$(http_code "$out") $(jv 'd["trang_thai"]' 'd["truong_da_sua"]' 'd["phan_cong"]' <<<"$out")"
INC1=$(jf 'd["incident_id"]' <<<"$out")
check "tin kêu cứu thật: đúng SĐT, 5 người, nguồn dien_thoai, created_by = người gửi" "0900104001|5|dien_thoai|$T_SUB" \
  "$(sql <<<"SELECT reporter_phone||'|'||people_count||'|'||source||'|'||created_by FROM cuu_tro.incidents WHERE id = '$INC1'")"
check "vết duyệt: da_duyet, người duyệt dieuphoi01, có thời điểm, gắn đúng tin, trường sửa {}" "da_duyet|dieuphoi01|true|true|{}" \
  "$(sql <<<"SELECT status||'|'||reviewed_by_name||'|'||(reviewed_at IS NOT NULL)||'|'||(incident_id = '$INC1')||'|'||edited_fields FROM cuu_tro.ai_intake_reviews WHERE id = '$M1'")"
check "tin từ hàng chờ vào outbox phân công tự động (#67)" 1 \
  "$(sql <<<"SELECT count(*) FROM cuu_tro.assignment_queue WHERE incident_id = '$INC1'")"
check "tinh-nguyen thấy tin mình chuyển (không có SĐT)" "$INC1" \
  "$(gql "$T" tinh-nguyen 'query($id: uuid!) { incidents_by_pk(id: $id) { id } }' "{\"id\": \"$INC1\"}" | jq_gql 'd["data"]["incidents_by_pk"]["id"]')"
out=$(post "/workflow/hang-cho/$M1/duyet" "$D" '{}')
check "duyệt lại → 409 da_xu_ly (kèm mã tin đã tạo)" "409 da_xu_ly $INC1" \
  "$(http_code "$out") $(jv 'd["detail"]["ma"]' 'd["detail"]["incident_id"]' <<<"$out")"
check "hủy mục đã duyệt → 409" 409 "$(http_code "$(post "/workflow/hang-cho/$M1/huy" "$D" '{"ly_do": "x"}')")"

# ---------- (4) Thiếu tọa độ: người duyệt bổ sung ----------
out=$(vao "$T" 'nha o xom Bau ngap sau, 3 nguoi mac ket, goi 0900 104 003' zalo)
M2=$(jf 'd["hang_cho"]["id"]' <<<"$out")
check "tin không có tọa độ vào hàng chờ, đề xuất báo thiếu lat/lon" "False ['lat', 'lon']" \
  "$(jv 'd["poka_yoke"]["hop_le"]' 'sorted(x["truong"] for x in d["poka_yoke"]["loi"])' <<<"$out")"
out=$(post "/workflow/hang-cho/$M2/duyet" "$D" '{}')
check "duyệt nguyên đề xuất thiếu tọa độ → 422 lat, lon" "422 ['lat', 'lon']" \
  "$(http_code "$out") $(jf 'sorted(x["truong"] for x in d["detail"]["loi"])' <<<"$out")"
check "422 không tạo tin, mục vẫn chờ duyệt" "1 cho_duyet" \
  "$(dem_tin) $(sql <<<"SELECT status FROM cuu_tro.ai_intake_reviews WHERE id = '$M2'")"
BODY2=$(gql "$D" dieu-phoi "$Q_MUC" "{\"id\": \"$M2\"}" | python3 -c '
import sys, json
t = json.load(sys.stdin)["data"]["ai_intake_reviews_by_pk"]["ai_result"]["tin_keu_cuu"]
t.update(lat=21.0401, lon=105.8101, people_count=4)
print(json.dumps({"tin_keu_cuu": t}, ensure_ascii=False))')
out=$(post "/workflow/hang-cho/$M2/duyet" "$D" "$BODY2")
check "duyệt sau khi chọn vị trí + đổi số người → 201, trường sửa lat, lon, people_count" "201 ['lat', 'lon', 'people_count']" \
  "$(http_code "$out") $(jf 'd["truong_da_sua"]' <<<"$out")"
check "vết ghi giá trị AI → người duyệt" "None 21.0401 3 4 mang_xa_hoi" \
  "$(sql <<<"SELECT edited_fields FROM cuu_tro.ai_intake_reviews WHERE id = '$M2'" | python3 -c '
import sys, json
e = json.load(sys.stdin)
print(e["lat"]["ai"], e["lat"]["nguoi"], e["people_count"]["ai"], e["people_count"]["nguoi"], end=" ")')$(sql <<<"SELECT final_body->>'source' FROM cuu_tro.ai_intake_reviews WHERE id = '$M2'")"

# ---------- (5) Tin trùng: hủy có lý do ----------
out=$(vao "$D" 'Lai la toi, nuoc len them, 5 nguoi, 21.0311, 105.8001, sdt 0900 104 001')
M3=$(jf 'd["hang_cho"]["id"]' <<<"$out")
check "đề xuất báo trùng tin vừa duyệt (cùng SĐT, ~110 m)" "False $INC1" \
  "$(jv 'd["poka_yoke"]["hop_le"]' 'd["poka_yoke"]["tin_trung"]["incident_id"]' <<<"$out")"
out=$(post "/workflow/hang-cho/$M3/duyet" "$D" '{}')
check "duyệt tin trùng → 409 tin_trung kèm mã tin đang mở" "409 tin_trung $INC1" \
  "$(http_code "$out") $(jv 'd["detail"]["ma"]' 'd["detail"]["incident_id"]' <<<"$out")"
check "409 trùng: mục vẫn chờ duyệt, không thêm tin" "cho_duyet 2" \
  "$(sql <<<"SELECT status FROM cuu_tro.ai_intake_reviews WHERE id = '$M3'") $(dem_tin)"
out=$(post "/workflow/hang-cho/$M3/huy" "$D" '{"ly_do": "Trùng tin kêu cứu đã có"}')
check "hủy có lý do → 200 da_huy" "200 da_huy" "$(http_code "$out") $(jf 'd["trang_thai"]' <<<"$out")"
check "vết hủy: lý do, người hủy, không gắn tin; không tạo tin" "da_huy|Trùng tin kêu cứu đã có|dieuphoi01|true 2" \
  "$(sql <<<"SELECT status||'|'||cancel_reason||'|'||reviewed_by_name||'|'||(incident_id IS NULL) FROM cuu_tro.ai_intake_reviews WHERE id = '$M3'") $(dem_tin)"
check "duyệt mục đã hủy → 409" 409 "$(http_code "$(post "/workflow/hang-cho/$M3/duyet" "$D" '{}')")"

# ---------- (6) Hai người duyệt cùng lúc ----------
out=$(vao "$T" 'Cuu, 2 nguoi bi ket tren mai, 21.0501, 105.8201, goi 0900 104 005')
M4=$(jf 'd["hang_cho"]["id"]' <<<"$out")
TMP=$(mktemp -d)
for i in 1 2; do
  curl -s -m 60 -o /dev/null -w '%{http_code}\n' -K <(printf 'header = "Authorization: Bearer %s"\n' "$D") -X POST \
    -H 'Content-Type: application/json' -d '{}' "$GW/workflow/hang-cho/$M4/duyet" >"$TMP/$i" &
done
wait
check "hai yêu cầu duyệt đồng thời → 1 × 201 + 1 × 409" "201 409" "$(sort "$TMP"/1 "$TMP"/2 | tr '\n' ' ' | sed 's/ $//')"
rm -rf "$TMP"
check "đúng 1 tin cho SĐT 0900104005" 1 \
  "$(sql <<<"SELECT count(*) FROM cuu_tro.incidents WHERE reporter_phone = '0900104005'")"

# ---------- (7) Vết không sửa được ----------
check "sửa vết đã duyệt (kể cả superuser) → trigger chặn" chan \
  "$(sql <<<"UPDATE cuu_tro.ai_intake_reviews SET reviewed_by_name = 'khac' WHERE id = '$M1'" >/dev/null 2>&1 && echo sua_duoc || echo chan)"
check "sửa đề xuất của AI → trigger chặn" chan \
  "$(sql <<<"UPDATE cuu_tro.ai_intake_reviews SET ai_result = '{\"de_xuat\": {}, \"tin_keu_cuu\": {}}' WHERE id = '$M4'" >/dev/null 2>&1 && echo sua_duoc || echo chan)"
check "tin có vết duyệt không xóa được (FK)" chan \
  "$(sql <<<"DELETE FROM cuu_tro.incidents WHERE id = '$INC1'" >/dev/null 2>&1 && echo xoa_duoc || echo chan)"

# ---------- (8) Đầu vào sai, WAF ----------
out=$(vao "$T" 'Can giup, 1 nguoi, 21.0601, 105.8301, goi 0900 104 006')
M5=$(jf 'd["hang_cho"]["id"]' <<<"$out")
check "lý do hủy > 500 ký tự → 422" 422 \
  "$(http_code "$(post "/workflow/hang-cho/$M5/huy" "$D" "{\"ly_do\": \"$(printf 'a%.0s' $(seq 1 501))\"}")")"
check "trường lạ trong body duyệt → 422" "422 ['x']" \
  "$(out=$(post "/workflow/hang-cho/$M5/duyet" "$D" '{"x": 1}'); echo "$(http_code "$out") $(jf '[e["truong"] for e in d["detail"]["loi"]]' <<<"$out")")"
check "mã không có → 404" 404 "$(http_code "$(post /workflow/hang-cho/00000000-0000-4000-8000-000000000000/duyet "$D" '{}')")"
check "mã sai dạng → 422" 422 "$(http_code "$(post /workflow/hang-cho/abc/huy "$D" '{}')")"
check "WAF bật trên route: XSS trong body duyệt → 403" 403 \
  "$(http_code "$(post "/workflow/hang-cho/$M5/duyet" "$D" '{"tin_keu_cuu": {"description": "<script>alert(1)</script>"}}')")"
check "mục vẫn chờ duyệt sau các yêu cầu sai" cho_duyet \
  "$(sql <<<"SELECT status FROM cuu_tro.ai_intake_reviews WHERE id = '$M5'")"

# ---------- (9) Log, web ----------
check "log cuu-tro-api và apisix không có SĐT hay nội dung tin" 0 \
  "$(docker compose logs --no-log-prefix cuu-tro-api apisix 2>&1 | grep -c '0900104\|0900 104\|Phu Dong\|xom Bau' || true)"
check "web điều phối /hang-cho mở được qua gateway" 200 \
  "$(curl -s -m 20 -o /dev/null -w '%{http_code}' "$GW/hang-cho")"

if [ "$fail" -eq 0 ]; then echo "OK: smoke hàng chờ duyệt HITL đạt"; else echo "CÓ LỖI: xem các dòng FAIL"; exit 1; fi
