#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử OpenBao (#14): chế độ server (không dev), đã mở khóa, AppRole chỉ đọc đúng phần
# của mình, và dịch vụ lõi chạy bằng bí mật lấy từ OpenBao chứ không từ .env.
# Dùng: make up && bash scripts/smoke-openbao.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

ADDR="http://127.0.0.1:${OPENBAO_PORT:-8200}"
DIR="${OPENBAO_LOCAL_DIR:-./.data/openbao}"
KC="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-disaster}"
fail=0

check() { # check <tên> <mong đợi> <thực tế>
  if [ "$2" = "$3" ]; then echo "PASS  $1 → $3"; else echo "FAIL  $1 → $3 (mong đợi $2)"; fail=1; fi
}
# bao_get <token> <path> → mã HTTP vào CODE, body vào OUT. Token không nằm trên dòng lệnh.
CODE='' OUT=''
bao_get() {
  local f
  f=$(mktemp)
  CODE=$(curl -s -o "$f" -w '%{http_code}' -K <(printf 'header = "X-Vault-Token: %s"\n' "$1") "$ADDR/v1/$2")
  OUT=$(cat "$f"); rm -f "$f"
}
sha() { python3 -c 'import sys,hashlib; print(hashlib.sha256(sys.stdin.read().encode()).hexdigest()[:12])'; }

st=$(curl -s "$ADDR/v1/sys/seal-status")
check "OpenBao đã init, đã mở khóa" "True False" "$(python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["initialized"], d["sealed"])' <<<"$st")"
check "OpenBao lưu trữ raft (không phải dev/inmem)" raft "$(python3 -c 'import sys,json; print(json.load(sys.stdin).get("storage_type"))' <<<"$st")"

# Đăng nhập AppRole apisix bằng đúng file mà bao-agent-apisix dùng
login=$(python3 -c 'import sys,json; print(json.dumps({"role_id":open(sys.argv[1]).read().strip(),"secret_id":open(sys.argv[2]).read().strip()}))' \
  "$DIR/approle/apisix/role_id" "$DIR/approle/apisix/secret_id" \
  | curl -s -X POST --data-binary @- "$ADDR/v1/auth/approle/login")
tok=$(python3 -c 'import sys,json; print(json.load(sys.stdin)["auth"]["client_token"])' <<<"$login")
bao_get "$tok" secret/data/core/gateway
check "AppRole apisix đọc secret/core/gateway" 200 "$CODE"
gw_secret=$(python3 -c 'import sys,json; print(json.load(sys.stdin)["data"]["data"]["client_secret"])' <<<"$OUT")
bao_get "$tok" secret/data/core/keycloak-db
check "AppRole apisix KHÔNG đọc được secret/core/keycloak-db" 403 "$CODE"
bao_get "$tok" secret/data/core/s3
check "AppRole apisix KHÔNG đọc được secret/core/s3" 403 "$CODE"

# Bí mật dịch vụ thật sự dùng = bí mật trong OpenBao (so băm, không in giá trị)
in_apisix=$(docker compose exec -T apisix cat /run/secrets/dxos/KC_GATEWAY_CLIENT_SECRET | sha)
check "APISIX dùng client secret từ OpenBao" "$(printf '%s' "$gw_secret" | sha)" "$in_apisix"
in_kc=$(docker compose exec -T keycloak bash -c 'tr "\0" "\n" < /proc/1/environ | sed -n "s/^KC_DB_PASSWORD=//p"' | tr -d '\n' | sha)
root=$(cat "$DIR/root.token")
bao_get "$root" secret/data/core/keycloak-db
kc_db=$(python3 -c 'import sys,json; print(json.load(sys.stdin)["data"]["data"]["password"])' <<<"$OUT")
check "Keycloak kết nối DB bằng mật khẩu từ OpenBao" "$(printf '%s' "$kc_db" | sha)" "$in_kc"

# Keycloak chấp nhận đúng secret trong OpenBao cho client dxos-gateway (client_credentials)
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$KC/realms/$REALM/protocol/openid-connect/token" \
  -d grant_type=client_credentials -d client_id=dxos-gateway --data-urlencode client_secret@<(printf '%s' "$gw_secret"))
check "Keycloak: dxos-gateway + secret từ OpenBao lấy được token" 200 "$code"

# Bí mật đã chuyển không còn trong cấu hình container
leak=$(docker compose --profile core config 2>/dev/null | grep -cE 'KC_DB_PASSWORD:|KC_GATEWAY_CLIENT_SECRET:|KC_BOOTSTRAP_ADMIN_PASSWORD:|KEYCLOAK_DB_PASSWORD:' || true)
check "docker-compose không truyền bí mật đã chuyển qua environment" 0 "$leak"
exit $fail
