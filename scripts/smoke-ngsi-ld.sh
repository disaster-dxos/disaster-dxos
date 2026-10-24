#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử bản sao số trạm đo NGSI-LD (#85) và trận lũ mẫu (#84), chạy THẬT từ bộ giả lập MQTT tới Scorpio:
# (1) Scorpio của lõi: không mở cổng ra host, CSDL riêng thuộc role scorpio (không superuser) có PostGIS,
#     không có MongoDB; consumer ban-sao-so trên stream CUU_TRO_CAM_BIEN cạnh ghi-csdl;
# (2) gateway /ngsi-ld/v1/*: không token → 401; có token → 200 (tên ngắn theo @context do gateway đặt);
#     ghi qua gateway, jsonldContexts, subscriptions → 403; Link/NGSILD-Tenant của client bị thay/bỏ;
#     WAF chặn XSS trong tham số q;
# (3) trận lũ mẫu: phát lại 49 giờ của trạm Câu Lâu (QN-CL-01) → 49 dòng sensor_readings đúng chuỗi trong
#     tệp, mức bình thường → cảnh báo → nguy hiểm → cảnh báo → bình thường; thực thể NGSI-LD = giờ cuối;
# (4) mọi trạm của trận lũ (9 trạm) có thực thể đúng loại, tọa độ, ngưỡng; lọc q=alertLevel, truy vấn
#     không gian (georel near) trả GeoJSON;
# (5) bản tin mới → thực thể cập nhật trong vài giây; bản tin cũ hơn (gửi bù) không ghi đè; gửi lại cùng
#     bản tin không đổi gì; bản tin sai bị bỏ;
# (6) Scorpio dừng → bản tin chờ, consumer giao lại có hẹn giờ; Scorpio chạy lại → thực thể được cập nhật,
#     consumer không tồn đọng.
# Dùng: make up && bash scripts/smoke-ngsi-ld.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

KC="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-disaster}"
GW="http://localhost:${APISIX_PORT:-9080}"
TRAM=QN-CL-01   # Câu Lâu: ngưỡng cảnh báo 300 cm, nguy hiểm 400 cm, đỉnh trận lũ mẫu 450 cm
ID="urn:ngsi-ld:WaterLevelStation:$TRAM"
TEP=apps/cuu-tro/workflow/cuu_tro_workflow/du_lieu/tran_lu_mau.json
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
# ngsi <token|-> <đường dẫn + query> [header curl thêm...]: GET qua gateway, in "<mã HTTP> <body>"
ngsi() {
  local tok=$1 path=$2 out code
  shift 2
  out=$(mktemp)
  if [ "$tok" = - ]; then
    code=$(curl -s -o "$out" -w '%{http_code}' "$@" "$GW$path")
  else
    code=$(curl -s -o "$out" -w '%{http_code}' -K <(printf 'header = "Authorization: Bearer %s"\n' "$tok") "$@" "$GW$path")
  fi
  printf '%s %s\n' "$code" "$(tr -d '\n' < "$out")"
  rm -f "$out"
}
# jf <biểu thức python trên d>: đọc JSON từ stdin (bỏ mã HTTP ở đầu nếu có)
jf() {
  python3 -c '
import sys, json
s = sys.stdin.read().strip()
if s[:3].isdigit() and s[3:4] == " ": s = s[4:]
d = json.loads(s) if s else None
print(eval(sys.argv[1], {"d": d}))' "$1"
}
sql() { docker compose exec -T postgres sh -c "psql -U \"\$POSTGRES_USER\" -d \"${1:-\$POSTGRES_DB}\" -tA -q -v ON_ERROR_STOP=1"; }
jsz() { docker compose exec -T nats wget -qO- 'http://127.0.0.1:8222/jsz?streams=true&consumers=true'; }
# Bộ giả lập và gửi bản tin bất kỳ bằng user thiết bị MQTT (như smoke-cam-bien.sh)
gia_lap() { docker compose --profile core --profile app run --rm --no-deps -T cuu-tro-gia-lap python -m cuu_tro_workflow.gia_lap "$@" 2>&1 | grep '^{'; }
mqtt_tho() {
  docker compose --profile core --profile app run --rm --no-deps -T cuu-tro-gia-lap python -c '
import os, sys
from cuu_tro_workflow.gia_lap import ket_noi
c = ket_noi(os.environ["MQTT_HOST"], int(os.environ["MQTT_PORT"]), os.environ["MQTT_USERNAME"], os.environ["MQTT_PASSWORD"])
c.publish(sys.argv[1], sys.argv[2].encode(), qos=1).wait_for_publish(10)
c.disconnect(); c.loop_stop(); print("da-gui")' "$1" "$2" 2>&1 | grep -v '^$' | tail -1
}
ban_tin() { # ban_tin <giá trị> <thời điểm ISO>: payload JSON cho trạm $TRAM
  printf '{"ma_tram":"%s","gia_tri":%s,"don_vi":"cm","thoi_diem":"%s"}' "$TRAM" "$1" "$2"
}
iso() { python3 -c 'import sys; from datetime import datetime, timedelta, timezone; print((datetime.now(timezone.utc) + timedelta(seconds=float(sys.argv[1]))).isoformat(timespec="milliseconds"))' "${1:-0}"; }
cung_luc() { python3 -c 'import sys; from datetime import datetime as D; f=lambda s: D.fromisoformat(s.replace("Z", "+00:00")); print(f(sys.argv[1]) == f(sys.argv[2]))' "$1" "$2" 2>/dev/null || echo False; }
# thuc_the <token>: thực thể của $TRAM dạng keyValues + observedAt của waterLevel, in "giá_trị mức observedAt"
thuc_the() {
  local out
  out=$(ngsi "$1" "/ngsi-ld/v1/entities/$ID")
  jf '"%s %s %s" % (d["waterLevel"]["value"], d["alertLevel"]["value"], d["waterLevel"]["observedAt"]) if isinstance(d, dict) and "waterLevel" in d else "khong-co"' <<<"$out"
}
# cho_thuc_the <token> <giá trị mong đợi> <thời điểm>: chờ tới N giây, in số giây đã chờ (hoặc "het-gio")
cho_thuc_the() {
  local r bat_dau
  bat_dau=$(python3 -c 'import time; print(time.time())')
  for _ in $(seq 1 "${4:-40}"); do
    r=$(thuc_the "$1")
    if [ "${r%% *}" = "$2" ] && [ "$(cung_luc "${r##* }" "$3")" = True ]; then
      python3 -c 'import sys, time; print("%.1f" % (time.time() - float(sys.argv[1])))' "$bat_dau"; return
    fi
    sleep 0.5
  done
  echo het-gio
}
num() { python3 -c 'import sys; print(float(sys.argv[1]))' "$1"; }

TOK=$(get_token dieuphoi01)

# ---------- (1) Scorpio + consumer ----------
check "Scorpio healthy" healthy "$(docker compose ps --format '{{.Health}}' scorpio)"
# Image khai báo EXPOSE 9090: "compose port" in ":0" dù không publish, nên đọc thẳng cổng đã publish
check "Scorpio không mở cổng ra host" "" "$(docker port "$(docker compose ps -q scorpio)" 2>/dev/null || true)"
check "CSDL ${SCORPIO_DB:-scorpio} thuộc role scorpio, có PostGIS, có bảng entity" "scorpio true true" \
  "$(sql <<<"SELECT pg_get_userbyid(datdba) || ' ' || EXISTS (SELECT FROM pg_extension WHERE extname = 'postgis') || ' ' || (to_regclass('public.entity') IS NOT NULL) FROM pg_database WHERE datname = current_database();" "${SCORPIO_DB:-scorpio}")"
check "role scorpio không phải superuser, không tạo được CSDL/role" "false false false" \
  "$(sql <<<"SELECT rolsuper || ' ' || rolcreatedb || ' ' || rolcreaterole FROM pg_roles WHERE rolname = '${SCORPIO_DB_USER:-scorpio}';")"
check "không có dịch vụ MongoDB trong stack" "" "$(docker compose --profile '*' config --images | grep -i mongo || true)"
out=$(jsz)
check "consumer ghi-csdl và ban-sao-so trên CUU_TRO_CAM_BIEN" "ban-sao-so ghi-csdl" \
  "$(jf '" ".join(sorted(c["name"] for a in d["account_details"] for s in a["stream_detail"] if s["name"] == "CUU_TRO_CAM_BIEN" for c in s.get("consumer_detail", [])))' <<<"$out")"
check "cuu-tro-ban-sao-so healthy" healthy "$(docker compose ps --format '{{.Health}}' cuu-tro-ban-sao-so)"

# ---------- (2) Gateway ----------
check "GET /ngsi-ld/v1/entities không token → 401" 401 "$(ngsi - '/ngsi-ld/v1/entities?type=WaterLevelStation' | cut -c1-3)"
for u in dieuphoi01 cuuho01 tinhnguyen01; do
  check "$u đọc /ngsi-ld/v1/entities qua gateway" 200 "$(ngsi "$(get_token "$u")" '/ngsi-ld/v1/entities?type=WaterLevelStation&options=keyValues' | cut -c1-3)"
done
check "POST entityOperations/upsert qua gateway → 403" 403 \
  "$(ngsi "$TOK" /ngsi-ld/v1/entityOperations/upsert -X POST -H 'Content-Type: application/ld+json' -d '[]' | cut -c1-3)"
check "DELETE thực thể qua gateway → 403" 403 "$(ngsi "$TOK" "/ngsi-ld/v1/entities/$ID" -X DELETE | cut -c1-3)"
check "PATCH thuộc tính qua gateway → 403" 403 \
  "$(ngsi "$TOK" "/ngsi-ld/v1/entities/$ID/attrs" -X PATCH -H 'Content-Type: application/json' -d '{}' | cut -c1-3)"
for p in /ngsi-ld/v1/jsonldContexts /ngsi-ld/v1/subscriptions /ngsi-ld/v1/csourceRegistrations /ngsi-ld/v1/temporal/entities /ngsi-ld/q/health; do
  check "GET $p qua gateway → 403" 403 "$(ngsi "$TOK" "$p" | cut -c1-3)"
done
check "WAF chặn XSS trong tham số q" 403 \
  "$(ngsi "$TOK" '/ngsi-ld/v1/entities?type=WaterLevelStation&q=name==%22%3Cscript%3Ealert(1)%3C/script%3E%22' | cut -c1-3)"

# ---------- (3) Trận lũ mẫu: phát lại 49 giờ của Câu Lâu ----------
read -r so_buoc dinh cuoi < <(python3 -c 'import json,sys; t=next(x for x in json.load(open(sys.argv[1]))["tram"] if x["ma"]==sys.argv[2]); c=t["chuoi"]; print(len(c), max(c), c[-1])' "$TEP" "$TRAM")
phat=$(gia_lap --kich-ban tran-lu --phat-lai --tram "$TRAM")
check "giả lập phát lại đủ $so_buoc giờ của $TRAM" "$so_buoc" "$(grep -c "\"ma_tram\": \"$TRAM\"" <<<"$phat")"
t_dau=$(head -1 <<<"$phat" | jf 'd["thoi_diem"]'); t_cuoi=$(tail -1 <<<"$phat" | jf 'd["thoi_diem"]')
check "thời điểm phát lại cách nhau 1 giờ, cách giờ đầu 48 giờ" 172800 \
  "$(python3 -c 'import sys; from datetime import datetime as D; print(int((D.fromisoformat(sys.argv[2]) - D.fromisoformat(sys.argv[1])).total_seconds()))' "$t_dau" "$t_cuoi")"
cho=$(cho_thuc_the "$TOK" "$(num "$cuoi")" "$t_cuoi" 60)
if [ "$cho" != het-gio ]; then r=True; else r=$(thuc_the "$TOK"); fi
check "thực thể $TRAM = giờ cuối của trận lũ ($cuoi cm, $t_cuoi)" True "$r"
# Đúng các thời điểm vừa phát lại (chạy lại smoke trên volume cũ không lẫn dòng của lần trước)
moc=$(python3 -c 'import sys, json; print("{" + ",".join(json.loads(l)["thoi_diem"] for l in sys.stdin if l.strip()) + "}")' <<<"$phat")
q_dong="SELECT r.value FROM cuu_tro.sensor_readings r JOIN cuu_tro.sensors s ON s.id = r.sensor_id
 WHERE s.code = '$TRAM' AND r.observed_at = ANY ('$moc'::timestamptz[]) ORDER BY r.observed_at"
for _ in $(seq 1 20); do [ "$(sql <<<"SELECT count(*) FROM ($q_dong) x;")" = "$so_buoc" ] && break; sleep 0.5; done
check "sensor_readings có đủ $so_buoc giờ, đúng chuỗi trong tệp" True \
  "$(sql <<<"$q_dong;" | python3 -c 'import json,sys; c=next(x for x in json.load(open(sys.argv[1]))["tram"] if x["ma"]==sys.argv[2])["chuoi"]; v=[float(l) for l in sys.stdin.read().split()]; print(v == [round(x, 2) for x in c] or (len(v), v[:3]))' "$TEP" "$TRAM")"
check "mức theo giờ: bình thường → cảnh báo → nguy hiểm → cảnh báo → bình thường" \
  "binh_thuong canh_bao nguy_hiem canh_bao binh_thuong" \
  "$(sql <<<"${q_dong/SELECT r.value/SELECT r.level};" | awk 'NR==1 || $0 != p {printf "%s%s", (NR>1?" ":""), $0} {p=$0}')"
check "đỉnh trận lũ $TRAM trong chuỗi đo = $dinh cm (vượt ngưỡng nguy hiểm 400)" "$(num "$dinh")" \
  "$(num "$(sql <<<"SELECT max(value) FROM ($q_dong) x;")")"

check "phát lại dồn dập: kết nối PostgreSQL của Scorpio trong giới hạn pool (≤ ${SCORPIO_DB_POOL:-8} + 2)" true \
  "$(sql <<<"SELECT (count(*) <= ${SCORPIO_DB_POOL:-8} + 2)::text FROM pg_stat_activity WHERE usename = '${SCORPIO_DB_USER:-scorpio}';")"
bo_vi_scorpio() { local l; l=$(docker compose logs cuu-tro-ban-sao-so 2>/dev/null); grep -c "bỏ bản tin .*Scorpio trả" <<<"$l" || true; }
check "không bản tin hợp lệ nào bị consumer bỏ vì lỗi Scorpio" 0 "$(bo_vi_scorpio)"

# ---------- (4) Mọi trạm của trận lũ ----------
gia_lap --mot-lan --kich-ban tran-lu --buoc-dau 20 >/dev/null
sleep 3
mong=$(python3 -c '
import json, sys
d = json.load(open(sys.argv[1]))
print(" ".join(sorted("%s:%s" % (t["ma"], "RainGauge" if t["kind"] == "luong_mua" else "WaterLevelStation") for t in d["tram"])))' "$TEP")
lay_tat_ca() {
  for ty in WaterLevelStation RainGauge; do ngsi "$TOK" "/ngsi-ld/v1/entities?type=$ty&options=keyValues&limit=100"; done
}
for _ in $(seq 1 30); do
  thuc=$(lay_tat_ca | while read -r _c body; do jf '"\n".join("%s:%s" % (e["stationCode"], e["type"]) for e in d)' <<<"$body"; done | sort | tr '\n' ' ' | sed 's/ $//')
  [ "$thuc" = "$mong" ] && break
  sleep 1
done
check "9 trạm của trận lũ có thực thể đúng loại" "$mong" "$thuc"
check "thực thể Ái Nghĩa: tọa độ, ngưỡng, đơn vị khớp seed" "[108.115, 15.886] 900.0 1000.0 CMT" \
  "$(ngsi "$TOK" '/ngsi-ld/v1/entities/urn:ngsi-ld:WaterLevelStation:QN-AN-01' | jf '"%s %s %s %s" % (d["location"]["value"]["coordinates"], d["warningThreshold"]["value"], d["dangerThreshold"]["value"], d["waterLevel"]["unitCode"])')"
nh=$(python3 -c '
import json, sys
d = json.load(open(sys.argv[1]))
print(" ".join(sorted(t["ma"] for t in d["tram"] if t["kind"] == "muc_nuoc" and t["chuoi"][20] >= t["nguong_nguy_hiem"])))' "$TEP")
check "lọc q=alertLevel==\"nguy_hiem\" (giờ 20 của trận lũ)" "$nh" \
  "$(ngsi "$TOK" '/ngsi-ld/v1/entities?type=WaterLevelStation&q=alertLevel==%22nguy_hiem%22&options=keyValues&limit=100' | jf '" ".join(sorted(e["stationCode"] for e in d))')"
check "georel near 5 km quanh Đại Lộc trả GeoJSON chỉ các trạm gần" "FeatureCollection AL-MN-01 AL-MN-02 QN-AN-01 QN-GT-01" \
  "$(ngsi "$TOK" '/ngsi-ld/v1/entities?type=WaterLevelStation&georel=near;maxDistance==5000&geometry=Point&coordinates=%5B108.11,15.86%5D&options=keyValues' -H 'Accept: application/geo+json' \
     | jf 'd["type"] + " " + " ".join(sorted(f["properties"]["stationCode"] for f in d["features"]))')"
check "Link/NGSILD-Tenant của client bị gateway thay/bỏ (vẫn tên ngắn, tenant mặc định)" "200 $TRAM" \
  "$(ngsi "$TOK" "/ngsi-ld/v1/entities/$ID?options=keyValues" -H 'Link: <http://example.invalid/ctx.jsonld>; rel="http://www.w3.org/ns/json-ld#context"' -H 'NGSILD-Tenant: khac' \
     | python3 -c 'import sys,json; s=sys.stdin.read(); print(s[:3], json.loads(s[4:]).get("stationCode"))')"

# ---------- (5) Cập nhật, gửi bù, gửi lại, bản tin sai ----------
t5=$(iso 0)
check "gửi bản tin mới (412.5 cm)" da-gui "$(mqtt_tho "cuu-tro/cam-bien/$TRAM/muc-nuoc" "$(ban_tin 412.5 "$t5")")"
cho=$(cho_thuc_the "$TOK" 412.5 "$t5")
check "thực thể cập nhật giá trị mới, mức nguy_hiem" "412.5 nguy_hiem" "$(thuc_the "$TOK" | cut -d' ' -f1,2)"
check "bản tin → Scorpio trong vòng 5 giây (đo được ${cho}s)" True \
  "$([ "$cho" != het-gio ] && python3 -c 'import sys; print(float(sys.argv[1]) <= 5)' "$cho" || echo het-gio)"
check "gửi bù bản tin cũ hơn 10 phút (999 cm)" da-gui "$(mqtt_tho "cuu-tro/cam-bien/$TRAM/muc-nuoc" "$(ban_tin 999 "$(iso -600)")")"
check "gửi lại đúng bản tin mới nhất" da-gui "$(mqtt_tho "cuu-tro/cam-bien/$TRAM/muc-nuoc" "$(ban_tin 412.5 "$t5")")"
check "gửi bản tin sai đơn vị" da-gui "$(mqtt_tho "cuu-tro/cam-bien/$TRAM/muc-nuoc" "{\"ma_tram\":\"$TRAM\",\"gia_tri\":1,\"don_vi\":\"m\",\"thoi_diem\":\"$(iso 0)\"}")"
sleep 3
r=$(thuc_the "$TOK")
check "gửi bù/gửi lại/bản tin sai không làm thực thể đổi (vẫn 412.5, cùng observedAt)" "412.5 nguy_hiem True" \
  "$(cut -d' ' -f1,2 <<<"$r") $(cung_luc "${r##* }" "$t5")"
check "bản tin gửi bù vẫn vào sensor_readings (consumer ghi-csdl độc lập)" 999.00 \
  "$(sql <<<"SELECT r.value FROM cuu_tro.sensor_readings r JOIN cuu_tro.sensors s ON s.id = r.sensor_id WHERE s.code = '$TRAM' ORDER BY r.received_at DESC LIMIT 1;")"

# ---------- (6) Scorpio dừng rồi chạy lại ----------
docker compose stop scorpio >/dev/null 2>&1
t6=$(iso 0)
check "Scorpio dừng: vẫn nhận bản tin (NATS lưu)" da-gui "$(mqtt_tho "cuu-tro/cam-bien/$TRAM/muc-nuoc" "$(ban_tin 388 "$t6")")"
# Đọc log vào biến rồi mới grep: "logs | grep -q" với pipefail báo lỗi khi grep thoát sớm (SIGPIPE)
bao_cho() { local l; l=$(docker compose logs --since 2m cuu-tro-ban-sao-so 2>/dev/null); [[ $l == *"chưa ghi được $ID"* ]] && echo True || echo False; }
for _ in $(seq 1 20); do [ "$(bao_cho)" = True ] && break; sleep 0.5; done
check "consumer báo chưa ghi được và hẹn giao lại" True "$(bao_cho)"
docker compose start scorpio >/dev/null 2>&1
for _ in $(seq 1 90); do [ "$(docker compose ps --format '{{.Health}}' scorpio)" = healthy ] && break; sleep 2; done
check "Scorpio chạy lại, healthy" healthy "$(docker compose ps --format '{{.Health}}' scorpio)"
cho=$(cho_thuc_the "$TOK" 388.0 "$t6" 240)
check "sau khi Scorpio chạy lại: thực thể nhận bản tin đã chờ (388 cm, canh_bao)" "388.0 canh_bao" \
  "$([ "$cho" != het-gio ] && thuc_the "$TOK" | cut -d' ' -f1,2 || echo "het-gio $(thuc_the "$TOK")")"
for _ in $(seq 1 20); do
  du=$(jf '" ".join(str(c[k]) for a in d["account_details"] for s in a["stream_detail"] if s["name"] == "CUU_TRO_CAM_BIEN" for c in s["consumer_detail"] if c["name"] == "ban-sao-so" for k in ("num_pending", "num_ack_pending"))' <<<"$(jsz)")
  [ "$du" = "0 0" ] && break
  sleep 1
done
check "consumer ban-sao-so không tồn đọng" "0 0" "$du"
check "consumer cuu-tro-ban-sao-so vẫn chạy" running "$(docker compose ps --format '{{.State}}' cuu-tro-ban-sao-so)"
check "cả lượt smoke: không bản tin hợp lệ nào bị bỏ vì lỗi Scorpio (Scorpio dừng chỉ làm giao lại)" 0 "$(bo_vi_scorpio)"
exit $fail
