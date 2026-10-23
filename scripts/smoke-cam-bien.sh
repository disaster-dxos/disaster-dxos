#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử luồng cảm biến của apps/cuu-tro (#30), chạy THẬT từ bộ giả lập MQTT tới GraphQL:
# (1) stream CUU_TRO_CAM_BIEN, CUU_TRO_CANH_BAO và consumer ghi-csdl đã được tạo khi app khởi động;
# (2) client MQTT không có thông tin xác thực bị từ chối (bộ giả lập không có mật khẩu);
# (3) giả lập gửi bản tin bình thường cho trạm AL-MN-02 → bản tin vào stream → dòng mới trong
#     sensor_readings (mức binh_thuong) → sensors.last_value / last_observed_at cập nhật;
# (4) kịch bản vượt ngưỡng → dòng nguy_hiem, sự kiện cảnh báo trên cuu-tro.canh-bao.cam-bien.AL-MN-02
#     (mức trước binh_thuong); gửi tiếp khi vẫn trên ngưỡng → KHÔNG có cảnh báo mới; nước rút → không cảnh báo;
# (5) bản tin sai (đơn vị sai, JSON hỏng, trạm không có) → bị bỏ, không ghi, consumer vẫn chạy, không tồn đọng;
# (6) dieu-phoi, cuu-ho, tinh-nguyen đọc sensor_readings qua APISIX /graphql; không token → 401;
#     không vai trò nào ghi được sensor_readings.
# Dùng: make up && bash scripts/smoke-cam-bien.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

KC="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-disaster}"
GW="http://localhost:${APISIX_PORT:-9080}"
TRAM=AL-MN-02   # seed: ngưỡng cảnh báo 300 cm, nguy hiểm 400 cm
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
# gql <token|-> <query>: POST qua gateway, in "<mã HTTP> <body>"
gql() {
  local out code body
  out=$(mktemp)
  body=$(python3 -c 'import sys,json; print(json.dumps({"query": sys.argv[1]}))' "$2")
  if [ "$1" = - ]; then
    code=$(curl -s -o "$out" -w '%{http_code}' -H 'Content-Type: application/json' -d "$body" "$GW/graphql")
  else
    code=$(curl -s -o "$out" -w '%{http_code}' -K <(printf 'header = "Authorization: Bearer %s"\n' "$1") \
      -H 'Content-Type: application/json' -d "$body" "$GW/graphql")
  fi
  printf '%s %s\n' "$code" "$(cat "$out")"
  rm -f "$out"
}
# jf <biểu thức python trên d>: đọc JSON từ stdin (bỏ mã HTTP ở đầu nếu có); lỗi GraphQL → ERR:<code>
jf() {
  python3 -c '
import sys, json
s = sys.stdin.read().strip()
if s[:3].isdigit() and s[3:4] == " ": s = s[4:]
d = json.loads(s)
if isinstance(d, dict) and "errors" in d:
    print("ERR:" + d["errors"][0].get("extensions", {}).get("code", "?")); sys.exit()
print(eval(sys.argv[1], {"d": d}))' "$1"
}
sql() { docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -q -v ON_ERROR_STOP=1'; }
jsz() { docker compose exec -T nats wget -qO- 'http://127.0.0.1:8222/jsz?streams=true&consumers=true'; }
# gia_lap <tham số>: chạy bộ giả lập trong container (mật khẩu thiết bị từ OpenBao), in dòng JSON cuối
gia_lap() { docker compose --profile core --profile app run --rm --no-deps -T cuu-tro-gia-lap python -m cuu_tro_workflow.gia_lap "$@" 2>&1 | grep '^{' | tail -1; }
# mqtt_tho <topic> <payload>: gửi bản tin bất kỳ (QoS 1) bằng user thiết bị, để thử bản tin sai
mqtt_tho() {
  docker compose --profile core --profile app run --rm --no-deps -T cuu-tro-gia-lap python -c '
import os, sys
from cuu_tro_workflow.gia_lap import ket_noi
c = ket_noi(os.environ["MQTT_HOST"], int(os.environ["MQTT_PORT"]), os.environ["MQTT_USERNAME"], os.environ["MQTT_PASSWORD"])
c.publish(sys.argv[1], sys.argv[2].encode(), qos=1).wait_for_publish(10)
c.disconnect(); c.loop_stop(); print("da-gui")' "$1" "$2" 2>&1 | grep -v '^$' | tail -1
}
canh_bao_cuoi() {
  docker compose exec -T cuu-tro-cam-bien bash /opt/dxos/env-from-files.sh /run/secrets/dxos \
    python -m cuu_tro_workflow.cam_bien_consumer canh-bao-cuoi "$TRAM" 2>/dev/null | tail -1 || true
}
# cho_dong <thời điểm ISO>: chờ tới 20 giây cho dòng sensor_readings của trạm tại thời điểm đó, in "giá trị mức"
cho_dong() {
  local i r
  for i in $(seq 1 40); do
    r=$(sql <<SQL
SELECT r.value || ' ' || r.level FROM cuu_tro.sensor_readings r JOIN cuu_tro.sensors s ON s.id = r.sensor_id
 WHERE s.code = '$TRAM' AND r.observed_at = '$1'::timestamptz;
SQL
)
    [ -n "$r" ] && { echo "$r"; return; }
    [ "$i" -lt 40 ] && sleep 0.5
  done
  echo "khong-co-dong"
}
so_dong() { sql <<<"SELECT count(*) FROM cuu_tro.sensor_readings;"; }
num() { python3 -c 'import sys; print("%.2f" % float(sys.argv[1]))' "$1"; }

# ---------- (1) Stream + consumer ----------
out=$(jsz)
check "stream CUU_TRO_CAM_BIEN, CUU_TRO_CANH_BAO, CUU_TRO_DIEU_PHOI đã tạo" "CUU_TRO_CAM_BIEN CUU_TRO_CANH_BAO CUU_TRO_DIEU_PHOI" \
  "$(jf '" ".join(sorted(s["name"] for a in d.get("account_details", []) for s in a.get("stream_detail", []) if s["name"].startswith("CUU_TRO_")))' <<<"$out")"
check "consumer ghi-csdl trên CUU_TRO_CAM_BIEN" True \
  "$(jf 'any(c["name"] == "ghi-csdl" for a in d.get("account_details", []) for s in a.get("stream_detail", []) if s["name"] == "CUU_TRO_CAM_BIEN" for c in s.get("consumer_detail", []))' <<<"$out")"
msgs_truoc=$(jf 'sum(s["state"]["messages"] for a in d["account_details"] for s in a["stream_detail"] if s["name"] == "CUU_TRO_CAM_BIEN")' <<<"$out")

# ---------- (2) MQTT không xác thực ----------
r=$(docker compose --profile core --profile app run --rm --no-deps -T -e MQTT_USERNAME= --entrypoint python cuu-tro-gia-lap \
  -m cuu_tro_workflow.gia_lap --mot-lan --tram "$TRAM" 2>&1 || true)
check "bộ giả lập không có user/mật khẩu bị NATS MQTT từ chối (Not authorized)" True "$([[ $r == *"từ chối kết nối: Not authorized"* ]] && echo True || echo "$r")"

# ---------- (3) Bản tin bình thường ----------
dong_truoc=$(so_dong)
bt=$(gia_lap --mot-lan --tram "$TRAM")
t1=$(jf 'd["thoi_diem"]' <<<"$bt"); v1=$(jf 'd["gia_tri"]' <<<"$bt")
check "giả lập gửi topic cuu-tro/cam-bien/$TRAM/muc-nuoc" "cuu-tro/cam-bien/$TRAM/muc-nuoc" "$(jf 'd["topic"]' <<<"$bt")"
check "dòng mới trong sensor_readings (bình thường)" "$(num "$v1") binh_thuong" "$(cho_dong "$t1")"
msgs_sau=$(jf 'sum(s["state"]["messages"] for a in d["account_details"] for s in a["stream_detail"] if s["name"] == "CUU_TRO_CAM_BIEN")' <<<"$(jsz)")
check "bản tin nằm trong stream CUU_TRO_CAM_BIEN" True "$([ "$msgs_sau" -gt "$msgs_truoc" ] && echo True || echo "$msgs_truoc → $msgs_sau")"
check "sensors.last_value / last_observed_at cập nhật" "$(num "$v1") true" \
  "$(sql <<<"SELECT last_value || ' ' || (last_observed_at = '$t1'::timestamptz) FROM cuu_tro.sensors WHERE code = '$TRAM';")"

# ---------- (4) Vượt ngưỡng → cảnh báo ----------
bt=$(gia_lap --mot-lan --kich-ban vuot-nguong --tram "$TRAM")
t2=$(jf 'd["thoi_diem"]' <<<"$bt"); v2=$(jf 'd["gia_tri"]' <<<"$bt")
check "dòng nguy_hiem trong sensor_readings" "$(num "$v2") nguy_hiem" "$(cho_dong "$t2")"
cb=""
for _ in $(seq 1 20); do
  cb=$(canh_bao_cuoi)
  [ "$(jf 'd.get("thoi_diem", "")' <<<"$cb")" != "" ] && \
    [ "$(python3 -c 'import sys; from datetime import datetime as D; print(D.fromisoformat(sys.argv[1]) == D.fromisoformat(sys.argv[2]))' "$(jf 'd["thoi_diem"]' <<<"$cb")" "$t2")" = True ] && break
  sleep 0.5
done
check "sự kiện cảnh báo trên cuu-tro.canh-bao.cam-bien.$TRAM" "vuot_nguong nguy_hiem binh_thuong 400.0 $v2" \
  "$(jf '" ".join(str(d.get(k)) for k in ("loai", "muc", "muc_truoc", "nguong", "gia_tri"))' <<<"$cb")"
check "thời điểm sự kiện = thời điểm bản tin" True \
  "$(python3 -c 'import sys; from datetime import datetime as D; print(D.fromisoformat(sys.argv[1]) == D.fromisoformat(sys.argv[2]))' "$(jf 'd.get("thoi_diem", "")' <<<"$cb")" "$t2" 2>&1)"
bt=$(gia_lap --mot-lan --kich-ban vuot-nguong --tram "$TRAM")
t3=$(jf 'd["thoi_diem"]' <<<"$bt")
check "vẫn trên ngưỡng: dòng nguy_hiem mới được ghi" nguy_hiem "$(cho_dong "$t3" | cut -d' ' -f2)"
sleep 1
check "vẫn trên ngưỡng: KHÔNG phát cảnh báo mới" True \
  "$(python3 -c 'import sys; from datetime import datetime as D; print(D.fromisoformat(sys.argv[1]) == D.fromisoformat(sys.argv[2]))' "$(jf 'd.get("thoi_diem", "")' <<<"$(canh_bao_cuoi)")" "$t2" 2>&1)"
bt=$(gia_lap --mot-lan --tram "$TRAM")
t4=$(jf 'd["thoi_diem"]' <<<"$bt")
check "nước rút: dòng binh_thuong, không cảnh báo" "binh_thuong True" \
  "$(cho_dong "$t4" | cut -d' ' -f2) $(python3 -c 'import sys; from datetime import datetime as D; print(D.fromisoformat(sys.argv[1]) == D.fromisoformat(sys.argv[2]))' "$(jf 'd.get("thoi_diem", "")' <<<"$(canh_bao_cuoi)")" "$t2" 2>&1)"

# ---------- (5) Bản tin sai ----------
dong_giua=$(so_dong)
now=$(python3 -c 'from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())')
check "gửi bản tin sai đơn vị" da-gui "$(mqtt_tho "cuu-tro/cam-bien/$TRAM/muc-nuoc" "{\"ma_tram\":\"$TRAM\",\"gia_tri\":1,\"don_vi\":\"m\",\"thoi_diem\":\"$now\"}")"
check "gửi bản tin JSON hỏng" da-gui "$(mqtt_tho "cuu-tro/cam-bien/$TRAM/muc-nuoc" '{hong')"
check "gửi bản tin trạm không có" da-gui "$(mqtt_tho "cuu-tro/cam-bien/KHONG-CO/muc-nuoc" "{\"ma_tram\":\"KHONG-CO\",\"gia_tri\":1,\"don_vi\":\"cm\",\"thoi_diem\":\"$now\"}")"
sleep 2
check "bản tin sai không tạo dòng sensor_readings" "$dong_giua" "$(so_dong)"
check "consumer ghi-csdl không tồn đọng (đã xử lý hết)" "0 0" \
  "$(jf '" ".join(str(c[k]) for a in d["account_details"] for s in a["stream_detail"] if s["name"] == "CUU_TRO_CAM_BIEN" for c in s["consumer_detail"] if c["name"] == "ghi-csdl" for k in ("num_pending", "num_ack_pending"))' <<<"$(jsz)")"
check "consumer cuu-tro-cam-bien vẫn chạy" running "$(docker compose ps --format '{{.State}}' cuu-tro-cam-bien)"
check "tổng dòng mới từ smoke (4 bản tin hợp lệ)" 4 "$(( $(so_dong) - dong_truoc ))"

# ---------- (6) GraphQL qua APISIX ----------
Q="{ sensor_readings(where: {sensor: {code: {_eq: \"$TRAM\"}}}, order_by: {observed_at: desc}, limit: 1) { value level sensor { code } } }"
for u in dieuphoi01 cuuho01 tinhnguyen01; do
  tok=$(get_token "$u")
  out=$(gql "$tok" "$Q")
  check "$u đọc sensor_readings qua /graphql" "200 binh_thuong $TRAM" \
    "${out%% *} $(jf 'd["data"]["sensor_readings"][0]["level"] + " " + d["data"]["sensor_readings"][0]["sensor"]["code"]' <<<"$out")"
  check "$u không ghi được sensor_readings" ERR:validation-failed \
    "$(gql "$tok" 'mutation { insert_sensor_readings_one(object: {value: 1, level: "binh_thuong"}) { id } }' | jf 'd')"
done
check "dieu-phoi đọc chuỗi đo qua quan hệ sensors.readings" True \
  "$(gql "$(get_token dieuphoi01)" "{ sensors(where: {code: {_eq: \"$TRAM\"}}) { readings_aggregate { aggregate { count } } } }" \
     | jf 'd["data"]["sensors"][0]["readings_aggregate"]["aggregate"]["count"] >= 4')"
check "/graphql không token (APISIX chặn)" 401 "$(gql - "$Q" | head -c 3)"
exit $fail
