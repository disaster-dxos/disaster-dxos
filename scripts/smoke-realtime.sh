#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử thông báo realtime (#68): Centrifugo OSS của lõi + cầu nối NATS → Centrifugo của apps/cuu-tro,
# đi THẬT qua APISIX (WebSocket /realtime/websocket, token qua /workflow/realtime/token):
# (1) Centrifugo không mở cổng ra host, HTTP API /api/* không có route qua gateway;
# (2) cấp token: không JWT → 401; cuu-ho, tinh-nguyen → 403; dieu-phoi → 200, token HS256 chỉ có sub +
#     kênh server-side "dieu-phoi" (iss cuu-tro-api, aud centrifugo, hạn ngắn), không tên/email, no-store;
# (3) kết nối WebSocket: không token, token ký bằng khóa khác, JWT Keycloak dùng thẳng → Centrifugo đóng
#     kết nối (3500/3501); Origin lạ → bắt tay 403; token của dieu-phoi → kết nối, kênh dieu-phoi;
# (4) tin kêu cứu mới (dieu-phoi tạo qua /graphql, ngoài bán kính mọi đội) → bộ khởi chạy phát
#     cuu-tro.dieu-phoi.tin-moi.<id> → web nhận "tin_moi" đúng id, không có SĐT/mô tả;
# (5) phát một sự kiện thử cuu-tro.dieu-phoi.can-xu-ly.<id> lên JetStream (kèm trường SĐT/tên giả) →
#     web nhận "can_xu_ly", trường ngoài danh sách trắng bị bỏ; phát lại cùng Nats-Msg-Id → không nhận lần 2;
# (6) make gia-lap-vuot-nguong (trạm AL-MN-02) → web nhận "canh_bao" trong 2 giây (tiêu chí #68).
# Dùng: make up && bash scripts/smoke-realtime.sh   (cần python3 trên máy host, không cần thư viện ngoài)
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

KC="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-disaster}"
GW="http://localhost:${APISIX_PORT:-9080}"
WS="ws://localhost:${APISIX_PORT:-9080}/realtime/websocket"
ORIGIN="${GATEWAY_PUBLIC_URL:-http://localhost:9080}"
TRAM=AL-MN-02   # seed: ngưỡng cảnh báo 300 cm, nguy hiểm 400 cm (giống smoke-cam-bien)
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
# api_token <JWT Keycloak|->: in "<mã HTTP> <body>" của GET /workflow/realtime/token, header vào $TMP/h
api_token() {
  local args=(-s -D "$TMP/h" -o "$TMP/b" -w '%{http_code}')
  local code
  if [ "$1" = - ]; then code=$(curl "${args[@]}" "$GW/workflow/realtime/token")
  else code=$(curl -K <(printf 'header = "Authorization: Bearer %s"\n' "$1") "${args[@]}" "$GW/workflow/realtime/token"); fi
  printf '%s %s\n' "$code" "$(cat "$TMP/b")"
}
jf() { python3 -c 'import sys,json; d=json.loads(sys.stdin.read()); print(eval(sys.argv[1], {"d": d}))' "$1"; }
# ws [tham số realtime-ws.py]: token qua biến môi trường REALTIME_TOKEN (không lên dòng lệnh)
ws() { python3 scripts/realtime-ws.py "$WS" --origin "$ORIGIN" "$@"; }
claims() { python3 -c 'import sys,json,base64; p=sys.argv[1].split(".")[1]; p+="="*(-len(p)%4); print(json.dumps(json.loads(base64.urlsafe_b64decode(p))))' "$1"; }
sql() { docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -q -v ON_ERROR_STOP=1'; }
temporal_cli() { docker compose exec -T temporal sh -c "temporal $* --address temporal:7233"; }
# phat <subject> <payload JSON> <Nats-Msg-Id>: phát lên JetStream bằng user cuu-tro-app (bí mật trong worker)
phat() {
  docker compose exec -T cuu-tro-worker python - "$@" <<'PY'
import asyncio, sys, nats
async def main():
    nc = await nats.connect(open("/run/secrets/dxos/NATS_URL").read().strip())
    ack = await nc.jetstream().publish(sys.argv[1], sys.argv[2].encode(), headers={"Nats-Msg-Id": sys.argv[3]})
    print(bool(ack.duplicate))
    await nc.close()
asyncio.run(main())
PY
}
gia_lap() { docker compose --profile core --profile app run --rm --no-deps -T cuu-tro-gia-lap python -m cuu_tro_workflow.gia_lap "$@" 2>&1 | grep '^{' | tail -1; }
# cho_su_kien <file kết quả> <loai:chuỗi> [giây]: mở WebSocket nền chờ sự kiện, ghi kết quả vào file
cho_su_kien() { REALTIME_TOKEN="$TOK" ws --cho "$2" --giay "${3:-15}" >"$1" & }
doi_ket_noi() { sleep 1.5; } # client nền đã kết nối xong trước khi phát sự kiện

NEW=''
reset() {
  if [ -n "$NEW" ]; then
    temporal_cli workflow terminate -w "phan-cong-$NEW" --reason smoke-reset >/dev/null 2>&1 || true
    sql >/dev/null <<<"DELETE FROM cuu_tro.incidents WHERE id = '$NEW';" || true
  fi
  rm -rf "$TMP"
}
trap reset EXIT

D=$(get_token dieuphoi01); C=$(get_token cuuho01); T=$(get_token tinhnguyen01)

# ---------- (1) Không lộ Centrifugo ra ngoài ----------
check "centrifugo không mở cổng ra host" "" "$(docker compose port centrifugo 8000 2>/dev/null || true)"
check "HTTP API Centrifugo không qua gateway (POST /api/publish)" 404 \
  "$(curl -s -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d '{}' "$GW/api/publish")"
check "đường khác của Centrifugo không qua gateway (POST /realtime/websocket)" 404 \
  "$(curl -s -o /dev/null -w '%{http_code}' -X POST "$GW/realtime/websocket")"

# ---------- (2) Cấp token ----------
out=$(api_token -); check "không JWT xin token → 401" 401 "${out%% *}"
out=$(api_token "$C"); check "cuu-ho xin token → 403" 403 "${out%% *}"
out=$(api_token "$T"); check "tinh-nguyen xin token → 403" 403 "${out%% *}"
out=$(api_token "$D")
check "dieu-phoi xin token → 200" 200 "${out%% *}"
TOK=$(jf 'd["token"]' <<<"${out#* }")
check "phản hồi token: Cache-Control no-store" True "$(grep -qi '^cache-control: no-store' "$TMP/h" && echo True || echo False)"
c=$(claims "$TOK")
check "token HS256, iss cuu-tro-api, aud centrifugo, kênh dieu-phoi" "HS256 cuu-tro-api centrifugo ['dieu-phoi']" \
  "$(python3 -c 'import sys,json,base64; p=sys.argv[1].split(".")[0]; p+="="*(-len(p)%4); print(json.loads(base64.urlsafe_b64decode(p))["alg"])' "$TOK") $(jf 'd["iss"] + " " + d["aud"] + " " + str(d["channels"])' <<<"$c")"
check "token chỉ có sub/iat/exp/iss/aud/channels (không tên, email, vai trò)" "aud channels exp iat iss sub" \
  "$(jf '" ".join(sorted(d))' <<<"$c")"
check "token hạn ngắn = REALTIME_TOKEN_HAN_GIAY" "${REALTIME_TOKEN_HAN_GIAY:-300}" "$(jf 'd["exp"] - d["iat"]' <<<"$c")"

# ---------- (3) Kết nối WebSocket ----------
check "WebSocket không token → bị từ chối" tu_choi "$(ws | jf 'd["ket_noi"]')"
GIA=$(python3 -c 'import sys,json,base64,hmac,hashlib,time
b=lambda x: base64.urlsafe_b64encode(x).rstrip(b"=").decode()
h=b(json.dumps({"alg":"HS256","typ":"JWT"}).encode())
p=b(json.dumps({"sub":"ke-gia-mao","exp":int(time.time())+300,"iss":"cuu-tro-api","aud":"centrifugo","channels":["dieu-phoi"]}).encode())
print(h+"."+p+"."+b(hmac.new(b"khoa-gia-mao-khong-phai-cua-he-thong", (h+"."+p).encode(), hashlib.sha256).digest()))')
check "WebSocket token ký bằng khóa khác → 3500" "tu_choi 3500" "$(REALTIME_TOKEN="$GIA" ws | jf 'd["ket_noi"] + " " + str(d.get("ma"))')"
check "WebSocket dùng thẳng JWT Keycloak của dieu-phoi → 3500" "tu_choi 3500" "$(REALTIME_TOKEN="$D" ws | jf 'd["ket_noi"] + " " + str(d.get("ma"))')"
check "WebSocket từ Origin lạ → bắt tay 403" "loi_http 403" \
  "$(REALTIME_TOKEN="$TOK" python3 scripts/realtime-ws.py "$WS" --origin http://evil.example | jf 'd["ket_noi"] + " " + str(d.get("ma"))')"
check "WebSocket token dieu-phoi → kết nối, kênh server-side dieu-phoi" "ok ['dieu-phoi']" \
  "$(REALTIME_TOKEN="$TOK" ws | jf 'd["ket_noi"] + " " + str(d.get("kenh"))')"

# ---------- (4) Tin kêu cứu mới → thông báo tin_moi ----------
PHONE="0969$(date +%H%M%S | cut -c1-6)"
cho_su_kien "$TMP/tin-moi" "tin_moi:" 20
doi_ket_noi
# shellcheck disable=SC2016 # $o là biến GraphQL
body=$(python3 -c 'import json,sys; print(json.dumps({"query": "mutation($o: incidents_insert_input!) { insert_incidents_one(object: $o) { id } }", "variables": {"o": {"description": "[smoke #68] nuoc ngap toi goi", "location": {"type": "Point", "coordinates": [107.6035, 15.6502]}, "urgency": "cao", "people_count": 2, "reporter_phone": sys.argv[1], "source": "web"}}}))' "$PHONE")
out=$(curl -s -K <(printf 'header = "Authorization: Bearer %s"\n' "$D") -H 'Content-Type: application/json' -H 'X-Hasura-Role: dieu-phoi' -d "$body" "$GW/graphql")
NEW=$(python3 -c 'import sys,json; print(json.load(sys.stdin)["data"]["insert_incidents_one"]["id"])' <<<"$out" 2>/dev/null || true)
check "dieu-phoi tạo tin mới qua /graphql" True "$([[ $NEW =~ ^[0-9a-f-]{36}$ ]] && echo True || echo "$out")"
wait
r=$(cat "$TMP/tin-moi")
check "web nhận tin_moi đúng tin, kênh dieu-phoi" "$NEW cao dieu-phoi" \
  "$(jf '(d.get("nhan") or {}).get("incident_id", "") + " " + str((d.get("nhan") or {}).get("urgency")) + " " + str(d.get("kenh_su_kien"))' <<<"$r")"
check "thông báo tin_moi không có SĐT, mô tả" True \
  "$(python3 -c 'import sys; r=sys.stdin.read(); print(sys.argv[1] not in r and "nuoc ngap" not in r and "reporter" not in r)' "$PHONE" <<<"$r")"

# ---------- (5) Sự kiện thử "cần xử lý" + danh sách trắng + chống trùng ----------
INC_THU=$(python3 -c 'import uuid; print(uuid.uuid4())')
MSG_ID="smoke-68:$INC_THU"
PAYLOAD=$(python3 -c 'import json,sys; print(json.dumps({"incident_id": sys.argv[1], "ly_do": "het_lan_giao", "urgency": "khan_cap", "so_lan_giao": 3, "workflow_id": "phan-cong-" + sys.argv[1], "mo_ta": "smoke #68", "reporter_phone": "0900000068", "reporter_name": "Nguoi Gia"}))' "$INC_THU")
cho_su_kien "$TMP/can-xu-ly" "can_xu_ly:$INC_THU" 15
doi_ket_noi
check "phát sự kiện thử lên JetStream (lần đầu)" False "$(phat "cuu-tro.dieu-phoi.can-xu-ly.$INC_THU" "$PAYLOAD" "$MSG_ID")"
wait
r=$(cat "$TMP/can-xu-ly")
check "web nhận can_xu_ly: id tin, lý do, mức khẩn, số lần giao" "$INC_THU het_lan_giao khan_cap 3" \
  "$(jf '" ".join(str((d.get("nhan") or {}).get(k)) for k in ("incident_id", "ly_do", "urgency", "so_lan_giao"))' <<<"$r")"
check "trường ngoài danh sách trắng bị bỏ (SĐT, tên, workflow_id)" "False False False" \
  "$(jf '" ".join(str(k in (d.get("nhan") or {})) for k in ("reporter_phone", "reporter_name", "workflow_id"))' <<<"$r")"
cho_su_kien "$TMP/trung" "can_xu_ly:$INC_THU" 4
doi_ket_noi
check "phát lại cùng Nats-Msg-Id → JetStream bỏ (duplicate)" True "$(phat "cuu-tro.dieu-phoi.can-xu-ly.$INC_THU" "$PAYLOAD" "$MSG_ID")"
wait
check "không nhận thông báo trùng" None "$(jf 'd.get("nhan")' <"$TMP/trung")"

# ---------- (6) Vượt ngưỡng → canh_bao trong 2 giây ----------
gia_lap --mot-lan --tram "$TRAM" >/dev/null   # đưa trạm về bình thường trước (lần chạy trước có thể còn nguy hiểm)
sleep 1
cho_su_kien "$TMP/canh-bao" "canh_bao:$TRAM" 20
doi_ket_noi
bt=$(gia_lap --mot-lan --kich-ban vuot-nguong --tram "$TRAM")
wait
r=$(cat "$TMP/canh-bao")
check "web nhận canh_bao của trạm $TRAM mức nguy_hiem" "$TRAM nguy_hiem" \
  "$(jf 'str((d.get("nhan") or {}).get("ma_tram")) + " " + str((d.get("nhan") or {}).get("muc"))' <<<"$r")"
tre=$(python3 -c 'import sys,json; from datetime import datetime as D
r=json.loads(sys.argv[1]); bt=json.loads(sys.argv[2])
print(round(r["luc_nhan"] - D.fromisoformat(bt["thoi_diem"]).timestamp(), 2) if r.get("luc_nhan") else "khong-nhan")' "$r" "$bt")
check "từ lúc thiết bị gửi tới lúc web nhận < 2 giây ($tre s)" True \
  "$(python3 -c 'import sys; print(sys.argv[1] != "khong-nhan" and float(sys.argv[1]) < 2)' "$tre")"
gia_lap --mot-lan --tram "$TRAM" >/dev/null   # nước rút: trả trạm về bình thường

if [ "$fail" -eq 0 ]; then echo "OK: smoke thông báo realtime đạt"; else echo "CÓ LỖI: xem các dòng FAIL"; exit 1; fi
