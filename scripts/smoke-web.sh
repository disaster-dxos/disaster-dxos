#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử web điều phối (#64) mở qua API Gateway như người dùng:
# (1) trang chủ và đường SPA (/auth/callback, kể cả tham số iss của Keycloak) qua APISIX trả 200 HTML;
# (2) tệp tĩnh (/_nuxt/*.js, *.css, /logo/favicon.ico) tải được, đúng content-type, có cache;
# (3) cấu hình đăng nhập Nitro chèn vào trang: Keycloak URL/realm, client dxos-web, gateway URL;
#     Keycloak chấp nhận authorize của dxos-web với redirect_uri <gateway>/auth/callback + PKCE S256,
#     từ chối redirect_uri lạ;
# (4) header bảo mật: CSP (script-src không unsafe-inline, hash khớp script inline, frame-ancestors
#     'none'), X-Frame-Options DENY, nosniff, không lộ X-Powered-By;
# (5) gateway: WAF chặn XSS trên route web (403), chỉ GET/HEAD (POST → 404), route API vẫn được ưu tiên.
# Dùng: make up && bash scripts/smoke-web.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

KC="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-disaster}"
GW="${GATEWAY_PUBLIC_URL:-http://localhost:${APISIX_PORT:-9080}}"; GW="${GW%/}"
CLIENT=dxos-web
fail=0
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT

check() { # check <tên> <mong đợi> <thực tế>
  local got=$3; [[ $3 =~ ^[0-9]{3}$ ]] && got="HTTP $3"
  if [ "$2" = "$3" ]; then echo "PASS  $1 → $got"; else echo "FAIL  $1 → $got (mong đợi $2)"; fail=1; fi
}
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
# hdr <file header> <tên>: giá trị header (không phân biệt hoa thường), rỗng nếu không có
hdr() { grep -i "^$2:" "$1" | head -1 | cut -d: -f2- | sed 's/^ *//; s/\r$//' || true; }

# ---------- (1) trang chủ và đường SPA ----------
c=$(curl -s -D "$tmp/h" -o "$tmp/index.html" -w '%{http_code}' "$GW/")
check "GET / qua gateway" 200 "$c"
check "GET / là HTML" yes "$(hdr "$tmp/h" content-type | grep -qi '^text/html' && echo yes || echo no)"
check "trang có gốc ứng dụng Nuxt (#__nuxt)" yes "$(grep -q 'id="__nuxt"' "$tmp/index.html" && echo yes || echo no)"
check "GET /auth/callback (đường SPA) qua gateway" 200 "$(code "$GW/auth/callback")"
# Keycloak gọi lại kèm iss=<URL realm> (RFC 9207): luật SSRF/RFI của CRS không được chặn nhầm
enc() { python3 -c 'import sys,urllib.parse as u; print(u.quote(sys.argv[1], safe=""))' "$1"; }
for iss in "$KC/realms/$REALM" "http://192.0.2.10:8080/realms/$REALM"; do
  check "Keycloak gọi lại /auth/callback kèm iss=$iss không bị WAF chặn" 200 \
    "$(code "$GW/auth/callback?state=s1&session_state=s2&iss=$(enc "$iss")&code=c1")"
done
check "WAF vẫn kiểm iss: XSS trong iss bị chặn" 403 \
  "$(code "$GW/auth/callback?state=s1&iss=$(enc '<script>alert(1)</script>')&code=c1")"

# ---------- (2) tệp tĩnh ----------
js=$(grep -o 'src="/_nuxt/[^"]*\.js"' "$tmp/index.html" | head -1 | cut -d'"' -f2 || true)
css=$(grep -o 'href="/_nuxt/[^"]*\.css"' "$tmp/index.html" | head -1 | cut -d'"' -f2 || true)
check "trang tham chiếu bundle JS và CSS" yes "$([ -n "$js" ] && [ -n "$css" ] && echo yes || echo no)"
c=$(curl -s -D "$tmp/hjs" -o /dev/null -w '%{http_code}' "$GW${js:-/_nuxt/khong-co.js}")
check "GET ${js:-<bundle JS>}" 200 "$c"
check "bundle JS đúng content-type" yes "$(hdr "$tmp/hjs" content-type | grep -qi javascript && echo yes || echo no)"
check "bundle JS cache immutable" yes "$(hdr "$tmp/hjs" cache-control | grep -qi immutable && echo yes || echo no)"
check "tệp tĩnh có nosniff" nosniff "$(hdr "$tmp/hjs" x-content-type-options)"
check "GET ${css:-<CSS>}" 200 "$(code "$GW${css:-/_nuxt/khong-co.css}")"
check "GET /logo/favicon.ico" 200 "$(code "$GW/logo/favicon.ico")"

# ---------- (3) cấu hình đăng nhập ----------
cfg=$(grep -o 'window.__NUXT__.config={[^<]*' "$tmp/index.html" || true)
has() { case "$cfg" in *"$1"*) echo yes ;; *) echo no ;; esac; }
check "trang mang client_id $CLIENT" yes "$(has "keycloakClientId:\"$CLIENT\"")"
check "trang mang Keycloak $KC, realm $REALM" yes "$( [ "$(has "keycloakUrl:\"$KC\"")" = yes ] && has "keycloakRealm:\"$REALM\"" || echo no)"
check "trang mang gateway $GW" yes "$(has "gatewayUrl:\"$GW\"")"
# Web tự chuyển sang Keycloak bằng JS (middleware/auth.global.ts, utils/oidc.ts buildAuthorizeUrl);
# ở đây gọi đúng URL đó để kiểm Keycloak chấp nhận client và redirect_uri qua gateway
authz() { # authz <redirect_uri>
  curl -s -o /dev/null -w '%{http_code}' -G "$KC/realms/$REALM/protocol/openid-connect/auth" \
    --data-urlencode client_id="$CLIENT" --data-urlencode redirect_uri="$1" \
    --data-urlencode response_type=code --data-urlencode 'scope=openid profile' \
    --data-urlencode state=smoke --data-urlencode nonce=smoke \
    --data-urlencode code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM \
    --data-urlencode code_challenge_method=S256
}
check "Keycloak mở trang đăng nhập cho $CLIENT, redirect_uri $GW/auth/callback" 200 "$(authz "$GW/auth/callback")"
check "Keycloak từ chối redirect_uri lạ" 400 "$(authz "https://ke-gian.example/auth/callback")"

# ---------- (4) header bảo mật ----------
csp=$(hdr "$tmp/h" content-security-policy)
check "có Content-Security-Policy" yes "$([ -n "$csp" ] && echo yes || echo no)"
check "CSP frame-ancestors 'none'" yes "$(grep -q "frame-ancestors 'none'" <<<"$csp" && echo yes || echo no)"
check "CSP script-src không unsafe-inline/unsafe-eval" yes \
  "$(grep -o 'script-src[^;]*' <<<"$csp" | grep -q unsafe && echo no || echo yes)"
want=$(python3 - "$tmp/index.html" <<'PY'
import base64, hashlib, re, sys
html = open(sys.argv[1], encoding="utf-8").read()
for m in re.finditer(r"<script>(.*?)</script>", html, re.S):
    print("'sha256-" + base64.b64encode(hashlib.sha256(m.group(1).encode()).digest()).decode() + "'")
PY
)
ok=yes; [ -n "$want" ] || ok=no
for h in $want; do grep -qF -- "$h" <<<"$csp" || ok=no; done
check "CSP có hash đúng mọi script inline (runtimeConfig)" yes "$ok"
check "X-Frame-Options" DENY "$(hdr "$tmp/h" x-frame-options)"
check "X-Content-Type-Options" nosniff "$(hdr "$tmp/h" x-content-type-options)"
check "không lộ X-Powered-By" "" "$(hdr "$tmp/h" x-powered-by)"

# ---------- (5) gateway ----------
check "WAF chặn XSS trên route web" 403 "$(code "$GW/?q=%3Cscript%3Ealert(1)%3C%2Fscript%3E")"
check "POST / không có route (web chỉ GET/HEAD)" 404 "$(code -X POST -d x=1 "$GW/")"
check "route API vẫn ưu tiên: /graphql không token" 401 "$(code -X POST -H 'Content-Type: application/json' -d '{"query":"{__typename}"}' "$GW/graphql")"
check "route API vẫn ưu tiên: /v1/metadata bị chặn" 403 "$(code "$GW/v1/metadata")"
check "GET /healthz của gateway" 200 "$(code "$GW/healthz")"

if [ "$fail" -ne 0 ]; then echo "CÓ LỖI: xem các dòng FAIL"; exit 1; fi
echo "OK: smoke web điều phối qua gateway đạt"
