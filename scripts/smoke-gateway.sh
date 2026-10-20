#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử route API Gateway (#12), gọi qua APISIX như ứng dụng Tầng 2:
# (1) /graphql, /files/*, /workflow/*: không token → 401, token giả → 401, token Keycloak → 2xx
#     (/workflow/hello chạy workflow Hello của apps/cuu-tro qua API workflow, #29);
# (2) endpoint quản trị Hasura (/v1/metadata, /v2/query, /console) bị chặn từ ngoài;
# (3) /files: ghi/đọc qua URL presigned S3 + JWT, giới hạn kích thước request (413);
# (4) Coraza WAF + OWASP CRS: SQLi/XSS trong query bị chặn 403 (kể cả khi có token), request thường vẫn qua;
# (5) CORS: origin trong GW_CORS_ALLOW_ORIGINS được phép, origin lạ không có header cho phép;
# (6) limit-count: vượt 20 request / 10 giây vào /healthz → 429.
# Dùng: make up && bash scripts/smoke-gateway.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

KC="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-disaster}"
GW="http://localhost:${APISIX_PORT:-9080}"
ADDR="http://127.0.0.1:${OPENBAO_PORT:-8200}"
DIR="${OPENBAO_LOCAL_DIR:-./.data/openbao}"
S3="http://127.0.0.1:${SEAWEEDFS_S3_PORT:-8333}"
ORIGIN="${GW_CORS_ALLOW_ORIGINS:-http://localhost:3000}"; ORIGIN="${ORIGIN%%,*}"
FAKE='eyJhbGciOiJSUzI1NiJ9.e30.gia'
fail=0

check() { # check <tên> <mong đợi> <thực tế>
  local got=$3; [[ $3 =~ ^[0-9]{3}$ ]] && got="HTTP $3"
  if [ "$2" = "$3" ]; then echo "PASS  $1 → $got"; else echo "FAIL  $1 → $got (mong đợi $2)"; fail=1; fi
}
# code <token|-> <tham số curl...>: mã HTTP; token đi qua file cấu hình curl, không nằm trên dòng lệnh
code() {
  local tok=$1; shift
  if [ "$tok" = - ]; then curl -s -o /dev/null -w '%{http_code}' "$@"
  else curl -s -o /dev/null -w '%{http_code}' -K <(printf 'header = "Authorization: Bearer %s"\n' "$tok") "$@"; fi
}
get_token() { # get_token <username>
  curl -s -X POST "$KC/realms/$REALM/protocol/openid-connect/token" \
    -d grant_type=password -d client_id=dxos-dev-cli -d scope=openid \
    -d username="$1" --data-urlencode password="${KC_DEMO_USER_PASSWORD:?}" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])'
}
kv() { # kv <đường dẫn> <khóa>: đọc bí mật OpenBao bằng root token máy dev
  curl -s -K <(printf 'header = "X-Vault-Token: %s"\n' "$(cat "$DIR/root.token")") "$ADDR/v1/secret/data/$1" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["data"]["data"][sys.argv[1]])' "$2"
}
# presign <method> <bucket/key>: in phần query X-Amz-* của URL presigned SigV4 (5 phút). Ký cho host
# công khai của gateway (SeaweedFS đọc X-Forwarded-Host do APISIX gửi) và path S3 /<bucket>/<key>
# (không có tiền tố /files). Khóa S3 đọc từ biến môi trường, không nằm trên dòng lệnh.
# Ở Tầng 2, URL này do dịch vụ của #27 cấp; smoke tự ký để kiểm đường đi qua gateway.
presign() {
  python3 - "$1" "$2" <<'PY'
import datetime, hashlib, hmac, os, sys, urllib.parse
method, path = sys.argv[1], "/" + sys.argv[2]
ak, sk, region, host = os.environ["S3_AK"], os.environ["S3_SK"], "us-east-1", os.environ["SIGN_HOST"]
now = datetime.datetime.now(datetime.timezone.utc)
amz_date, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
scope = f"{day}/{region}/s3/aws4_request"
q = {"X-Amz-Algorithm": "AWS4-HMAC-SHA256", "X-Amz-Credential": f"{ak}/{scope}",
     "X-Amz-Date": amz_date, "X-Amz-Expires": "300", "X-Amz-SignedHeaders": "host"}
enc = lambda s: urllib.parse.quote(s, safe="-_.~")
cq = "&".join(f"{enc(k)}={enc(v)}" for k, v in sorted(q.items()))
creq = "\n".join([method, urllib.parse.quote(path, safe="/-_.~"), cq, f"host:{host}\n", "host", "UNSIGNED-PAYLOAD"])
sts = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(creq.encode()).hexdigest()])
k = ("AWS4" + sk).encode()
for part in (day, region, "s3", "aws4_request"):
    k = hmac.new(k, part.encode(), hashlib.sha256).digest()
print(cq + "&X-Amz-Signature=" + hmac.new(k, sts.encode(), hashlib.sha256).hexdigest())
PY
}

tok=$(get_token cuuho01)
echo "Đã lấy access token cho cuuho01 (${#tok} ký tự)"
gql='{"query":"{ __typename }"}'

# ---------- (1) JWT ở từng route ----------
check "POST /graphql không token" 401 "$(code - -H 'Content-Type: application/json' -d "$gql" "$GW/graphql")"
check "POST /graphql token giả" 401 "$(code "$FAKE" -H 'Content-Type: application/json' -d "$gql" "$GW/graphql")"
out=$(curl -s -K <(printf 'header = "Authorization: Bearer %s"\n' "$tok") -H 'Content-Type: application/json' -d "$gql" "$GW/graphql")
check "POST /graphql token Keycloak → Hasura /v1/graphql (Hasura kiểm JWT lần 2)" '{"data":{"__typename":"query_root"}}' "$out"
out=$(curl -s -K <(printf 'header = "Authorization: Bearer %s"\n' "$tok") -H 'X-Hasura-Role: admin' -H 'Content-Type: application/json' -d "$gql" "$GW/graphql")
check "POST /graphql xin vai trò admin bị Hasura chặn" access-denied \
  "$(python3 -c 'import sys,json; print(json.load(sys.stdin)["errors"][0]["extensions"]["code"])' <<<"$out" 2>/dev/null || echo "$out")"

check "GET /files/* không token" 401 "$(code - "$GW/files/bat-ky/anh.jpg")"
check "GET /files/* token giả" 401 "$(code "$FAKE" "$GW/files/bat-ky/anh.jpg")"

check "POST /workflow/* không token" 401 "$(code - -X POST "$GW/workflow/hello")"
check "POST /workflow/* token giả" 401 "$(code "$FAKE" -X POST "$GW/workflow/hello")"
check "POST /workflow/hello token Keycloak → API workflow → Temporal (#29)" 200 "$(code "$tok" -X POST "$GW/workflow/hello")"

# ---------- (2) endpoint quản trị Hasura không mở ra ngoài ----------
for p in /v1/metadata /v2/query /v1/query /console; do
  check "POST $p qua gateway bị chặn (kể cả có token)" 403 "$(code "$tok" -X POST -H 'Content-Type: application/json' -d '{"type":"export_metadata","args":{}}' "$GW$p")"
done

# ---------- (3) /files qua URL presigned S3 ----------
S3_AK=$(kv core/s3 access_key); S3_SK=$(kv core/s3 secret_key); SIGN_HOST=${GW#http://}
export S3_AK S3_SK SIGN_HOST
bucket="smoke-gw-$(date +%s)"
curl -s -o /dev/null -K <(printf 'user = "%s:%s"\n' "$S3_AK" "$S3_SK") --aws-sigv4 "aws:amz:us-east-1:s3" -X PUT "$S3/$bucket"
key="hien-truong/anh-01.jpg"
check "PUT /files presigned + JWT (ảnh JPEG đi qua WAF)" 200 \
  "$(code "$tok" -X PUT -H 'Content-Type: image/jpeg' --data-binary 'anh gia' "$GW/files/$bucket/$key?$(presign PUT "$bucket/$key")")"
got=$(curl -s -K <(printf 'header = "Authorization: Bearer %s"\n' "$tok") "$GW/files/$bucket/$key?$(presign GET "$bucket/$key")")
check "GET /files presigned + JWT đọc lại đúng nội dung" "anh gia" "$got"
check "GET /files presigned nhưng không JWT" 401 "$(code - "$GW/files/$bucket/$key?$(presign GET "$bucket/$key")")"
check "GET /files có JWT nhưng không chữ ký S3 (S3 từ chối)" 403 "$(code "$tok" "$GW/files/$bucket/$key")"
max=${GW_FILES_MAX_BODY_BYTES:-20971520}
check "PUT /files vượt $max byte" 413 \
  "$(head -c $((max + 1024)) /dev/zero | code "$tok" -X PUT -H 'Content-Type: application/octet-stream' --data-binary @- "$GW/files/$bucket/to.bin")"
for k in "$key" ""; do
  curl -s -o /dev/null -K <(printf 'user = "%s:%s"\n' "$S3_AK" "$S3_SK") --aws-sigv4 "aws:amz:us-east-1:s3" -X DELETE "$S3/$bucket/$k"
done

# ---------- (4) Coraza WAF + OWASP CRS ----------
check "GET /graphql query bình thường (?op=tim-kiem) vẫn qua WAF" 200 \
  "$(code "$tok" "$GW/graphql?query=%7B__typename%7D&op=tim-kiem")"
check "GET /graphql SQLi trong query bị WAF chặn" 403 "$(code "$tok" "$GW/graphql?id=1%27%20OR%20%271%27%3D%271")"
check "GET /graphql XSS trong query bị WAF chặn" 403 "$(code "$tok" "$GW/graphql?q=%3Cscript%3Ealert(1)%3C%2Fscript%3E")"
check "GET /files SQLi bị WAF chặn trước bước kiểm JWT" 403 "$(code - "$GW/files/a/b?id=1%20UNION%20SELECT%20password%20FROM%20users--")"
check "POST /workflow XSS trong body JSON bị WAF chặn" 403 \
  "$(code "$tok" -X POST -H 'Content-Type: application/json' -d '{"ghi_chu":"<script>alert(document.cookie)</script>"}' "$GW/workflow/hello")"

# shellcheck disable=SC2016 # $id là biến GraphQL, không phải biến shell
check "POST /graphql SQLi trong biến GraphQL (body JSON) bị WAF chặn" 403 \
  "$(code "$tok" -H 'Content-Type: application/json' -d '{"query":"query($id: String) { __typename }","variables":{"id":"1 UNION SELECT password FROM users--"}}' "$GW/graphql")"
check "POST /graphql body vượt 1 MiB" 413 \
  "$(head -c 1100000 /dev/zero | tr '\0' a | code "$tok" -H 'Content-Type: application/json' --data-binary @- "$GW/graphql")"

# ---------- (5) CORS ----------
cors() { # cors <origin>: giá trị Access-Control-Allow-Origin của preflight
  curl -s -o /dev/null -D - -X OPTIONS -H "Origin: $1" -H 'Access-Control-Request-Method: POST' \
    -H 'Access-Control-Request-Headers: authorization,content-type' "$GW/graphql" \
    | tr -d '\r' | sed -n 's/^[Aa]ccess-[Cc]ontrol-[Aa]llow-[Oo]rigin: //p'
}
check "CORS preflight từ $ORIGIN được phép" "$ORIGIN" "$(cors "$ORIGIN")"
check "CORS preflight từ origin lạ không được phép" "" "$(cors http://evil.example)"

# ---------- (6) limit-count ----------
# Chờ cửa sổ 10 giây hiện tại hết (các script trước đã gọi /healthz), rồi bắn 25 request
reset=$(curl -s -o /dev/null -D - "$GW/healthz" | tr -d '\r' | sed -n 's/^[Xx]-[Rr]ate[Ll]imit-[Rr]eset: //p')
sleep "${reset:-0}"
codes=$(for _ in $(seq 25); do curl -s -o /dev/null -w '%{http_code}\n' "$GW/healthz"; done | sort | uniq -c | awk '{printf "%s×%s ", $2, $1}')
check "limit-count /healthz: 25 request / 10 giây (giới hạn 20)" "200×20 429×5 " "$codes"
# Trả lại /healthz cho healthcheck và lần chạy sau
reset=$(curl -s -o /dev/null -D - "$GW/healthz" | tr -d '\r' | sed -n 's/^[Xx]-[Rr]ate[Ll]imit-[Rr]eset: //p')
sleep "${reset:-0}"
hdr=$(curl -s -o /dev/null -D - -K <(printf 'header = "Authorization: Bearer %s"\n' "$tok") -H 'Content-Type: application/json' -d "$gql" "$GW/graphql" \
  | tr -d '\r' | sed -n 's/^[Xx]-[Rr]ate[Ll]imit-[Ll]imit: //p')
check "limit-count route API (X-RateLimit-Limit)" "limit=${GW_RATE_LIMIT_COUNT:-300}" "limit=$hdr"
exit $fail
