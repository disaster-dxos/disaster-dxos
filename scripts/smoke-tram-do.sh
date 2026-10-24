#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử lớp trạm đo mực nước của web điều phối (#62), gọi THẬT qua APISIX đúng như trình duyệt (đường dẫn
# NGSI-LD và query GraphQL đọc NGUYÊN VĂN từ apps/cuu-tro/web/utils/tram-do.ts):
# (1) gateway: không token → 401; preflight CORS từ origin của web cho phép Authorization; trang chủ web có
#     CSP connect-src tới gateway (fetch được);
# (2) bộ giả lập gửi một bản tin mới cho mọi trạm mẫu → bản sao số NGSI-LD cập nhật; danh sách trạm (GeoJSON)
#     trả 200 cho cả 3 vai, có mọi trạm mực nước vừa gửi, mỗi feature có mã, tọa độ, mực nước, cấp báo động hợp lệ;
#     giá trị và cấp báo động của từng trạm khớp lần đo mới nhất trong CSDL (màu trên bản đồ = popup);
# (3) popup: chuỗi đo 24 giờ (GraphQL sensor_readings) chạy được với vai mặc định của cả 3 vai, mới nhất
#     trước, lần đo đầu là bản tin vừa gửi; số dòng khớp CSDL (tối đa giới hạn của web).
# Bản tin gửi theo kịch bản binh-thuong của bộ giả lập (dữ liệu giả), chạy lại nhiều lần vẫn đúng.
# Dùng: make up && bash scripts/smoke-tram-do.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

KC="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-disaster}"
GW="http://localhost:${APISIX_PORT:-9080}"
ORIGIN="${GW_CORS_ALLOW_ORIGINS:-http://localhost:3000}"; ORIGIN="${ORIGIN%%,*}"
TS_FILE=apps/cuu-tro/web/utils/tram-do.ts
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
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
jf() { python3 -c 'import sys,json; d=json.loads(sys.stdin.read()); print(eval(sys.argv[1], {"d": d}))' "$1"; }
sql() { docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -q -v ON_ERROR_STOP=1'; }
gia_lap() { docker compose --profile core --profile app run --rm --no-deps -T cuu-tro-gia-lap python -m cuu_tro_workflow.gia_lap "$@" 2>&1 | grep '^{'; }
# web_ts <duong|query>: đường dẫn NGSI-LD hoặc query lịch sử đúng như web dùng
web_ts() {
  python3 - "$TS_FILE" "$1" <<'PY'
import re, sys
src = open(sys.argv[1], encoding="utf-8").read()
hang = {k: re.search(rf"export const {k} = (\d+)", src).group(1) for k in ("SO_TRAM_TOI_DA", "SO_DIEM_TOI_DA")}
ten = "DUONG_TRAM" if sys.argv[2] == "duong" else "Q_LICH_SU_TRAM"
s = re.search(rf"export const {ten} = `(.*?)`", src, re.S).group(1)
for k, v in hang.items():
    s = s.replace("${%s}" % k, v)
print(s)
PY
}
DUONG=$(web_ts duong)
ACCEPT=$(sed -n "s/^export const ACCEPT_TRAM = '\(.*\)'$/\1/p" "$TS_FILE")
# tram <token|-> → body vào $TMP/tram.json, in mã HTTP
tram() {
  if [ "$1" = - ]; then curl -s -o "$TMP/tram.json" -w '%{http_code}' -H "Accept: $ACCEPT" "$GW$DUONG"
  else curl -s -o "$TMP/tram.json" -w '%{http_code}' -K <(printf 'header = "Authorization: Bearer %s"\n' "$1") -H "Accept: $ACCEPT" "$GW$DUONG"; fi
}
# lich_su <token> <mã trạm>: query lịch sử của web, KHÔNG gửi X-Hasura-Role (như web: vai mặc định trong token)
lich_su() {
  local body
  body=$(python3 -c 'import json,sys; from datetime import datetime,timedelta,timezone; print(json.dumps({"query": sys.argv[1], "variables": {"ma": sys.argv[2], "tu": (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()}}))' "$(web_ts query)" "$2")
  curl -s -K <(printf 'header = "Authorization: Bearer %s"\n' "$1") -H 'Content-Type: application/json' -d "$body" "$GW/graphql"
}

D=$(get_token dieuphoi01); C=$(get_token cuuho01); T=$(get_token tinhnguyen01)

# ---------------- (1) Gateway ----------------
check "đường dẫn web đọc từ tram-do.ts: entities WaterLevelStation, GeoJSON" "/ngsi-ld/v1/entities?type=WaterLevelStation application/geo+json" \
  "${DUONG%%&*} $ACCEPT"
check "danh sách trạm không token → APISIX 401" 401 "$(tram -)"
check "preflight CORS từ origin web cho phép Authorization" True "$(curl -s -o /dev/null -D - -X OPTIONS "$GW$DUONG" -H "Origin: $ORIGIN" \
  -H 'Access-Control-Request-Method: GET' -H 'Access-Control-Request-Headers: authorization' \
  | python3 -c 'import sys; h={l.split(":",1)[0].strip().lower(): l.split(":",1)[1].strip() for l in sys.stdin if ":" in l}; print(h.get("access-control-allow-origin") == sys.argv[1] and "authorization" in h.get("access-control-allow-headers","").lower())' "$ORIGIN")"
check "CSP của web cho phép fetch tới gateway (connect-src)" True "$(curl -s -o /dev/null -D - "$GW/" \
  | python3 -c 'import sys,re; c=next((l.split(":",1)[1] for l in sys.stdin if l.lower().startswith("content-security-policy:")), ""); m=re.search(r"connect-src([^;]*)", c); print(bool(m) and ("'"'"'self'"'"'" in m.group(1) or sys.argv[1] in m.group(1)))' "$GW")"

# ---------------- (2) Danh sách trạm ----------------
gia_lap --mot-lan --kich-ban binh-thuong >"$TMP/gui.jsonl"
check "bộ giả lập gửi bản tin cho mọi trạm mẫu" True "$(python3 -c 'import sys,json; print(len([l for l in open(sys.argv[1]) if l.strip()]) >= 9)' "$TMP/gui.jsonl")"
# Chờ bản sao số nhận đủ giá trị vừa gửi của các trạm mực nước (tối đa 40 giây)
dong_bo=False
for _ in $(seq 1 40); do
  if [ "$(tram "$D")" = 200 ] && [ "$(python3 - "$TMP/gui.jsonl" "$TMP/tram.json" <<'PY'
import json, sys
gui = {}
for l in open(sys.argv[1]):
    if l.strip():
        b = json.loads(l)
        if b.get("don_vi") == "cm": gui[b["ma_tram"]] = float(b["gia_tri"])
co = {f["properties"]["stationCode"]: f["properties"].get("waterLevel") for f in json.load(open(sys.argv[2]))["features"]}
print(bool(gui) and all(co.get(m) is not None and abs(float(co[m]) - v) < 0.01 for m, v in gui.items()))
PY
)" = True ]; then dong_bo=True; break; fi
  sleep 1
done
check "bản sao số NGSI-LD nhận giá trị mới của mọi trạm mực nước" True "$dong_bo"
GUI=$(python3 -c 'import json,sys; print(",".join(sorted({json.loads(l)["ma_tram"] for l in open(sys.argv[1]) if l.strip() and json.loads(l).get("don_vi") == "cm"})))' "$TMP/gui.jsonl")
MUC_NUOC=$(sql <<<"SELECT string_agg(code, ',') FROM cuu_tro.sensors WHERE kind = 'muc_nuoc';")
for vt in "dieu-phoi:$D" "cuu-ho:$C" "tinh-nguyen:$T"; do
  u=${vt%%:*}; tok=${vt#*:}
  code=$(tram "$tok")
  check "danh sách trạm (vai $u) → 200 FeatureCollection, có mọi trạm vừa gửi, chỉ trạm mực nước của CSDL" "200 FeatureCollection True True" \
    "$code $(python3 -c '
import json, sys
d = json.load(open(sys.argv[1])); ma = {f["properties"]["stationCode"] for f in d["features"]}
print(d["type"], set(sys.argv[2].split(",")) <= ma, ma <= set(sys.argv[3].split(",")))' "$TMP/tram.json" "$GUI" "$MUC_NUOC")"
done
check "mỗi feature: mã, tọa độ Point hợp lệ, mực nước số, cấp báo động hợp lệ, có ngưỡng" True "$(python3 -c '
import json, sys
fs = json.load(open(sys.argv[1]))["features"]
def ok(f):
    p, g = f["properties"], f["geometry"]
    return (isinstance(p.get("stationCode"), str) and g["type"] == "Point" and abs(g["coordinates"][0]) <= 180
            and abs(g["coordinates"][1]) <= 90 and isinstance(p.get("waterLevel"), (int, float))
            and p.get("alertLevel") in ("binh_thuong", "canh_bao", "nguy_hiem")
            and isinstance(p.get("warningThreshold"), (int, float)) and isinstance(p.get("dangerThreshold"), (int, float)))
print(bool(fs) and all(ok(f) for f in fs))' "$TMP/tram.json")"
sql <<<"SELECT s.code || '|' || r.value::float8 || '|' || r.level FROM cuu_tro.sensors s JOIN LATERAL (SELECT value, level FROM cuu_tro.sensor_readings WHERE sensor_id = s.id ORDER BY observed_at DESC LIMIT 1) r ON true WHERE s.kind = 'muc_nuoc';" >"$TMP/csdl.txt"
check "mực nước + cấp báo động trên bản đồ khớp lần đo mới nhất trong CSDL (mọi trạm vừa gửi)" khop "$(python3 -c '
import json, sys
csdl = {l.split("|")[0]: (float(l.split("|")[1]), l.split("|")[2].strip()) for l in open(sys.argv[2]) if l.strip()}
gui = set(sys.argv[3].split(","))
lech = [f["properties"]["stationCode"] for f in json.load(open(sys.argv[1]))["features"] if f["properties"]["stationCode"] in gui
        and csdl.get(f["properties"]["stationCode"]) != (float(f["properties"]["waterLevel"]), f["properties"]["alertLevel"])]
print("khop" if not lech else "lech: " + ",".join(lech))' "$TMP/tram.json" "$TMP/csdl.txt" "$GUI")"

# ---------------- (3) Chuỗi đo cho biểu đồ nhỏ ----------------
MA=$(python3 -c 'import json,sys; print(next(json.loads(l)["ma_tram"] for l in open(sys.argv[1]) if l.strip() and json.loads(l).get("don_vi") == "cm"))' "$TMP/gui.jsonl")
GT=$(python3 -c 'import json,sys; print(next(float(json.loads(l)["gia_tri"]) for l in open(sys.argv[1]) if l.strip() and json.loads(l).get("ma_tram") == sys.argv[2]))' "$TMP/gui.jsonl" "$MA")
GIOI_HAN=$(sed -n 's/^export const SO_DIEM_TOI_DA = \([0-9]*\)$/\1/p' "$TS_FILE")
N=$(sql <<<"SELECT least(count(*), $GIOI_HAN) FROM cuu_tro.sensor_readings r JOIN cuu_tro.sensors s ON s.id = r.sensor_id WHERE s.code = '$MA' AND r.observed_at >= now() - interval '24 hours';")
for vt in "dieu-phoi:$D" "cuu-ho:$C" "tinh-nguyen:$T"; do
  u=${vt%%:*}
  r=$(lich_su "${vt#*:}" "$MA")
  check "chuỗi đo 24 giờ trạm $MA (vai mặc định của $u): mới nhất trước, đầu là bản tin vừa gửi, $N dòng" "True $N" \
    "$(jf '"%s %d" % ((lambda h: bool(h) and abs(float(h[0]["value"]) - '"$GT"') < 0.01 and all(a["observed_at"] >= b["observed_at"] for a, b in zip(h, h[1:])))(d["data"]["sensor_readings"]), len(d["data"]["sensor_readings"]))' <<<"$r" 2>/dev/null || echo "$r")"
done

if [ "$fail" -ne 0 ]; then echo "smoke-tram-do: CÓ LỖI"; exit 1; fi
echo "smoke-tram-do: tất cả đều đạt"
