#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử bản đồ tin kêu cứu realtime (#60): GraphQL subscription của Hasura đi THẬT qua APISIX
# (WebSocket ws://<gateway>/graphql, giao thức graphql-transport-ws, JWT trong connection_init như web):
# (1) gateway: HTTP /graphql vẫn bắt buộc JWT (401); bắt tay WebSocket qua route graphql-ws, WAF vẫn chặn
#     XSS trong tham số bắt tay (403);
# (2) từ chối: không token → Hasura coi là anonymous, không có bảng incidents (validation-failed); JWT sai
#     chữ ký → Hasura đóng kết nối; tinh-nguyen xin vai dieu-phoi → bị từ chối; tinh-nguyen xin cột
#     reporter_phone → validation-failed;
# (3) dieu-phoi: kết quả chỉ có 5 trường của bản đồ; tạo tin thử qua /graphql → subscription nhận tin
#     mới trong 2 giây (tiêu chí #60), đúng tọa độ, mức khẩn, trạng thái;
# (4) quyền theo hàng qua subscription: tinh-nguyen, cuu-ho không nhận tin của người khác/đội khác;
#     tinh-nguyen nhận tin chính mình tạo, không có SĐT.
# Tin thử có mô tả "[smoke #60]", đặt ngoài bán kính mọi đội seed; xóa (kèm dừng workflow phân công) khi xong.
# Dùng: make up && bash scripts/smoke-ban-do.sh   (cần python3 trên máy host, không cần thư viện ngoài)
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

KC="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-disaster}"
GW="http://localhost:${APISIX_PORT:-9080}"
WS="ws://localhost:${APISIX_PORT:-9080}/graphql"
ORIGIN="${GATEWAY_PUBLIC_URL:-http://localhost:9080}"
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
jf() { python3 -c 'import sys,json; d=json.loads(sys.stdin.read()); print(eval(sys.argv[1], {"d": d}))' "$1"; }
# sub <token|-> [tham số graphql-ws.py]: subscription qua gateway, JWT qua biến môi trường (không lên dòng lệnh)
sub() { local t=$1; shift; [ "$t" = - ] && t=''; GRAPHQL_TOKEN="$t" python3 scripts/graphql-ws.py "$WS" --origin "$ORIGIN" "$@"; }
sql() { docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -q -v ON_ERROR_STOP=1'; }
temporal_cli() { docker compose exec -T temporal sh -c "temporal $* --address temporal:7233"; }
# tao_tin <token> <vai> <SĐT> <kinh độ> <vĩ độ> <urgency>: tạo tin qua HTTP /graphql, in id (hoặc body lỗi)
tao_tin() {
  local body out
  # shellcheck disable=SC2016 # $o là biến GraphQL
  body=$(python3 -c 'import json,sys; print(json.dumps({"query": "mutation($o: incidents_insert_input!) { insert_incidents_one(object: $o) { id } }", "variables": {"o": {"description": "[smoke #60] nuoc ngap, can thuyen", "location": {"type": "Point", "coordinates": [float(sys.argv[2]), float(sys.argv[3])]}, "urgency": sys.argv[4], "people_count": 2, "reporter_phone": sys.argv[1], "source": "web"}}}))' "$3" "$4" "$5" "$6")
  out=$(curl -s -K <(printf 'header = "Authorization: Bearer %s"\n' "$1") -H 'Content-Type: application/json' -H "X-Hasura-Role: $2" -d "$body" "$GW/graphql")
  python3 -c 'import sys,json; print(json.load(sys.stdin)["data"]["insert_incidents_one"]["id"])' <<<"$out" 2>/dev/null || echo "$out"
}
# doi_file <file> [giây]: chờ client nền nhận xong kết quả đầu tiên
doi_file() { local _; for _ in $(seq 1 $((${2:-10} * 10))); do [ -s "$1" ] && return 0; sleep 0.1; done; return 1; }

TAO=()
reset() {
  local id
  for id in "${TAO[@]}"; do
    temporal_cli workflow terminate -w "phan-cong-$id" --reason smoke-reset >/dev/null 2>&1 || true
    sql >/dev/null <<<"DELETE FROM cuu_tro.incidents WHERE id = '$id';" || true
  done
  rm -rf "$TMP"
}
trap reset EXIT

D=$(get_token dieuphoi01); C=$(get_token cuuho01); T=$(get_token tinhnguyen01)
# Ngoài bán kính mọi đội seed (~55 km, giống smoke-hasura/smoke-realtime): tin mới không làm đội seed bị giao việc
LNG=107.6035; LAT=15.6502

# ---------- (1) Gateway ----------
check "HTTP POST /graphql không token → APISIX 401" 401 \
  "$(curl -s -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' -d '{"query":"{ incidents { id } }"}' "$GW/graphql")"
check "HTTP GET /graphql không Upgrade, không token → 401 (không lọt sang route WebSocket)" 401 \
  "$(curl -s -o /dev/null -w '%{http_code}' "$GW/graphql?query=%7Bincidents%7Bid%7D%7D")"
check "bắt tay WebSocket có XSS trong tham số → WAF 403" "loi_http 403" \
  "$(GRAPHQL_TOKEN="$D" python3 scripts/graphql-ws.py "$WS?q=%3Cscript%3Ealert(1)%3C%2Fscript%3E" --origin "$ORIGIN" | jf 'd["ket_noi"] + " " + str(d.get("ma"))')"

# ---------- (2) Từ chối ----------
check "WebSocket không token: Hasura coi là anonymous, subscription incidents bị từ chối" "ok validation-failed" \
  "$(sub - | jf 'd["ket_noi"] + " " + ",".join(d.get("ma_loi") or ["nhan-duoc-du-lieu"])')"
SAI="${D%.*}.$(printf 'chu-ky-gia-mao-khong-hop-le' | base64 | tr '+/' '-_' | tr -d '=')"
check "WebSocket JWT sai chữ ký: Hasura đóng kết nối" tu_choi "$(sub "$SAI" --vai dieu-phoi | jf 'd["ket_noi"]')"
# Hasura đóng kết nối (4400) hoặc trả lỗi access-denied cho subscription tùy phiên bản: cả hai đều là từ chối
check "WebSocket tinh-nguyen xin vai dieu-phoi → bị từ chối" tu_choi \
  "$(sub "$T" --vai dieu-phoi | jf '"tu_choi" if d["ket_noi"] == "tu_choi" or "access-denied" in (d.get("ma_loi") or []) else d')"
check "WebSocket tinh-nguyen xin cột reporter_phone → validation-failed" validation-failed \
  "$(sub "$T" --vai tinh-nguyen --query 'subscription { incidents { id reporter_phone } }' | jf '",".join(d.get("ma_loi") or ["nhan-duoc-du-lieu"])')"

# ---------- (3) dieu-phoi nhận tin mới trong 2 giây ----------
r=$(sub "$D" --vai dieu-phoi)
check "dieu-phoi: subscription kết nối, nhận kết quả đầu tiên" ok "$(jf 'd["ket_noi"] if "so_tin" in d else d' <<<"$r")"
check "kết quả chỉ có 5 trường của bản đồ (không SĐT, tên, mô tả)" "created_at id location status urgency" \
  "$(jf '" ".join(d.get("truong") or ["(chua co tin nao)"])' <<<"$r")"
sub "$D" --vai dieu-phoi --cho-moi --giay 12 --san-sang "$TMP/s-dp" >"$TMP/dp" &
sub "$C" --vai cuu-ho --cho-moi --giay 12 --san-sang "$TMP/s-ch" >"$TMP/ch" &
sub "$T" --vai tinh-nguyen --cho-moi --giay 12 --san-sang "$TMP/s-tn" >"$TMP/tn" &
san_sang=yes
for f in dp ch tn; do doi_file "$TMP/s-$f" || san_sang="chua: $f"; done
check "3 client nền (dieu-phoi, cuu-ho, tinh-nguyen) đã nhận kết quả đầu" yes "$san_sang"
luc_tao=$(python3 -c 'import time; print(time.time())')
NEW=$(tao_tin "$D" dieu-phoi "0968$(date +%H%M%S)" "$LNG" "$LAT" khan_cap)
check "dieu-phoi tạo tin thử qua /graphql" True "$([[ $NEW =~ ^[0-9a-f-]{36}$ ]] && echo True || echo "$NEW")"
[[ $NEW =~ ^[0-9a-f-]{36}$ ]] && TAO+=("$NEW")
wait
r=$(cat "$TMP/dp")
check "subscription dieu-phoi nhận đúng tin mới, không tải lại" "$NEW" "$(jf '(d.get("moi") or {}).get("id")' <<<"$r")"
tre=$(python3 -c 'import sys,json; r=json.loads(sys.argv[1]); print(round(r["luc_nhan"] - float(sys.argv[2]), 2) if r.get("luc_nhan") else "khong-nhan")' "$r" "$luc_tao")
check "từ lúc tạo tin tới lúc subscription nhận < 2 giây ($tre s)" True \
  "$(python3 -c 'import sys; print(sys.argv[1] != "khong-nhan" and float(sys.argv[1]) < 2)' "$tre")"
check "tin mới đúng tọa độ, mức khẩn, trạng thái" "[$LNG, $LAT] khan_cap tiep_nhan" \
  "$(jf 'str((d.get("moi") or {}).get("location", {}).get("coordinates")) + " " + str((d.get("moi") or {}).get("urgency")) + " " + str((d.get("moi") or {}).get("status"))' <<<"$r")"

# ---------- (4) Quyền theo hàng qua subscription ----------
check "cuu-ho không nhận tin chưa phân công cho đội mình" None "$(jf 'd.get("moi") if d.get("ket_noi") == "ok" else d' <"$TMP/ch")"
check "tinh-nguyen không nhận tin người khác tạo" None "$(jf 'd.get("moi") if d.get("ket_noi") == "ok" else d' <"$TMP/tn")"
rm -f "$TMP/s-tn"
sub "$T" --vai tinh-nguyen --cho-moi --giay 12 --san-sang "$TMP/s-tn" >"$TMP/tn2" &
doi_file "$TMP/s-tn" || true
MINE=$(tao_tin "$T" tinh-nguyen "0967$(date +%H%M%S)" "$LNG" 15.6602 cao)
check "tinh-nguyen tạo tin thử qua /graphql" True "$([[ $MINE =~ ^[0-9a-f-]{36}$ ]] && echo True || echo "$MINE")"
[[ $MINE =~ ^[0-9a-f-]{36}$ ]] && TAO+=("$MINE")
wait
r=$(cat "$TMP/tn2")
check "tinh-nguyen nhận tin chính mình tạo" "$MINE" "$(jf '(d.get("moi") or {}).get("id")' <<<"$r")"
check "tin của tinh-nguyen qua subscription không có SĐT" False "$(jf '"reporter_phone" in (d.get("moi") or {})' <<<"$r")"

if [ "$fail" -eq 0 ]; then echo "OK: smoke bản đồ realtime đạt"; else echo "CÓ LỖI: xem các dòng FAIL"; exit 1; fi
