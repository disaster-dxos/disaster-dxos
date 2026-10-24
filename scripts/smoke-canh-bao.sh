#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử thông báo cảnh báo vượt ngưỡng (#87), chạy THẬT từ thiết bị MQTT tới hộp thư và web điều phối:
# (1) consumer canh-bao-temporal trên CUU_TRO_CANH_BAO, consumer cũ realtime-canh-bao không còn;
# (2) một đợt của trạm Hội An (QN-HA-01, ngưỡng 150/200 cm): bình thường → cảnh báo → vẫn cảnh báo →
#     nguy hiểm → xuống cảnh báo → nguy hiểm lại → bình thường. Workflow canh-bao-QN-HA-01-<đợt> chạy rồi
#     kết thúc; hộp thư có ĐÚNG 1 dòng cho mỗi bước canh_bao, nguy_hiem, ve_duoi_nguong (kênh gia-lap, đã
#     gửi); nội dung tiếng Việt có trạm, mực nước, cấp báo động, thời điểm, liên kết bản đồ;
# (3) web điều phối nhận thông báo đầu đợt qua Centrifugo (kênh dieu-phoi);
# (4) gửi lại cùng bản tin, gửi bù bản tin cũ, gửi lại sự kiện sau khi đợt đã kết thúc → không thêm dòng,
#     không tạo đợt mới;
# (5) dieu-phoi đọc hộp thư qua /graphql; cuu-ho, tinh-nguyen không thấy bảng; không token → 401;
# (6) CANH_BAO_KENH=telegram mà OpenBao chưa có token: bước bị ghi "loi" (không thử lại vô ích), đợt vẫn
#     tiếp tục; trả worker về gia-lap thì bước kết thúc đợt vẫn được báo.
# Dùng: make up && bash scripts/smoke-canh-bao.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

KC="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-disaster}"
GW="http://localhost:${APISIX_PORT:-9080}"
WS="ws://localhost:${APISIX_PORT:-9080}/realtime/websocket"
ORIGIN="${GATEWAY_PUBLIC_URL:-http://localhost:9080}"
TRAM=QN-HA-01      # seed: ngưỡng cảnh báo 150 cm, nguy hiểm 200 cm
TRAM_TG=DN-CLE-01  # seed: ngưỡng cảnh báo 180 cm, nguy hiểm 250 cm
TMP=$(mktemp -d)
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
gql() { # gql <token|-> <query>: POST /graphql qua gateway, in "<mã HTTP> <body>"
  local body code out
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
jf() {
  python3 -c '
import sys, json
s = sys.stdin.read().strip()
if s[:3].isdigit() and s[3:4] == " ": s = s[4:]
d = json.loads(s) if s else None
print(eval(sys.argv[1], {"d": d}))' "$1"
}
sql() { docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -q -v ON_ERROR_STOP=1'; }
jsz() { docker compose exec -T nats wget -qO- 'http://127.0.0.1:8222/jsz?streams=true&consumers=true'; }
# phat <subject> <payload JSON> <Nats-Msg-Id>: phát thẳng lên JetStream bằng user cuu-tro-app (giả lập sự kiện
# bị giao lại muộn, thứ consumer ghi-csdl không tự phát lại)
phat() {
  docker compose exec -T cuu-tro-worker python - "$@" <<'PY'
import asyncio, sys, nats
async def main():
    nc = await nats.connect(open("/run/secrets/dxos/NATS_URL").read().strip())
    await nc.jetstream().publish(sys.argv[1], sys.argv[2].encode(), headers={"Nats-Msg-Id": sys.argv[3]})
    print("da-phat")
    await nc.close()
asyncio.run(main())
PY
}
temporal_cli() { docker compose exec -T temporal sh -c "temporal $* --address temporal:7233"; }
mqtt_tho() { # mqtt_tho <mã trạm> <giá trị cm> <thời điểm ISO>: gửi một bản tin mực nước bằng user thiết bị
  docker compose --profile core --profile app run --rm --no-deps -T cuu-tro-gia-lap python -c '
import json, os, sys
from cuu_tro_workflow.gia_lap import ket_noi
c = ket_noi(os.environ["MQTT_HOST"], int(os.environ["MQTT_PORT"]), os.environ["MQTT_USERNAME"], os.environ["MQTT_PASSWORD"])
p = {"ma_tram": sys.argv[1], "gia_tri": float(sys.argv[2]), "don_vi": "cm", "thoi_diem": sys.argv[3]}
c.publish(f"cuu-tro/cam-bien/{sys.argv[1]}/muc-nuoc", json.dumps(p).encode(), qos=1).wait_for_publish(10)
c.disconnect(); c.loop_stop(); print("da-gui")' "$1" "$2" "$3" 2>&1 | grep -v '^$' | tail -1
}
# chuoi_ban_tin <mã trạm> <giá trị>...: gửi lần lượt, thời điểm cách nhau 2 giây, kết thúc ở hiện tại;
# in thời điểm từng bản tin, mỗi dòng một
chuoi_ban_tin() {
  local ma=$1 n i luc
  shift
  n=$#
  i=0
  for v in "$@"; do
    luc=$(python3 -c 'import sys; from datetime import datetime, timedelta, timezone; print((datetime.now(timezone.utc) - timedelta(seconds=2 * int(sys.argv[1]))).isoformat(timespec="milliseconds"))' "$((n - 1 - i))")
    [ "$(mqtt_tho "$ma" "$v" "$luc")" = da-gui ] || echo "LỖI gửi $ma $v" >&2
    echo "$luc"
    i=$((i + 1))
  done
}
dot_cua() { python3 -c 'import sys; from datetime import datetime, timezone; print(datetime.fromisoformat(sys.argv[1]).astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"))' "$1"; }
hop_thu() { # hop_thu <mã trạm> <đợt>: các bước trong hộp thư "bước:trạng thái:kênh", theo thứ tự tạo
  sql <<<"SELECT string_agg(step || ':' || status || ':' || channel, ' ' ORDER BY id) FROM cuu_tro.sensor_alert_notifications WHERE sensor_code = '$1' AND episode_at = '$2'::timestamptz;"
}
cho_hop_thu() { # cho_hop_thu <mã trạm> <đợt> <mong đợi> [giây]: chờ hộp thư đạt trạng thái mong đợi
  local i r
  for i in $(seq 1 $(( ${4:-30} * 2 ))); do
    r=$(hop_thu "$1" "$2")
    [ "$r" = "$3" ] && { echo "$r"; return; }
    [ "$i" -lt $(( ${4:-30} * 2 )) ] && sleep 0.5
  done
  echo "$r"
}
trang_thai_wf() { temporal_cli workflow describe -w "canh-bao-$1-$2" -o json 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["workflowExecutionInfo"]["status"])' 2>/dev/null || echo khong-co; }
khoi_dong_worker() { # khoi_dong_worker <kênh>: chạy lại worker với CANH_BAO_KENH khác, chờ healthy
  CANH_BAO_KENH=$1 docker compose --profile core --profile app up -d --no-deps cuu-tro-worker >/dev/null 2>&1
  for _ in $(seq 1 60); do
    [ "$(docker compose ps --format '{{.Health}}' cuu-tro-worker)" = healthy ] && return
    sleep 2
  done
}
# shellcheck disable=SC2329 # gọi qua trap EXIT
reset() {
  rm -rf "$TMP"
  # Luôn trả worker về kênh trong .env (mặc định gia-lap) kể cả khi smoke dừng giữa chừng ở bước (6)
  if [ "${DA_DOI_KENH:-0}" = 1 ]; then khoi_dong_worker "${CANH_BAO_KENH:-gia-lap}"; fi
}
trap reset EXIT

# ---------- (1) Consumer ----------
out=$(jsz)
check "consumer canh-bao-temporal trên CUU_TRO_CANH_BAO (realtime-canh-bao đã bỏ)" "canh-bao-temporal" \
  "$(jf '" ".join(sorted(c["name"] for a in d["account_details"] for s in a["stream_detail"] if s["name"] == "CUU_TRO_CANH_BAO" for c in s.get("consumer_detail", [])))' <<<"$out")"
check "worker chạy kênh gia-lap" True \
  "$(l=$(docker compose logs cuu-tro-worker 2>/dev/null); [[ $l == *"cảnh báo vượt ngưỡng gửi qua kênh gia-lap"* ]] && echo True || echo False)"

# ---------- (2) Một đợt đầy đủ ----------
mqtt_tho "$TRAM" 100 "$(python3 -c 'from datetime import datetime, timedelta, timezone; print((datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat(timespec="milliseconds"))')" >/dev/null
sleep 3   # đợt cũ (nếu lần chạy trước còn) nhận "về dưới ngưỡng" xong
TOK=$(get_token dieuphoi01)
REALTIME_TOKEN=$(curl -s -K <(printf 'header = "Authorization: Bearer %s"\n' "$TOK") "$GW/workflow/realtime/token" | jf 'd["token"]')
REALTIME_TOKEN="$REALTIME_TOKEN" python3 scripts/realtime-ws.py "$WS" --origin "$ORIGIN" --cho "canh_bao:$TRAM" --giay 30 >"$TMP/web" &
sleep 1.5
mapfile -t LUC < <(chuoi_ban_tin "$TRAM" 160 170 210 190 220 120)
DOT=$(dot_cua "${LUC[0]}")
check "hộp thư: đúng 1 lần mỗi bước của đợt $DOT" "canh_bao:da_gui:gia-lap nguy_hiem:da_gui:gia-lap ve_duoi_nguong:da_gui:gia-lap" \
  "$(cho_hop_thu "$TRAM" "$DOT" "canh_bao:da_gui:gia-lap nguy_hiem:da_gui:gia-lap ve_duoi_nguong:da_gui:gia-lap")"
for _ in $(seq 1 20); do [ "$(trang_thai_wf "$TRAM" "$DOT")" = WORKFLOW_EXECUTION_STATUS_COMPLETED ] && break; sleep 0.5; done
check "workflow canh-bao-$TRAM-$DOT đã kết thúc" WORKFLOW_EXECUTION_STATUS_COMPLETED "$(trang_thai_wf "$TRAM" "$DOT")"
check "kết quả workflow: đã báo 3 bước, kết thúc khi về dưới ngưỡng" "['canh_bao', 'nguy_hiem', 've_duoi_nguong'] ve_duoi_nguong" \
  "$(temporal_cli workflow show -w "canh-bao-$TRAM-$DOT" -o json 2>/dev/null | python3 -c '
import sys, json, base64
ev = [e for e in json.load(sys.stdin)["events"] if "workflowExecutionCompletedEventAttributes" in e]
r = json.loads(base64.b64decode(ev[-1]["workflowExecutionCompletedEventAttributes"]["result"]["payloads"][0]["data"]))
print(r["da_bao"], r["ket_thuc"])' 2>/dev/null || echo khong-doc-duoc)"
noi=$(sql <<<"SELECT message FROM cuu_tro.sensor_alert_notifications WHERE sensor_code = '$TRAM' AND episode_at = '$DOT'::timestamptz AND step = 'nguy_hiem';")
check "nội dung bước nguy_hiem: tiêu đề tiếng Việt có tên + mã trạm" True \
  "$([[ $noi == "🔴 NGUY HIỂM: Mực nước sông Hoài tại Hội An (giả lập) ($TRAM)"* ]] && echo True || echo "$noi")"
dong4=$(sed -n 4p <<<"$noi")
if [[ $dong4 == "Thời điểm đo: "*"(giờ Việt Nam)" ]]; then dong4=True; fi
check "nội dung: mực nước + ngưỡng, cấp báo động, thời điểm giờ Việt Nam" "Mực nước: 210 cm (ngưỡng nguy hiểm 200 cm)|Cấp báo động: Nguy hiểm (trước: Cảnh báo)|True" \
  "$(sed -n 2p <<<"$noi")|$(sed -n 3p <<<"$noi")|$dong4"
check "nội dung: liên kết bản đồ tới tọa độ trạm và web điều phối" "Bản đồ: https://www.openstreetmap.org/?mlat=15.87700&mlon=108.33300#map=14/15.87700/108.33300|Web điều phối: ${GATEWAY_PUBLIC_URL:-http://localhost:9080}/" \
  "$(sed -n 5p <<<"$noi")|$(sed -n 6p <<<"$noi")"
check "nội dung bước kết thúc đợt" "🟢 ĐÃ VỀ DƯỚI NGƯỠNG: Mực nước sông Hoài tại Hội An (giả lập) ($TRAM)|Cấp báo động: Bình thường (cao nhất trong đợt: Nguy hiểm)" \
  "$(sql <<<"SELECT split_part(message, E'\n', 1) || '|' || split_part(message, E'\n', 3) FROM cuu_tro.sensor_alert_notifications WHERE sensor_code = '$TRAM' AND episode_at = '$DOT'::timestamptz AND step = 've_duoi_nguong';")"
check "hộp thư không có dữ liệu cá nhân (không dãy số dạng SĐT)" 0 \
  "$(sql <<<"SELECT count(*) FROM cuu_tro.sensor_alert_notifications WHERE message ~ '(^|[^0-9])0[0-9]{8,}';")"

# ---------- (3) Web điều phối ----------
wait
check "web điều phối nhận thông báo đầu đợt (canh_bao, bước canh_bao) qua Centrifugo" "$TRAM canh_bao $DOT" \
  "$(jf '"%s %s %s" % ((d.get("nhan") or {}).get("ma_tram"), (d.get("nhan") or {}).get("buoc"), (d.get("nhan") or {}).get("dot"))' <"$TMP/web")"

# ---------- (4) Gửi lại, gửi bù, sau khi đợt kết thúc ----------
check "gửi lại đúng bản tin nguy hiểm" da-gui "$(mqtt_tho "$TRAM" 210 "${LUC[2]}")"
check "gửi bù bản tin cảnh báo cũ" da-gui "$(mqtt_tho "$TRAM" 175 "$(python3 -c 'import sys; from datetime import datetime, timedelta; print((datetime.fromisoformat(sys.argv[1]) - timedelta(seconds=1)).isoformat())' "${LUC[1]}")")"
sleep 3
check "gửi lại/gửi bù không thêm dòng hộp thư của đợt" 3 \
  "$(sql <<<"SELECT count(*) FROM cuu_tro.sensor_alert_notifications WHERE sensor_code = '$TRAM' AND episode_at = '$DOT'::timestamptz;")"
check "không có đợt nào khác mở ra cho $TRAM sau đợt $DOT" 0 \
  "$(sql <<<"SELECT count(*) FROM cuu_tro.sensor_alert_notifications WHERE sensor_code = '$TRAM' AND episode_at > '$DOT'::timestamptz;")"
# Bản tin gửi lại/gửi bù bị consumer ghi-csdl chặn trước (không phải lần đo mới nhất). Sự kiện của đợt đã xong
# bị giao lại muộn (phát thẳng lên stream) thì Temporal từ chối chạy lại id đợt, không thêm dòng
check "phát lại sự kiện nguy_hiem của đợt đã kết thúc" da-phat \
  "$(phat "cuu-tro.canh-bao.cam-bien.$TRAM" "{\"loai\":\"vuot_nguong\",\"ma_tram\":\"$TRAM\",\"ten_tram\":\"x\",\"dai_luong\":\"muc_nuoc\",\"muc\":\"nguy_hiem\",\"muc_truoc\":\"canh_bao\",\"gia_tri\":230,\"nguong\":200,\"don_vi\":\"cm\",\"thoi_diem\":\"${LUC[2]}\",\"dot\":\"$DOT\"}" "smoke-giao-lai-$DOT")"
for _ in $(seq 1 20); do
  l=$(docker compose logs --since 2m cuu-tro-worker 2>/dev/null)
  [[ $l == *"đợt $DOT đã kết thúc"* ]] && break
  sleep 0.5
done
check "hộp thư của đợt vẫn đúng 3 dòng" 3 \
  "$(sql <<<"SELECT count(*) FROM cuu_tro.sensor_alert_notifications WHERE sensor_code = '$TRAM' AND episode_at = '$DOT'::timestamptz;")"
check "sự kiện của đợt đã kết thúc bị bỏ qua (Temporal từ chối chạy lại id đợt)" True \
  "$(l=$(docker compose logs --since 2m cuu-tro-worker 2>/dev/null); [[ $l == *"đợt $DOT đã kết thúc"* ]] && echo True || echo False)"

# ---------- (5) Quyền đọc hộp thư ----------
Q="{ sensor_alert_notifications(where: {sensor_code: {_eq: \"$TRAM\"}, episode_at: {_eq: \"$DOT\"}}, order_by: {id: asc}) { step status channel sensor { code } } }"
check "dieu-phoi đọc hộp thư qua /graphql" "200 canh_bao,nguy_hiem,ve_duoi_nguong $TRAM" \
  "$(gql "$TOK" "$Q" | python3 -c 'import sys,json; s=sys.stdin.read(); d=json.loads(s[4:]); r=d["data"]["sensor_alert_notifications"]; print(s[:3], ",".join(x["step"] for x in r), r[0]["sensor"]["code"])')"
for u in cuuho01 tinhnguyen01; do
  check "$u không thấy hộp thư cảnh báo" validation-failed \
    "$(gql "$(get_token "$u")" "$Q" | jf 'd["errors"][0]["extensions"]["code"] if "errors" in d else "doc-duoc"')"
done
check "/graphql không token → 401" 401 "$(gql - "$Q" | head -c 3)"

# ---------- (6) Kênh telegram chưa có token ----------
mqtt_tho "$TRAM_TG" 100 "$(python3 -c 'from datetime import datetime, timedelta, timezone; print((datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat(timespec="milliseconds"))')" >/dev/null
sleep 3
DA_DOI_KENH=1
khoi_dong_worker telegram
check "worker chạy lại với CANH_BAO_KENH=telegram" healthy "$(docker compose ps --format '{{.Health}}' cuu-tro-worker)"
mapfile -t LUC2 < <(chuoi_ban_tin "$TRAM_TG" 200)
DOT2=$(dot_cua "${LUC2[0]}")
check "telegram chưa có token: bước canh_bao ghi lỗi, không thử lại" "canh_bao:loi:telegram" \
  "$(cho_hop_thu "$TRAM_TG" "$DOT2" "canh_bao:loi:telegram")"
check "lỗi ghi rõ nguyên nhân cấu hình" True \
  "$(d=$(sql <<<"SELECT detail || ' ' || attempts FROM cuu_tro.sensor_alert_notifications WHERE sensor_code = '$TRAM_TG' AND episode_at = '$DOT2'::timestamptz AND step = 'canh_bao';"); [[ $d == *"thiếu TELEGRAM_BOT_TOKEN"*" 1" ]] && echo True || echo "$d")"
khoi_dong_worker "${CANH_BAO_KENH:-gia-lap}"
DA_DOI_KENH=0
check "worker trở lại kênh ${CANH_BAO_KENH:-gia-lap}" healthy "$(docker compose ps --format '{{.Health}}' cuu-tro-worker)"
chuoi_ban_tin "$TRAM_TG" 150 >/dev/null
check "đợt vẫn tiếp tục: bước kết thúc đợt được báo qua gia-lap" "canh_bao:loi:telegram ve_duoi_nguong:da_gui:gia-lap" \
  "$(cho_hop_thu "$TRAM_TG" "$DOT2" "canh_bao:loi:telegram ve_duoi_nguong:da_gui:gia-lap")"
exit $fail
