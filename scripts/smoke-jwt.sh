#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử nhanh profile core: gọi route mẫu /api/v1/me qua APISIX
# (1) không token → 401, (2) token giả → 401, (3) token Keycloak hợp lệ → 200.
# Dùng: make up && bash scripts/smoke-jwt.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

KC="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-disaster}"
GW="http://localhost:${APISIX_PORT:-9080}"
USER_NAME="${1:-dieuphoi01}"
fail=0

check() { # check <tên> <mã mong đợi> <mã thực tế>
  if [ "$2" = "$3" ]; then echo "PASS  $1 → HTTP $3"; else echo "FAIL  $1 → HTTP $3 (mong đợi $2)"; fail=1; fi
}

code=$(curl -s -o /dev/null -w '%{http_code}' "$GW/healthz")
check "GET /healthz (không cần token)" 200 "$code"

code=$(curl -s -o /dev/null -w '%{http_code}' "$GW/api/v1/me")
check "GET /api/v1/me không token" 401 "$code"

code=$(curl -s -o /dev/null -w '%{http_code}' -H 'Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.e30.gia' "$GW/api/v1/me")
check "GET /api/v1/me token giả" 401 "$code"

token=$(curl -s -X POST "$KC/realms/$REALM/protocol/openid-connect/token" \
  -d grant_type=password -d client_id=dxos-dev-cli -d scope=openid \
  -d username="$USER_NAME" --data-urlencode password="${KC_DEMO_USER_PASSWORD:?}" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
echo "Đã lấy access token cho $USER_NAME (${#token} ký tự)"

body=$(curl -s -w '\n%{http_code}' -H "Authorization: Bearer $token" "$GW/api/v1/me")
check "GET /api/v1/me token Keycloak" 200 "$(tail -n1 <<<"$body")"
echo "      body: $(sed '$d' <<<"$body")"

roles=$(python3 -c 'import sys,json,base64; p=sys.argv[1].split(".")[1]; p+="="*(-len(p)%4); print(",".join(json.loads(base64.urlsafe_b64decode(p))["realm_access"]["roles"]))' "$token")
echo "      realm_access.roles trong token: $roles"
exit $fail
