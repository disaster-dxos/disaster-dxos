#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử nhanh profile core: gọi route mẫu /api/v1/me qua APISIX
# (1) không token → 401, (2) token giả → 401, (3) token Keycloak hợp lệ → 200,
# (4) claim https://hasura.io/jwt/claims đúng cho mỗi user mẫu (#13),
# (5) đăng nhập trình duyệt: dieu-phoi bị bắt cài OTP, vai trò khác thì không (#13).
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
  local got=$3; [[ $3 =~ ^[0-9]{3}$ ]] && got="HTTP $3"
  if [ "$2" = "$3" ]; then echo "PASS  $1 → $got"; else echo "FAIL  $1 → $got (mong đợi $2)"; fail=1; fi
}

code=$(curl -s -o /dev/null -w '%{http_code}' "$GW/healthz")
check "GET /healthz (không cần token)" 200 "$code"

code=$(curl -s -o /dev/null -w '%{http_code}' "$GW/api/v1/me")
check "GET /api/v1/me không token" 401 "$code"

code=$(curl -s -o /dev/null -w '%{http_code}' -H 'Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.e30.gia' "$GW/api/v1/me")
check "GET /api/v1/me token giả" 401 "$code"

get_token() { # get_token <username>
  curl -s -X POST "$KC/realms/$REALM/protocol/openid-connect/token" \
    -d grant_type=password -d client_id=dxos-dev-cli -d scope=openid \
    -d username="$1" --data-urlencode password="${KC_DEMO_USER_PASSWORD:?}" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])'
}

token=$(get_token "$USER_NAME")
echo "Đã lấy access token cho $USER_NAME (${#token} ký tự)"

body=$(curl -s -w '\n%{http_code}' -H "Authorization: Bearer $token" "$GW/api/v1/me")
check "GET /api/v1/me token Keycloak" 200 "$(tail -n1 <<<"$body")"
echo "      body: $(sed '$d' <<<"$body")"

roles=$(python3 -c 'import sys,json,base64; p=sys.argv[1].split(".")[1]; p+="="*(-len(p)%4); print(",".join(json.loads(base64.urlsafe_b64decode(p))["realm_access"]["roles"]))' "$token")
echo "      realm_access.roles trong token: $roles"

# (4) Claim cho Hasura: vai trò mặc định lấy từ thuộc tính hasura_default_role, không từ roles[0]
for pair in dieuphoi01:dieu-phoi cuuho01:cuu-ho tinhnguyen01:tinh-nguyen; do
  u=${pair%%:*}; want=${pair#*:}
  out=$(python3 - "$(get_token "$u")" "$want" <<'PY'
import sys, json, base64
p = sys.argv[1].split(".")[1]; p += "=" * (-len(p) % 4)
t = json.loads(base64.urlsafe_b64decode(p))
c = t.get("https://hasura.io/jwt/claims", {})
ok = (c.get("x-hasura-default-role") == sys.argv[2]
      and c.get("x-hasura-user-id") == t["sub"]
      and sys.argv[2] in c.get("x-hasura-allowed-roles", []))
print(("OK " if ok else "SAI ") + json.dumps(c, ensure_ascii=False))
PY
)
  check "claim Hasura của $u (default-role=$want)" OK "${out%% *}"
  echo "      ${out#* }"
done

# (5) Đăng nhập trình duyệt (client dxos-web, PKCE): sau mật khẩu, dieu-phoi phải sang
# trang cài OTP (CONFIGURE_TOTP); cuu-ho đi thẳng về redirect_uri.
browser_login() { # browser_login <username> → in URL Keycloak chuyển hướng tới sau khi nhập mật khẩu
  local jar verifier challenge page action
  jar=$(mktemp)
  verifier=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')
  challenge=$(python3 -c 'import sys,hashlib,base64; print(base64.urlsafe_b64encode(hashlib.sha256(sys.argv[1].encode()).digest()).rstrip(b"=").decode())' "$verifier")
  page=$(curl -s -c "$jar" -b "$jar" "$KC/realms/$REALM/protocol/openid-connect/auth?client_id=dxos-web&response_type=code&scope=openid&redirect_uri=http%3A%2F%2Flocalhost%3A3000%2Fcb&state=smoke&code_challenge=$challenge&code_challenge_method=S256")
  action=$(python3 -c 'import sys,re,html; print(html.unescape(re.search(r"action=\"([^\"]+)\"", sys.stdin.read()).group(1)))' <<<"$page")
  curl -s -c "$jar" -b "$jar" -o /dev/null -w '%{redirect_url}' -X POST "$action" \
    -d username="$1" --data-urlencode password="${KC_DEMO_USER_PASSWORD:?}"
  rm -f "$jar"
}
case $(browser_login dieuphoi01) in *execution=CONFIGURE_TOTP*) r=OTP ;; *) r=khong-OTP ;; esac
check "đăng nhập web dieuphoi01 bị bắt cài OTP" OTP "$r"
case $(browser_login cuuho01) in http://localhost:3000/cb*) r=vao-thang ;; *) r=bi-chan ;; esac
check "đăng nhập web cuuho01 không bị hỏi OTP" vao-thang "$r"
exit $fail
