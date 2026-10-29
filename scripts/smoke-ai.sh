#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử AI bóc tách tin kêu cứu POST /workflow/ai/boc-tach (#102), gọi THẬT qua APISIX bằng token Keycloak
# của user mẫu, với nhà cung cấp đang cấu hình (mặc định gia-lap: bộ luật, không cần mô hình; CI và smoke
# không kéo Qwen2.5 7B):
# (1) không token → 401 (APISIX); cuu-ho → 403 (API);
# (2) tin SMS không dấu có SĐT + tọa độ → 200: đề xuất đúng trường của /keu-cuu (SĐT chuẩn hóa, tọa độ, số
#     người, mức khẩn cấp, nhu cầu), Poka-yoke hợp lệ, mô tả che SĐT, KHÔNG tạo tin kêu cứu nào;
# (3) tin không có tọa độ → Poka-yoke báo thiếu lat/lon (người duyệt phải chọn vị trí trên bản đồ);
# (4) kiểm trước tin trùng: tạo tin thật qua /workflow/keu-cuu rồi bóc tách tin cùng SĐT cách ~110 m →
#     poka_yoke.tin_trung trỏ đúng tin đó (hàm CSDL incident_find_duplicate, migration 0013);
# (5) đầu vào sai → 422 theo trường; body > 8 KiB → 413; WAF vẫn bật (XSS → 403);
# (6) log cuu-tro-api và APISIX không có SĐT hay nội dung tin;
# (7) cấu hình compose: Ollama ở profile ai, image ghim phiên bản, không mở cổng ra máy host; mô hình mặc
#     định qwen2.5:7b; dịch vụ ollama không chạy khi chưa bật profile ai;
# (8) giới hạn tần suất riêng của route /workflow/ai/* → 429 (chạy CUỐI).
# SĐT giả 0900102xxx, tọa độ giả (Hà Nội) xa đội mẫu; tin thử bị xóa khi kết thúc.
# Dùng: make up && make seed && bash scripts/smoke-ai.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

KC="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-disaster}"
GW="http://localhost:${APISIX_PORT:-9080}"
LIMIT="${GW_AI_RATE_LIMIT_COUNT:-30}"
PROVIDER="${LLM_PROVIDER:-gia-lap}"
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
# post <đường dẫn> <token|-> <body>: in "<mã HTTP> <body>"
post() {
  local path=$1 tok=$2 body=$3 out code
  out=$(mktemp)
  local args=(-s -o "$out" -w '%{http_code}' -X POST -H 'Content-Type: application/json' --data-binary "$body")
  if [ "$tok" = - ]; then code=$(curl "${args[@]}" "$GW$path")
  else code=$(curl -K <(printf 'header = "Authorization: Bearer %s"\n' "$tok") "${args[@]}" "$GW$path"); fi
  printf '%s %s\n' "$code" "$(cat "$out")"
  rm -f "$out"
}
bt() { post /workflow/ai/boc-tach "$1" "$2"; }
http_code() { printf '%s' "${1%% *}"; }
# jf <biểu thức python trên d>: đọc phần body JSON (sau mã HTTP) từ stdin
jf() { python3 -c 'import sys,json; d=json.loads(sys.stdin.read().split(" ", 1)[1]); print(eval(sys.argv[1], {"d": d}))' "$1"; }
# jv <biểu thức>…: như jf, nhiều biểu thức, in cách nhau một dấu cách
jv() { python3 -c 'import sys,json; d=json.loads(sys.stdin.read().split(" ", 1)[1]); print(*(eval(e, {"d": d}) for e in sys.argv[1:]))' "$@"; }
# vb <văn bản> [nguồn]: body JSON của /ai/boc-tach
vb() { python3 -c 'import sys,json; print(json.dumps({"van_ban": sys.argv[1], "nguon": sys.argv[2]}, ensure_ascii=False))' "$1" "${2:-sms}"; }
sql() { docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -q -v ON_ERROR_STOP=1'; }
temporal_cli() { docker compose exec -T temporal sh -c "temporal $* --address temporal:7233"; }
dem_tin() { sql <<<"SELECT count(*) FROM cuu_tro.incidents WHERE reporter_phone LIKE '0900102%'"; }

reset() {
  local id
  for id in $(sql <<<"SELECT id FROM cuu_tro.incidents WHERE reporter_phone LIKE '0900102%'"); do
    temporal_cli workflow terminate -w "phan-cong-$id" --reason smoke-reset >/dev/null 2>&1 || true
  done
  sql >/dev/null <<<"DELETE FROM cuu_tro.incidents WHERE reporter_phone LIKE '0900102%';" || true
}
reset
trap reset EXIT

D=$(get_token dieuphoi01); C=$(get_token cuuho01); T=$(get_token tinhnguyen01)

# ---------- (1) Quyền ----------
TIN='Cuu voi!! Nha toi o thon 3 xa Phu Minh, nuoc ngap toi mai, co 5 nguoi trong do 2 tre em. Vi tri 20.9612, 105.7488. SDT 0900 102 001'
check "không token → 401 (APISIX)" 401 "$(http_code "$(bt - "$(vb "$TIN")")")"
check "cuu-ho → 403 (chỉ dieu-phoi, tinh-nguyen)" 403 "$(http_code "$(bt "$C" "$(vb "$TIN")")")"

# ---------- (2) Bóc tách tin hợp lệ ----------
truoc=$(dem_tin)
out=$(bt "$T" "$(vb "$TIN")")
check "tinh-nguyen bóc tách tin SMS → 200" 200 "$(http_code "$out")"
check "nhà cung cấp đúng LLM_PROVIDER" "$PROVIDER" "$(jf 'd["ai"]["nha_cung_cap"]' <<<"$out")"
check "SĐT chuẩn hóa, tọa độ lấy từ tin" "0900102001 20.9612 105.7488" \
  "$(jv 'd["tin_keu_cuu"]["reporter_phone"]' 'd["tin_keu_cuu"]["lat"]' 'd["tin_keu_cuu"]["lon"]' <<<"$out")"
check "số người, mức khẩn cấp (ngập tới mái → khan_cap), nhu cầu cứu người" "5 khan_cap True" \
  "$(jv 'd["tin_keu_cuu"]["people_count"]' 'd["tin_keu_cuu"]["urgency"]' '"cuu_nguoi" in d["de_xuat"]["nhu_cau"]' <<<"$out")"
check "địa chỉ bóc từ tin, nguồn sms → dien_thoai" "True dien_thoai" \
  "$(jv 'd["tin_keu_cuu"]["address_text"].startswith("thon 3")' 'd["tin_keu_cuu"]["source"]' <<<"$out")"
check "Poka-yoke hợp lệ, không trùng" "True [] None" \
  "$(jv 'd["poka_yoke"]["hop_le"]' 'd["poka_yoke"]["loi"]' 'd["poka_yoke"]["tin_trung"]' <<<"$out")"
check "mô tả che SĐT ([SĐT])" "True" "$(jf '"0900" not in d["tin_keu_cuu"]["description"] and "[SĐT]" in d["tin_keu_cuu"]["description"]' <<<"$out")"
check "bóc tách KHÔNG tạo tin kêu cứu (người duyệt quyết định)" "$truoc" "$(dem_tin)"
out=$(bt "$D" "$(vb 'Tôi là Trần Thị Mai ở tổ 4 phường Phúc La, có 2 cụ già bị kẹt, cần thuốc. Gọi +84 900 102 002. Vị trí 20.9701, 105.7799' zalo)")
check "dieu-phoi bóc tách tin Zalo có dấu → tên, địa chỉ, mức cao, nguồn mang_xa_hoi" \
  "200 Trần Thị Mai tổ 4 phường Phúc La cao mang_xa_hoi" \
  "$(http_code "$out") $(jv 'd["tin_keu_cuu"]["reporter_name"]' 'd["tin_keu_cuu"]["address_text"]' 'd["tin_keu_cuu"]["urgency"]' 'd["tin_keu_cuu"]["source"]' <<<"$out")"

# ---------- (3) Thiếu tọa độ ----------
out=$(bt "$T" "$(vb 'nha o xom Bau ngap sau, 3 nguoi mac ket, goi 0900102003')")
check "tin không có tọa độ → Poka-yoke báo thiếu lat, lon" "200 False ['lat', 'lon']" \
  "$(http_code "$out") $(jv 'd["poka_yoke"]["hop_le"]' 'sorted(x["truong"] for x in d["poka_yoke"]["loi"])' <<<"$out")"

# ---------- (4) Kiểm trước tin trùng ----------
out=$(post /workflow/keu-cuu "$T" '{"lat": 20.9612, "lon": 105.7488, "reporter_phone": "0900102001", "description": "[smoke #102] tin gốc", "urgency": "cao", "people_count": 5}')
check "tạo tin thật qua /workflow/keu-cuu → 201" 201 "$(http_code "$out")"
ID=$(jf 'd["id"]' <<<"$out")
out=$(bt "$T" "$(vb 'Lại là tôi, nước lên thêm, 5 người, 20.9622, 105.7488, sđt 0900102001')")
check "cùng SĐT cách ~110 m → tin_trung trỏ đúng tin đang mở" "False $ID True" \
  "$(jv 'd["poka_yoke"]["hop_le"]' 'd["poka_yoke"]["tin_trung"]["incident_id"]' '100 <= d["poka_yoke"]["tin_trung"]["khoang_cach_m"] <= 120' <<<"$out")"
out=$(bt "$T" "$(vb 'Nhà khác, 2 người, 20.9622, 105.7488, sđt 0900102009')")
check "khác SĐT cùng chỗ → không trùng" "True None" \
  "$(jv 'd["poka_yoke"]["hop_le"]' 'd["poka_yoke"]["tin_trung"]' <<<"$out")"
check "kiểm trùng không tạo thêm tin (chỉ 1 tin của 0900102001)" 1 \
  "$(sql <<<"SELECT count(*) FROM cuu_tro.incidents WHERE reporter_phone = '0900102001'")"

# ---------- (5) Đầu vào sai, WAF ----------
out=$(bt "$T" '{"van_ban": "   ", "nguon": "fax", "lat": 1}')
check "đầu vào sai → 422 theo trường (van_ban, nguon, trường lạ)" "422 ['lat', 'nguon', 'van_ban']" \
  "$(http_code "$out") $(jf 'sorted(x["truong"] for x in d["detail"]["loi"])' <<<"$out")"
check "văn bản > 2000 ký tự → 422" 422 \
  "$(http_code "$(bt "$T" "$(vb "$(printf 'a%.0s' $(seq 1 2001))")")")"
check "body > 8 KiB → 413" 413 \
  "$(http_code "$(bt "$T" "{\"van_ban\": \"$(printf 'a%.0s' $(seq 1 9000))\"}")")"
check "WAF vẫn bật trên route: XSS trong văn bản → 403" 403 \
  "$(http_code "$(bt "$T" '{"van_ban": "<script>alert(1)</script> cứu"}')")"

# ---------- (6) Log ----------
check "log cuu-tro-api và apisix không có SĐT hay nội dung tin" 0 \
  "$(docker compose logs --no-log-prefix cuu-tro-api apisix 2>&1 | grep -c '0900102\|900 102\|Phu Minh\|Phúc La' || true)"

# ---------- (7) Cấu hình compose profile ai ----------
cfg=$(docker compose --profile ai config --format json)
check "ollama ở profile ai, image ghim phiên bản (không latest), không mở cổng ra host" \
  "['ai'] True True" \
  "$(python3 -c 'import sys,json; s=json.load(sys.stdin)["services"]["ollama"]; i=s["image"]; print(s.get("profiles"), i.startswith("ollama/ollama:") and not i.endswith(":latest"), not s.get("ports"))' <<<"$cfg")"
check "mô hình mặc định của ollama-pull: qwen2.5:7b (Apache-2.0)" "${LLM_MODEL:-qwen2.5:7b}" \
  "$(python3 -c 'import sys,json; print(json.load(sys.stdin)["services"]["ollama-pull"]["environment"]["LLM_MODEL"])' <<<"$cfg")"
if [ "$PROVIDER" = gia-lap ]; then
  check "chế độ gia-lap: dịch vụ ollama không chạy (không cần mô hình)" 0 \
    "$(docker compose ps -q ollama 2>/dev/null | grep -c . || true)"
fi

# ---------- (8) Giới hạn tần suất riêng (chạy cuối) ----------
codes=""
for _ in $(seq 1 $((LIMIT + 2))); do
  c=$(http_code "$(bt "$T" '{}')")
  codes="$codes $c"
  [ "$c" = 429 ] && break
done
check "route /workflow/ai/* có giới hạn riêng (≤ $LIMIT request/cửa sổ) → 429" 429 "${codes##* }"
check "giới hạn riêng của route là $LIMIT (header X-RateLimit-Limit)" "$LIMIT" \
  "$(curl -s -o /dev/null -D - -K <(printf 'header = "Authorization: Bearer %s"\n' "$T") -X POST \
       -H 'Content-Type: application/json' -d '{}' "$GW/workflow/ai/boc-tach" \
     | tr -d '\r' | awk -F': ' 'tolower($1) == "x-ratelimit-limit" {print $2}')"

if [ "$fail" -eq 0 ]; then echo "OK: smoke AI bóc tách đạt"; else echo "CÓ LỖI: xem các dòng FAIL"; exit 1; fi
