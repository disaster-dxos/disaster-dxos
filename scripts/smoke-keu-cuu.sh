#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử API tiếp nhận tin kêu cứu POST /workflow/keu-cuu (#66), gọi THẬT qua APISIX bằng token Keycloak
# của user mẫu, kiểm kết quả trong PostgreSQL, Hasura (/graphql) và subscription bản đồ (#60):
# (1) không token → 401 (APISIX); cuu-ho → 403 (API);
# (2) Poka-yoke → 422 kèm lỗi theo trường, tiếng Việt: thiếu tọa độ, vĩ độ ngoài khoảng, ngoài vùng phục vụ,
#     SĐT sai dạng; không tạo tin nào;
# (3) tinh-nguyen tạo tin hợp lệ → 201: CSDL có tin tiep_nhan, SĐT đã chuẩn hóa (+84 → 0), created_by = sub,
#     vào hàng đợi phân công tự động (#67); dieu-phoi thấy qua /graphql; subscription bản đồ nhận tin mới;
# (4) chặn trùng: cùng SĐT cách ~150 m → 409 kèm mã tin đang mở; khác SĐT cùng chỗ → 201; cùng SĐT cách
#     ~280 m → 201;
# (5) GỬI ĐỒNG THỜI: 5 request cùng SĐT, cùng lúc qua gateway → đúng 1 × 201, 4 × 409 trỏ về tin đó;
#     hai phiên PostgreSQL (role cuu_tro_app): phiên B phải CHỜ khóa advisory của phiên A (chưa commit) rồi
#     bị chặn 23505 kèm id tin của A, thay vì cùng lọt;
# (6) WAF vẫn bật trên route (XSS trong mô tả → 403); log cuu-tro-api và APISIX không có SĐT;
# (7) giới hạn tần suất riêng của route → 429 (chạy CUỐI: sau đó route bị chặn GW_RATE_LIMIT_WINDOW giây).
# Tin thử đặt ở tọa độ giả xa đội mẫu (không đội nào trong bán kính phân công), SĐT giả 0900066xxx;
# workflow phân công tự khởi chạy của tin thử bị dừng và tin bị xóa khi kết thúc.
# Dùng: make up && make seed && bash scripts/smoke-keu-cuu.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

KC="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-disaster}"
GW="http://localhost:${APISIX_PORT:-9080}"
WS="ws://localhost:${APISIX_PORT:-9080}/graphql"
ORIGIN="${GATEWAY_PUBLIC_URL:-http://localhost:9080}"
LIMIT="${GW_KEU_CUU_RATE_LIMIT_COUNT:-20}"
# Tọa độ giả (Hà Nội), cách đội mẫu (Quảng Nam) hàng trăm km
LAT=20.9500
LNG=105.7500
fail=0
TMP=$(mktemp -d)

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
# kc <token|-> <body JSON>: POST /workflow/keu-cuu, in "<mã HTTP> <body>"
kc() {
  local tok=$1 body=$2 out code
  out=$(mktemp)
  local args=(-s -o "$out" -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d "$body")
  if [ "$tok" = - ]; then code=$(curl "${args[@]}" "$GW/workflow/keu-cuu")
  else code=$(curl -K <(printf 'header = "Authorization: Bearer %s"\n' "$tok") "${args[@]}" "$GW/workflow/keu-cuu"); fi
  printf '%s %s\n' "$code" "$(cat "$out")"
  rm -f "$out"
}
http_code() { printf '%s' "${1%% *}"; }
# jf <biểu thức python trên d>: đọc phần body JSON (sau mã HTTP) từ stdin
jf() { python3 -c 'import sys,json; d=json.loads(sys.stdin.read().split(" ", 1)[1]); print(eval(sys.argv[1], {"d": d}))' "$1"; }
# tin <SĐT> <vĩ độ> <kinh độ> [urgency]: body JSON tin kêu cứu
tin() { printf '{"lat": %s, "lon": %s, "reporter_phone": "%s", "description": "[smoke #66] nuoc ngap, can ho tro", "urgency": "%s", "people_count": 2}' "$2" "$3" "$1" "${4:-cao}"; }
sql() { docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -q -v ON_ERROR_STOP=1'; }
temporal_cli() { docker compose exec -T temporal sh -c "temporal $* --address temporal:7233"; }
doi_file() { local _; for _ in $(seq 1 $((${2:-10} * 10))); do [ -s "$1" ] && return 0; sleep 0.1; done; return 1; }

reset() {
  local id
  for id in $(sql <<<"SELECT id FROM cuu_tro.incidents WHERE reporter_phone LIKE '0900066%'"); do
    temporal_cli workflow terminate -w "phan-cong-$id" --reason smoke-reset >/dev/null 2>&1 || true
  done
  sql >/dev/null <<<"DELETE FROM cuu_tro.incidents WHERE reporter_phone LIKE '0900066%';" || true
}
reset
trap 'reset; rm -rf "$TMP"' EXIT

D=$(get_token dieuphoi01); C=$(get_token cuuho01); T=$(get_token tinhnguyen01)
T_SUB=$(sub_of "$T")
dem_tin() { sql <<<"SELECT count(*) FROM cuu_tro.incidents WHERE reporter_phone LIKE '0900066%'"; }

# ---------- (1) Quyền ----------
check "không token (APISIX chặn)" 401 "$(http_code "$(kc - "$(tin 0900066001 $LAT $LNG)")")"
check "cuu-ho không được tạo tin" 403 "$(http_code "$(kc "$C" "$(tin 0900066001 $LAT $LNG)")")"

# ---------- (2) Poka-yoke 422 ----------
out=$(kc "$T" '{"reporter_phone": "0900066001", "description": "[smoke #66] khong co toa do"}')
check "thiếu tọa độ → 422, lỗi ở lat + lon, thông báo tiếng Việt" "422 du_lieu_khong_hop_le lat,lon True" \
  "$(http_code "$out") $(jf 'd["detail"]["ma"] + " " + ",".join(sorted(x["truong"] for x in d["detail"]["loi"])) + " " + str("bắt buộc có vị trí" in d["detail"]["loi"][0]["thong_bao"])' <<<"$out")"
out=$(kc "$T" "$(tin 0900066001 95 $LNG)")
check "vĩ độ 95 → 422 ở lat" "422 lat" "$(http_code "$out") $(jf '",".join(x["truong"] for x in d["detail"]["loi"])' <<<"$out")"
out=$(kc "$T" "$(tin 0900066001 48.85 2.35)")
check "ngoài vùng phục vụ (Paris) → 422" "422 True" "$(http_code "$out") $(jf 'str("ngoài vùng phục vụ" in d["detail"]["loi"][0]["thong_bao"])' <<<"$out")"
out=$(kc "$T" "$(tin 12345 $LAT $LNG)")
check "SĐT sai dạng → 422 ở reporter_phone, không lặp lại số đã nhập" "422 reporter_phone False" \
  "$(http_code "$out") $(jf '",".join(x["truong"] for x in d["detail"]["loi"]) + " " + str("12345" in str(d))' <<<"$out")"
check "422 không tạo tin nào" 0 "$(dem_tin)"

# ---------- (3) Tạo tin hợp lệ, hiện trên bản đồ ----------
sub_ws() { GRAPHQL_TOKEN="$D" python3 scripts/graphql-ws.py "$WS" --origin "$ORIGIN" --vai dieu-phoi "$@"; }
sub_ws --cho-moi --giay 12 --san-sang "$TMP/s-dp" >"$TMP/dp" &
doi_file "$TMP/s-dp" || echo "(subscription chưa sẵn sàng)"
out=$(kc "$T" "$(tin '+84 900 066 001' $LAT $LNG khan_cap)")
ID1=$(jf 'd.get("id")' <<<"$out" 2>/dev/null || echo "")
check "tinh-nguyen tạo tin hợp lệ (SĐT +84) → 201 tiep_nhan khan_cap, không trả SĐT" "201 tiep_nhan khan_cap tu_dong False" \
  "$(http_code "$out") $(jf 'd["status"] + " " + d["urgency"] + " " + d["phan_cong"] + " " + str("0900066001" in str(d))' <<<"$out")"
check "CSDL: SĐT đã chuẩn hóa, created_by = sub token, nguồn app, vị trí đúng" "0900066001|$T_SUB|app|$LNG|$LAT" \
  "$(sql <<<"SELECT reporter_phone || '|' || created_by || '|' || source || '|' || round(ST_X(location::geometry)::numeric, 4) || '|' || round(ST_Y(location::geometry)::numeric, 4) FROM cuu_tro.incidents WHERE id = '$ID1'")"
check "outbox: tin vào hàng đợi phân công tự động (#67)" 1 \
  "$(sql <<<"SELECT count(*) FROM cuu_tro.assignment_queue WHERE incident_id = '$ID1'")"
gql=$(curl -s -K <(printf 'header = "Authorization: Bearer %s"\n' "$D") -H 'Content-Type: application/json' -H 'X-Hasura-Role: dieu-phoi' \
  -d "{\"query\": \"{ incidents_by_pk(id: \\\"$ID1\\\") { id status urgency } }\"}" "$GW/graphql")
check "dieu-phoi thấy tin qua /graphql" "$ID1 tiep_nhan" \
  "$(python3 -c 'import sys,json; t=json.load(sys.stdin)["data"]["incidents_by_pk"] or {}; print(t.get("id"), t.get("status"))' <<<"$gql")"
wait
check "subscription bản đồ (dieu-phoi) nhận tin vừa tạo qua API" "$ID1" \
  "$(python3 -c 'import sys,json; print((json.load(sys.stdin).get("moi") or {}).get("id"))' <"$TMP/dp")"

# ---------- (4) Chặn trùng ----------
out=$(kc "$T" "$(tin 0900066001 20.95135 $LNG)")
check "cùng SĐT, cách ~150 m, tin còn mở → 409 kèm mã tin đang mở" "409 tin_trung $ID1 200 True" \
  "$(http_code "$out") $(jf 'd["detail"]["ma"] + " " + d["detail"]["incident_id"] + " " + str(d["detail"]["ban_kinh_m"]) + " " + str(140 <= d["detail"]["khoang_cach_m"] <= 160)' <<<"$out")"
check "409 có thông báo tiếng Việt" True "$(jf 'str("Không tạo tin mới" in d["detail"]["thong_bao"])' <<<"$out")"
check "khác SĐT, cùng chỗ → 201" 201 "$(http_code "$(kc "$T" "$(tin 0900066002 $LAT $LNG)")")"
check "cùng SĐT, cách ~280 m (ngoài 200 m) → 201" 201 "$(http_code "$(kc "$T" "$(tin 0900066001 20.9525 $LNG)")")"
check "CSDL: 3 tin (tin trùng không được tạo)" 3 "$(dem_tin)"

# ---------- (5) Gửi đồng thời ----------
for i in 1 2 3 4 5; do
  kc "$D" "$(tin 0900066020 "20.960$i" $LNG)" >"$TMP/dt$i" &
done
wait
ma=$(for i in 1 2 3 4 5; do http_code "$(cat "$TMP/dt$i")"; echo; done | sort | uniq -c | awk '{printf "%s×%s ", $2, $1}')
check "5 request đồng thời cùng SĐT qua gateway → 1 tạo, 4 trùng" "201×1 409×4 " "$ma"
ID_DT=$(sql <<<"SELECT id FROM cuu_tro.incidents WHERE reporter_phone = '0900066020'")
check "CSDL: đúng 1 tin của SĐT gửi đồng thời; mọi 409 trỏ về tin đó" "1 $ID_DT" \
  "$(sql <<<"SELECT count(*) FROM cuu_tro.incidents WHERE reporter_phone = '0900066020'") $(for i in 1 2 3 4 5; do o=$(cat "$TMP/dt$i"); [ "$(http_code "$o")" = 409 ] && jf 'd["detail"]["incident_id"]' <<<"$o"; done | sort -u | tr '\n' ' ' | sed 's/ $//')"

# Hai phiên PostgreSQL bằng role của API: A giữ transaction 3 giây chưa commit, B gửi trong lúc đó
ins="SET ROLE cuu_tro_app; INSERT INTO cuu_tro.incidents (description, location, reporter_phone, urgency, source, created_by)
     VALUES ('[smoke #66] hai phien', ST_SetSRID(ST_MakePoint($LNG, 20.97), 4326)::geography, '0900066030', 'cao', 'app', 'smoke-66')"
sql >"$TMP/a" 2>&1 <<<"BEGIN; $ins RETURNING id; SELECT pg_sleep(3); COMMIT;" &
sleep 1
t0=$(python3 -c 'import time; print(time.time())')
sql >"$TMP/b" 2>&1 <<<"$ins;" && b_ok=lot || b_ok=chan
cho=$(python3 -c 'import sys,time; print(time.time() - float(sys.argv[1]) >= 1.5)' "$t0")
wait
ID_A=$(grep -Eo '^[0-9a-f-]{36}$' "$TMP/a" | head -1 || true)
check "hai phiên CSDL: B chờ khóa của A rồi bị chặn, DETAIL trỏ về tin của A" "chan True True" \
  "$b_ok $cho $(grep -q "incident_id=$ID_A" "$TMP/b" && [ -n "$ID_A" ] && echo True || echo False)"
check "CSDL: chỉ tin của phiên A được tạo" 1 "$(sql <<<"SELECT count(*) FROM cuu_tro.incidents WHERE reporter_phone = '0900066030'")"

# ---------- (6) WAF, log ----------
out=$(kc "$T" '{"lat": 20.98, "lon": 105.75, "reporter_phone": "0900066040", "description": "<script>alert(1)</script>"}')
check "WAF vẫn bật trên route: XSS trong mô tả → 403" 403 "$(http_code "$out")"
check "log cuu-tro-api và apisix không có SĐT người báo" 0 \
  "$(docker compose logs --no-log-prefix cuu-tro-api apisix 2>&1 | grep -c '0900066\|900 066' || true)"

# ---------- (7) Giới hạn tần suất riêng (chạy cuối) ----------
codes=""
for _ in $(seq 1 $((LIMIT + 2))); do
  c=$(http_code "$(kc "$T" '{}')")
  codes="$codes $c"
  [ "$c" = 429 ] && break
done
check "route /workflow/keu-cuu có giới hạn riêng (≤ $LIMIT request/cửa sổ) → 429" 429 "${codes##* }"
check "giới hạn riêng của route là $LIMIT (header X-RateLimit-Limit)" "$LIMIT" \
  "$(curl -s -o /dev/null -D - -K <(printf 'header = "Authorization: Bearer %s"\n' "$T") -X POST \
       -H 'Content-Type: application/json' -d '{}' "$GW/workflow/keu-cuu" \
     | tr -d '\r' | awk -F': ' 'tolower($1) == "x-ratelimit-limit" {print $2}')"

if [ "$fail" -eq 0 ]; then echo "OK: smoke API kêu cứu đạt"; else echo "CÓ LỖI: xem các dòng FAIL"; exit 1; fi
