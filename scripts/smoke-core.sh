#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử các dịch vụ dữ liệu và quy trình của profile core (#11):
# (1) Hasura: chạy bằng role hasura (không phải superuser), console tắt, admin secret lấy từ
#     OpenBao, nhận JWT Keycloak (kiểm lại chữ ký, đọc claim https://hasura.io/jwt/claims),
#     từ chối token giả; (2) SeaweedFS S3: khóa từ OpenBao ghi/đọc/xóa được, khóa sai bị 403;
# (3) Temporal frontend SERVING, namespace default có; (4) NATS JetStream bật, có giới hạn; MQTT và
#     cổng client bắt buộc xác thực, user thiết bị chỉ qua MQTT, user backend chỉ qua NATS thường (#30);
# (5) docker compose không truyền bí mật đã chuyển qua environment.
# Gọi thẳng cổng 127.0.0.1 của dịch vụ (route APISIX /graphql, /files, /workflow là việc của #12).
# Dùng: make up && bash scripts/smoke-core.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

ADDR="http://127.0.0.1:${OPENBAO_PORT:-8200}"
DIR="${OPENBAO_LOCAL_DIR:-./.data/openbao}"
KC="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-disaster}"
HS="http://127.0.0.1:${HASURA_PORT:-8081}"
S3="http://127.0.0.1:${SEAWEEDFS_S3_PORT:-8333}"
fail=0

check() { # check <tên> <mong đợi> <thực tế>
  if [ "$2" = "$3" ]; then echo "PASS  $1 → $3"; else echo "FAIL  $1 → $3 (mong đợi $2)"; fail=1; fi
}
# kv <đường dẫn> <khóa>: đọc bí mật bằng root token máy dev (token không nằm trên dòng lệnh)
kv() {
  curl -s -K <(printf 'header = "X-Vault-Token: %s"\n' "$(cat "$DIR/root.token")") "$ADDR/v1/secret/data/$1" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["data"]["data"][sys.argv[1]])' "$2"
}
jfield() { python3 -c 'import sys,json; d=json.load(sys.stdin); print(eval(sys.argv[1], {"d": d}))' "$1"; }

# ---------- (1) Hasura ----------
code=$(curl -s -o /dev/null -w '%{http_code}' "$HS/healthz")
check "Hasura /healthz" 200 "$code"
code=$(curl -s -o /dev/null -w '%{http_code}' "$HS/console")
check "Hasura console tắt (Tầng 1 headless)" 404 "$code"

admin=$(kv core/hasura admin_secret)
q='{"type":"run_sql","args":{"source":"default","sql":"SELECT current_user, (SELECT rolsuper FROM pg_roles WHERE rolname = current_user)","read_only":true}}'
out=$(curl -s -K <(printf 'header = "X-Hasura-Admin-Secret: %s"\n' "$admin") -H 'Content-Type: application/json' -d "$q" "$HS/v2/query")
check "Hasura: admin secret từ OpenBao, kết nối DB bằng role riêng" "${HASURA_DB_USER:-hasura} f" \
  "$(jfield '" ".join(d["result"][1])' <<<"$out" 2>/dev/null || echo "$out")"
code=$(curl -s -o /dev/null -w '%{http_code}' -H 'X-Hasura-Admin-Secret: sai' -H 'Content-Type: application/json' -d "$q" "$HS/v2/query")
check "Hasura: admin secret sai bị từ chối" 401 "$code"

get_token() { # get_token <username>
  curl -s -X POST "$KC/realms/$REALM/protocol/openid-connect/token" \
    -d grant_type=password -d client_id=dxos-dev-cli -d scope=openid \
    -d username="$1" --data-urlencode password="${KC_DEMO_USER_PASSWORD:?}" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])'
}
gql='{"query":"{ __typename }"}'
# User mẫu "<user>:<vai mặc định>" của ứng dụng đang chọn; mặc định của apps/cuu-tro. Ứng dụng khác đặt
# SMOKE_CORE_USERS (vd apps/muon-thiet-bi/module.env) để smoke lõi chạy được với realm của nó (#110)
for pair in ${SMOKE_CORE_USERS:-dieuphoi01:dieu-phoi cuuho01:cuu-ho}; do
  u=${pair%%:*}; want=${pair#*:}
  tok=$(get_token "$u")
  out=$(curl -s -K <(printf 'header = "Authorization: Bearer %s"\n' "$tok") -H 'Content-Type: application/json' -d "$gql" "$HS/v1/graphql")
  check "Hasura nhận JWT Keycloak của $u" query_root "$(jfield 'd.get("data",{}).get("__typename") or d' <<<"$out")"
  # Vai trò Hasura dùng = x-hasura-default-role trong token; xin vai trò khác ngoài allowed-roles bị chặn
  out=$(curl -s -K <(printf 'header = "Authorization: Bearer %s"\n' "$tok") -H 'X-Hasura-Role: admin' -H 'Content-Type: application/json' -d "$gql" "$HS/v1/graphql")
  check "Hasura chặn $u ($want) tự nâng vai trò admin" access-denied "$(jfield 'd["errors"][0]["extensions"]["code"]' <<<"$out" 2>/dev/null || echo "$out")"
done
out=$(curl -s -H 'Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.e30.gia' -H 'Content-Type: application/json' -d "$gql" "$HS/v1/graphql")
check "Hasura từ chối token giả" invalid-jwt "$(jfield 'd["errors"][0]["extensions"]["code"]' <<<"$out" 2>/dev/null || echo "$out")"

# ---------- (2) SeaweedFS S3 (ký SigV4 bằng curl --aws-sigv4; khóa đi qua file cấu hình curl) ----------
ak=$(kv core/s3 access_key); sk=$(kv core/s3 secret_key)
bucket="smoke-$(date +%s)"
s3() { # s3 <access:secret> <method> <path> [tham số curl...] → mã HTTP
  local cred=$1 method=$2 path=$3; shift 3
  curl -s -o /dev/null -w '%{http_code}' -K <(printf 'user = "%s"\n' "$cred") \
    --aws-sigv4 "aws:amz:us-east-1:s3" -X "$method" "$@" "$S3/$path"
}
check "S3 khóa sai bị từ chối" 403 "$(s3 "sai:khoa-sai" GET "")"
check "S3 (khóa OpenBao) tạo bucket $bucket" 200 "$(s3 "$ak:$sk" PUT "$bucket")"
check "S3 ghi object" 200 "$(s3 "$ak:$sk" PUT "$bucket/anh-hien-truong.txt" -H 'Content-Type: text/plain' --data-binary 'du lieu gia')"
got=$(curl -s -K <(printf 'user = "%s:%s"\n' "$ak" "$sk") --aws-sigv4 "aws:amz:us-east-1:s3" "$S3/$bucket/anh-hien-truong.txt")
check "S3 đọc lại đúng nội dung" "du lieu gia" "$got"
check "S3 xóa object" 204 "$(s3 "$ak:$sk" DELETE "$bucket/anh-hien-truong.txt")"
check "S3 xóa bucket" 204 "$(s3 "$ak:$sk" DELETE "$bucket")"
sha() { python3 -c 'import sys,hashlib; print(hashlib.sha256(sys.stdin.read().encode()).hexdigest()[:12])'; }
in_sw=$(docker compose exec -T seaweedfs cat /run/secrets/dxos/s3.json | python3 -c 'import sys,json; print(json.load(sys.stdin)["identities"][0]["credentials"][0]["secretKey"], end="")' | sha)
check "SeaweedFS chạy bằng khóa S3 từ OpenBao" "$(printf '%s' "$sk" | sha)" "$in_sw"

# ---------- (3) Temporal ----------
out=$(docker compose exec -T temporal sh -c 'temporal operator cluster health --address temporal:7233' 2>&1 || true)
case $out in *SERVING*) r=SERVING ;; *) r="$out" ;; esac
check "Temporal frontend" SERVING "$r"
out=$(docker compose exec -T temporal sh -c 'temporal operator namespace describe --address temporal:7233 -n default -o json' 2>&1 || true)
check "Temporal namespace default" default "$(jfield 'd["namespaceInfo"]["name"]' <<<"$out" 2>/dev/null || echo "$out")"
out=$(docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d postgres -tA -c "SELECT string_agg(datname || '"'"':'"'"' || pg_get_userbyid(datdba), '"'"' '"'"' ORDER BY datname) FROM pg_database WHERE datname LIKE '"'"'temporal%'"'"'"')
check "CSDL Temporal thuộc role riêng" "temporal:${TEMPORAL_DB_USER:-temporal} temporal_visibility:${TEMPORAL_DB_USER:-temporal}" "$out"

# ---------- (4) NATS ----------
out=$(docker compose exec -T nats wget -qO- http://127.0.0.1:8222/jsz 2>&1 || true)
check "NATS JetStream bật" True "$(jfield '"config" in d and not d.get("disabled", False)' <<<"$out" 2>/dev/null || echo "$out")"
# Xác thực bắt buộc (#30): user/mật khẩu trong OpenBao secret/app/<DXOS_APP>/nats, render vào
# auth.conf của NATS; <APP>-thiet-bi chỉ vào được qua MQTT, <APP>-app chỉ qua cổng NATS thường.
APP="${DXOS_APP:-cuu-tro}"
NATS_APP_PW=$(kv "app/$APP/nats" app_password)
NATS_DEV_PW=$(kv "app/$APP/nats" device_password)
# mqtt_connect <user|-> <mật khẩu>: MQTT 3.1.1 CONNECT → in CONNACK-<mã> (0 = nhận, 4/5 = từ chối)
# hoặc "dong-ket-noi" khi server đóng kết nối không trả CONNACK. Mật khẩu đi qua stdin.
mqtt_connect() {
  python3 - "${NATS_MQTT_PORT:-1883}" "$1" <<PY
import socket, sys
port, user = int(sys.argv[1]), sys.argv[2]
pw = """$2""".encode()
cid = b"dxos-smoke"
flags = 0x02 | ((0xC0) if user != "-" else 0)  # clean session (+ username + password)
var = b"\x00\x04MQTT\x04" + bytes([flags]) + b"\x00\x1e"
payload = len(cid).to_bytes(2, "big") + cid
if user != "-":
    payload += len(user).to_bytes(2, "big") + user.encode() + len(pw).to_bytes(2, "big") + pw
pkt = b"\x10" + bytes([len(var) + len(payload)]) + var + payload
try:
    s = socket.create_connection(("127.0.0.1", port), timeout=5)
    s.sendall(pkt); ack = s.recv(4); s.close()
    if not ack:
        print("dong-ket-noi")
    else:
        print("CONNACK-%d" % ack[3] if ack[:1] == b"\x20" and len(ack) == 4 else "tra-loi-la:" + ack.hex())
except OSError as e:
    print("loi:" + str(e))
PY
}
check "NATS MQTT cổng ${NATS_MQTT_PORT:-1883}: CONNECT không xác thực bị từ chối" CONNACK-5 "$(mqtt_connect - '')"
check "NATS MQTT: sai mật khẩu bị từ chối" CONNACK-5 "$(mqtt_connect "$APP-thiet-bi" sai-mat-khau)"
check "NATS MQTT: user $APP-thiet-bi đúng mật khẩu được nhận" CONNACK-0 "$(mqtt_connect "$APP-thiet-bi" "$NATS_DEV_PW")"
check "NATS MQTT: user backend $APP-app không được vào qua MQTT" CONNACK-5 "$(mqtt_connect "$APP-app" "$NATS_APP_PW")"

# nats_connect <user|-> <mật khẩu>: giao thức NATS: INFO → CONNECT (verbose) + PING → in OK hoặc lỗi -ERR
nats_connect() {
  python3 - "${NATS_PORT:-4222}" "$1" <<PY
import json, socket, sys
port, user = int(sys.argv[1]), sys.argv[2]
opts = {"verbose": False, "pedantic": False, "name": "dxos-smoke", "lang": "python", "version": "0"}
if user != "-":
    opts.update(user=user, **{"pass": """$2"""})
try:
    s = socket.create_connection(("127.0.0.1", port), timeout=5)
    f = s.makefile("rb")
    if not f.readline().startswith(b"INFO"):
        print("khong-co-INFO"); sys.exit()
    s.sendall(b"CONNECT " + json.dumps(opts).encode() + b"\r\nPING\r\n")
    line = f.readline().decode().strip()
    print("OK" if line == "PONG" else line or "dong-ket-noi")
    s.close()
except OSError as e:
    print("loi:" + str(e))
PY
}
check "NATS cổng client ${NATS_PORT:-4222}: không xác thực bị từ chối" "-ERR 'Authorization Violation'" "$(nats_connect - '')"
check "NATS cổng client: user $APP-app đúng mật khẩu được nhận" OK "$(nats_connect "$APP-app" "$NATS_APP_PW")"
check "NATS cổng client: user thiết bị chỉ được dùng MQTT" "-ERR 'Authorization Violation'" "$(nats_connect "$APP-thiet-bi" "$NATS_DEV_PW")"
lim=$(jfield '0 < d["config"]["max_memory"] <= 1 << 30 and 0 < d["config"]["max_storage"] <= 8 << 30' <<<"$out" 2>/dev/null || echo "$out")
check "NATS JetStream có giới hạn bộ nhớ/ổ (mặc định 64MB/1GB)" True "$lim"

# ---------- (5) Không lộ bí mật ----------
leak=$(docker compose --profile core config 2>/dev/null | grep -cE 'POSTGRES_PASSWORD:|POSTGRES_PWD:|HASURA_GRAPHQL_ADMIN_SECRET:|HASURA_GRAPHQL_DATABASE_URL:|"accessKey"|"secretKey"' || true)
check "docker-compose không truyền mật khẩu DB, admin secret Hasura, khóa S3 qua environment" 0 "$leak"
exit $fail
