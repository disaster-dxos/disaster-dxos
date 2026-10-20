#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Khởi tạo OpenBao một lần và nạp bí mật lõi (#14). Chạy lại bao nhiêu lần cũng được:
# chỉ tạo cái còn thiếu, KHÔNG ghi đè bí mật, key hay secret_id đã có.
#
#   scripts/openbao-init.sh          init (nếu chưa) → unseal → KV v2 → bí mật → policy → AppRole
#   scripts/openbao-init.sh unseal   chỉ mở khóa (sau khi khởi động lại, khi tắt auto-unseal)
#
# Gọi HTTP API qua 127.0.0.1:${OPENBAO_PORT}; cần curl, python3, openssl trên máy host.
# Key và token ghi vào ${OPENBAO_LOCAL_DIR} (mặc định .data/openbao/, đã nằm trong .gitignore):
#   init.json          kết quả "operator init" (unseal key + root token) — GIỮ KÍN, không commit
#   unseal/unseal.keys unseal key, mỗi dòng một key (openbao-unseal đọc khi dev)
#   root.token         root token, chỉ dùng để quản trị trên máy dev
#   approle/<dịch vụ>/{role_id,secret_id}   bao agent của từng dịch vụ đăng nhập bằng 2 file này
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

ADDR="http://127.0.0.1:${OPENBAO_PORT:-8200}"
DIR="${OPENBAO_LOCAL_DIR:-./.data/openbao}"
SHARES="${OPENBAO_KEY_SHARES:-3}"
THRESHOLD="${OPENBAO_KEY_THRESHOLD:-2}"
POLICY_DIR=core/openbao/policies
APP="${DXOS_APP:-cuu-tro}"
# Policy riêng của ứng dụng (vd backend worker đọc mật khẩu role DB của ứng dụng): policy và AppRole
# tên app-<ứng dụng>-<dịch vụ>, để nhiều ứng dụng dùng chung một OpenBao không đụng tên nhau
APP_POLICY_DIR="apps/$APP/openbao/policies"
umask 077

log() { echo "openbao-init: $*"; }
die() { echo "openbao-init: LỖI: $*" >&2; exit 1; }
for c in curl python3 openssl; do command -v "$c" >/dev/null || die "thiếu lệnh '$c'"; done

# api <METHOD> <path> [-]  → đặt HTTP_CODE và BODY; "-" = gửi body JSON từ stdin.
# Token đi qua file cấu hình curl (process substitution), không nằm trên dòng lệnh.
HTTP_CODE='' BODY=''
api() {
  local method=$1 path=$2 out
  out=$(mktemp)
  local args=(-s -o "$out" -w '%{http_code}' -X "$method" "$ADDR/v1/$path")
  if [ "${3:-}" = "-" ]; then args+=(-H 'Content-Type: application/json' --data-binary @-); fi
  if [ -n "${ROOT_TOKEN:-}" ]; then
    HTTP_CODE=$(curl -K <(printf 'header = "X-Vault-Token: %s"\n' "$ROOT_TOKEN") "${args[@]}") || HTTP_CODE=000
  else
    HTTP_CODE=$(curl "${args[@]}") || HTTP_CODE=000
  fi
  BODY=$(cat "$out")
  rm -f "$out"
}
# api_ok: như api nhưng dừng script khi mã HTTP không phải 2xx/3xx
api_ok() {
  api "$@"
  [[ $HTTP_CODE =~ ^[23] ]] || die "$1 $2 → HTTP $HTTP_CODE: $BODY"
}
# jget <biểu thức python trên d>: đọc JSON từ stdin
jget() { python3 -c "import sys,json; d=json.load(sys.stdin); print($1)"; }

wait_api() {
  local _
  for _ in $(seq 1 60); do
    api GET sys/seal-status >/dev/null
    [ "$HTTP_CODE" = 200 ] && return 0
    sleep 2
  done
  die "OpenBao không trả lời ở $ADDR. Chạy trước: docker compose --profile core up -d openbao"
}

do_init() {
  api_ok GET sys/seal-status
  if [ "$(jget 'd["initialized"]' <<<"$BODY")" = True ]; then
    log "đã init từ trước"
    return 0
  fi
  [ -e "$DIR/init.json" ] && die "$DIR/init.json đã tồn tại nhưng OpenBao chưa init (volume baodata bị xóa?). Chuyển file cũ đi rồi chạy lại."
  mkdir -p "$DIR/unseal"
  log "init với $SHARES key share, ngưỡng $THRESHOLD"
  api_ok PUT sys/init - <<<"$(python3 -c 'import json,sys; print(json.dumps({"secret_shares":int(sys.argv[1]),"secret_threshold":int(sys.argv[2])}))' "$SHARES" "$THRESHOLD")"
  printf '%s\n' "$BODY" > "$DIR/init.json"
  jget '"\n".join(d["keys_base64"])' < "$DIR/init.json" > "$DIR/unseal/unseal.keys"
  jget 'd["root_token"]' < "$DIR/init.json" > "$DIR/root.token"
  log "đã lưu unseal key và root token vào $DIR/ (ngoài git)"
}

do_unseal() {
  local k
  api_ok GET sys/seal-status
  [ "$(jget 'd["initialized"]' <<<"$BODY")" = True ] || die "OpenBao chưa init. Chạy: make bao-init"
  if [ "$(jget 'd["sealed"]' <<<"$BODY")" = False ]; then log "đã mở khóa"; return 0; fi
  [ -s "$DIR/unseal/unseal.keys" ] || die "không có $DIR/unseal/unseal.keys để mở khóa"
  while read -r k; do
    # key đi qua stdin, không nằm trên dòng lệnh
    api_ok PUT sys/unseal - <<<"$(python3 -c 'import json,sys; print(json.dumps({"key":sys.stdin.read().strip()}))' <<<"$k")"
    [ "$(jget 'd["sealed"]' <<<"$BODY")" = False ] && { log "đã mở khóa"; return 0; }
  done < "$DIR/unseal/unseal.keys"
  die "nhập hết key mà vẫn sealed"
}

# kv_seed <đường dẫn dưới secret/> <khóa>=<tên biến env hoặc @rand[:n] hoặc @empty> ...
# Chỉ ghi khi bí mật chưa có (cas=0). Lấy giá trị từ biến môi trường nếu .env cũ còn biến đó
# (chuyển dữ liệu từ bản trước #14 mà không đổi mật khẩu đã dùng trong volume), nếu không thì sinh ngẫu nhiên.
kv_seed() {
  local path=$1; shift
  api GET "secret/data/$path" >/dev/null
  if [ "$HTTP_CODE" = 200 ]; then log "secret/$path: đã có, giữ nguyên"; return 0; fi
  local spec key src n payload
  payload=$(for spec in "$@"; do
    key=${spec%%=*}; src=${spec#*=}
    case $src in
      @rand*) n=${src#@rand}; n=${n#:}; printf '%s\t%s\n' "$key" "$(openssl rand -hex "${n:-24}")" ;;
      @empty) printf '%s\t\n' "$key" ;;
      *) if [ -n "${!src:-}" ]; then printf '%s\t%s\n' "$key" "${!src}"
         else printf '%s\t%s\n' "$key" "$(openssl rand -hex 24)"; fi ;;
    esac
  done | python3 -c 'import sys,json; print(json.dumps({"options":{"cas":0},"data":dict(l.rstrip("\n").split("\t",1) for l in sys.stdin)}))')
  api_ok POST "secret/data/$path" - <<<"$payload"
  log "secret/$path: đã tạo"
}

do_setup() {
  [ -s "$DIR/root.token" ] || die "không có $DIR/root.token (cần root token để cấu hình)"
  ROOT_TOKEN=$(cat "$DIR/root.token")

  # KV v2 tại secret/
  api_ok GET sys/mounts
  if [ "$(jget '"secret/" in d.get("data", d)' <<<"$BODY")" != True ]; then
    api_ok POST sys/mounts/secret - <<<'{"type":"kv","options":{"version":"2"},"description":"Bí mật lõi Disaster DX-OS"}'
    log "đã bật KV v2 tại secret/"
  fi

  # Bí mật lõi. Biến bên phải là tên biến cũ trong .env (bản trước #14/#11): còn thì nạp đúng
  # giá trị đó để khớp volume cũ, không còn thì sinh ngẫu nhiên.
  kv_seed core/postgres       password=POSTGRES_PASSWORD
  kv_seed core/keycloak-db    password=KEYCLOAK_DB_PASSWORD
  kv_seed core/keycloak-admin password=KC_BOOTSTRAP_ADMIN_PASSWORD
  kv_seed core/gateway        client_secret=KC_GATEWAY_CLIENT_SECRET
  kv_seed core/hasura-db      password=@rand:24
  kv_seed core/hasura         admin_secret=HASURA_GRAPHQL_ADMIN_SECRET
  kv_seed core/temporal-db    password=@rand:24
  kv_seed core/s3             access_key=@rand:10 secret_key=@rand:24
  # Khóa ký checkpoint Tessera (#28, sinh bằng core/ledger)
  kv_seed core/ledger         signing_key=@empty
  # Role DB dịch vụ của ứng dụng Tầng 2 đang chọn (<schema>_app, #29): postgres-roles tạo role,
  # backend của ứng dụng (worker) đăng nhập bằng role này. Lõi chỉ biết quy ước tên, không biết nghiệp vụ.
  kv_seed "app/$APP/db"       password=@rand:24

  # AppRole
  api_ok GET sys/auth
  if [ "$(jget '"approle/" in d.get("data", d)' <<<"$BODY")" != True ]; then
    api_ok POST sys/auth/approle - <<<'{"type":"approle"}'
    log "đã bật auth AppRole"
  fi

  # Mỗi file core/openbao/policies/<dịch vụ>.hcl → policy core-<dịch vụ> + AppRole <dịch vụ>;
  # mỗi file apps/<ứng dụng>/openbao/policies/<dịch vụ>.hcl → policy + AppRole app-<ứng dụng>-<dịch vụ>
  local f svc policy
  for f in "$POLICY_DIR"/*.hcl "$APP_POLICY_DIR"/*.hcl; do
    [ -e "$f" ] || continue
    case $f in
      "$APP_POLICY_DIR"/*) svc="app-$APP-$(basename "$f" .hcl)"; policy=$svc ;;
      *) svc=$(basename "$f" .hcl); policy="core-$svc" ;;
    esac
    api_ok PUT "sys/policies/acl/$policy" - <<<"$(python3 -c 'import sys,json; print(json.dumps({"policy":open(sys.argv[1]).read()}))' "$f")"
    # Token ngắn hạn, agent tự gia hạn/đăng nhập lại. secret_id không hết hạn: chỉ cho dev.
    api_ok POST "auth/approle/role/$svc" - <<<"$(python3 -c 'import sys,json; print(json.dumps({"token_policies":[sys.argv[1]],"token_ttl":"1h","token_max_ttl":"24h","secret_id_ttl":"0","token_type":"service"}))' "$policy")"
    mkdir -p "$DIR/approle/$svc"
    api_ok GET "auth/approle/role/$svc/role-id"
    jget 'd["data"]["role_id"]' <<<"$BODY" | tr -d '\n' > "$DIR/approle/$svc/role_id"
    if [ ! -s "$DIR/approle/$svc/secret_id" ]; then
      api_ok POST "auth/approle/role/$svc/secret-id"
      jget 'd["data"]["secret_id"]' <<<"$BODY" | tr -d '\n' > "$DIR/approle/$svc/secret_id"
      log "AppRole $svc: đã cấp secret_id mới"
    fi
    # Container agent chạy user openbao (uid 100) phải đọc được qua bind mount;
    # thư mục cha $DIR vẫn 0700 nên user khác trên máy host không vào được.
    chmod 0755 "$DIR/approle/$svc"
    chmod 0644 "$DIR/approle/$svc/role_id" "$DIR/approle/$svc/secret_id"
    log "policy $policy + AppRole $svc: OK"
  done
}

mkdir -p "$DIR"
chmod 0700 "$DIR"
wait_api
case "${1:-all}" in
  unseal) do_unseal ;;
  all)    do_init; do_unseal; do_setup; log "xong. Kiểm tra: make smoke" ;;
  *) echo "Dùng: $0 [unseal]" >&2; exit 2 ;;
esac
