#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử ảnh hiện trường của apps/cuu-tro (#27), gọi THẬT qua APISIX bằng token Keycloak của 3 user
# mẫu, kiểm kết quả trên SeaweedFS (S3) và PostgreSQL:
# (1) bucket cuu-tro-media do s3-buckets tạo, riêng tư (không ký → 403); khóa S3 của ứng dụng chỉ dùng
#     được bucket cuu-tro-*, không tạo được bucket; route /files/* chỉ đọc (PUT → 404);
# (2) dieu-phoi tải ảnh qua /workflow/tai-len/* → object trên S3 đúng nội dung + dòng incident_media;
#     không token → 401; tệp giả mạo → 415; quá ANH_MAX_BYTES → 413; quá giới hạn gateway → 413;
# (3) cuu-ho xem ảnh tin của đội mình → được (link presigned đọc đúng nội dung); tin đội khác → 403;
#     tinh-nguyen liệt kê/xem ảnh của tin → 403; tinh-nguyen gửi ảnh cho tin mình vừa tạo → 201, xem
#     lại ảnh của mình → 200, gửi cho tin người khác → 403;
# (4) link xem: không JWT → 401, đổi object → 403, hết hạn → 403; GraphQL không cho thêm incident_media.
# Dữ liệu tạo ra (dòng incident_media, tin thử, object) được xóa khi kết thúc.
# Dùng: make up && make seed && bash scripts/smoke-anh.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

KC="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-disaster}"
GW="http://localhost:${APISIX_PORT:-9080}"
S3="http://127.0.0.1:${SEAWEEDFS_S3_PORT:-8333}"
ADDR="http://127.0.0.1:${OPENBAO_PORT:-8200}"
DIR="${OPENBAO_LOCAL_DIR:-./.data/openbao}"
APP="${DXOS_APP:-cuu-tro}"
BUCKET="$APP-media"
INC_DOI=b0000000-0000-4000-8000-000000000002   # phân công cho đội của cuuho01 (seed)
INC_KHAC=b0000000-0000-4000-8000-000000000003  # phân công cho đội khác
MAX=${ANH_MAX_BYTES:-10485760}
GW_MAX=${GW_UPLOAD_MAX_BODY_BYTES:-20971520}
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
kv() { # kv <đường dẫn> <khóa>: đọc bí mật OpenBao bằng root token máy dev
  curl -s -K <(printf 'header = "X-Vault-Token: %s"\n' "$(cat "$DIR/root.token")") "$ADDR/v1/secret/data/$1" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["data"]["data"][sys.argv[1]])' "$2"
}
s3() { # s3 <access:secret> <method> <path> [tham số curl...] → mã HTTP (khóa đi qua file cấu hình curl)
  local cred=$1 method=$2 path=$3; shift 3
  curl -s -o /dev/null -w '%{http_code}' -K <(printf 'user = "%s"\n' "$cred") \
    --aws-sigv4 "aws:amz:us-east-1:s3" -X "$method" "$@" "$S3/$path"
}
# req <token|-> <tham số curl...>: in "<mã HTTP> <body>"; token đi qua file cấu hình curl
req() {
  local tok=$1 out code; shift
  out=$(mktemp)
  if [ "$tok" = - ]; then code=$(curl -s -o "$out" -w '%{http_code}' "$@")
  else code=$(curl -s -o "$out" -w '%{http_code}' -K <(printf 'header = "Authorization: Bearer %s"\n' "$tok") "$@"); fi
  printf '%s %s\n' "$code" "$(cat "$out")"
  rm -f "$out"
}
hc() { printf '%s' "${1%% *}"; }
# jf <biểu thức python trên d>: đọc phần body JSON (sau mã HTTP) từ stdin
jf() { python3 -c 'import sys,json; d=json.loads(sys.stdin.read().split(" ", 1)[1]); print(eval(sys.argv[1], {"d": d}))' "$1"; }
sql() { docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -q -v ON_ERROR_STOP=1'; }
tai() { # tai <token|-> <incident_id> <tệp> [Content-Type]
  req "$1" -X POST -H "Content-Type: ${4:-image/jpeg}" --data-binary @"$3" "$GW/workflow/tai-len/su-co/$2/anh"
}
sha() { if command -v sha256sum >/dev/null; then sha256sum | cut -d' ' -f1; else shasum -a 256 | cut -d' ' -f1; fi; }

# Ảnh mẫu: JPEG/PNG tối thiểu đúng chữ ký đầu tệp (dữ liệu giả)
python3 - "$TMP" <<'PY'
import struct, sys, zlib
d = sys.argv[1]
open(f"{d}/hien-truong.jpg", "wb").write(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + b"anh gia #27" * 50 + b"\xff\xd9")
def chunk(t, b): return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b))
png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) \
    + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND", b"")
open(f"{d}/hien-truong.png", "wb").write(png)
# Tệp giả mạo: tên .jpg, gửi Content-Type image/jpeg nhưng nội dung là HTML
open(f"{d}/gia-mao.jpg", "wb").write(b"<html><script>alert('anh')</script></html>")
PY
head -c $((MAX + 1)) /dev/zero | { printf '\xff\xd8\xff\xe0'; cat; } > "$TMP/qua-lon.jpg"

D=$(get_token dieuphoi01); C=$(get_token cuuho01); T=$(get_token tinhnguyen01)
AK=$(kv core/s3 access_key); SK=$(kv core/s3 secret_key)
APP_AK=$(kv "app/$APP/s3" access_key); APP_SK=$(kv "app/$APP/s3" secret_key)
INC_TN=''
cleanup() {
  local k ids=''
  for k in "${MEDIA[@]}"; do [ -n "$k" ] && ids+="${ids:+,}'$k'"; done
  {
    [ -n "$ids" ] && echo "DELETE FROM cuu_tro.incident_media WHERE id IN ($ids);"
    [ -n "$INC_TN" ] && echo "DELETE FROM cuu_tro.incidents WHERE id = '$INC_TN';"
    echo "SELECT 1;"
  } | sql >/dev/null || true
  for k in "${KEYS[@]}"; do [ -n "$k" ] && { s3 "$AK:$SK" DELETE "$BUCKET/$k" >/dev/null || true; }; done
  [ -n "${TMPB:-}" ] && s3 "$AK:$SK" DELETE "$TMPB" >/dev/null
  rm -rf "$TMP"
}
MEDIA=(); KEYS=()
trap cleanup EXIT
nho() { # nho <kết quả tải lên>: ghi lại id + object key để dọn khi kết thúc
  MEDIA+=("$(jf 'd.get("id", "")' <<<"$1" 2>/dev/null || true)")
  KEYS+=("$(jf 'd.get("object_key", "")' <<<"$1" 2>/dev/null || true)")
}

# ---------- (1) Bucket, định danh S3 của ứng dụng, route /files chỉ đọc ----------
check "bucket $BUCKET đã được s3-buckets tạo (HEAD bằng khóa quản trị)" 200 "$(s3 "$AK:$SK" HEAD "$BUCKET")"
check "bucket $BUCKET riêng tư: liệt kê không ký → 403" 403 "$(curl -s -o /dev/null -w '%{http_code}' "$S3/$BUCKET")"
check "s3-buckets chạy lại không lỗi (bucket đã có)" 0 \
  "$(docker compose --profile core run --rm --no-deps s3-buckets >/dev/null 2>&1; echo $?)"
check "khóa S3 của ứng dụng ghi được bucket $BUCKET" 200 \
  "$(s3 "$APP_AK:$APP_SK" PUT "$BUCKET/smoke/thu.txt" -H 'Content-Type: text/plain' --data-binary 'thu')"
check "khóa S3 của ứng dụng xóa object trong bucket $BUCKET" 204 "$(s3 "$APP_AK:$APP_SK" DELETE "$BUCKET/smoke/thu.txt")"
TMPB="smoke-anh-$(date +%s)"
s3 "$AK:$SK" PUT "$TMPB" >/dev/null
check "khóa S3 của ứng dụng KHÔNG ghi được bucket ngoài tiền tố $APP-" 403 \
  "$(s3 "$APP_AK:$APP_SK" PUT "$TMPB/x.txt" -H 'Content-Type: text/plain' --data-binary 'x')"
check "khóa S3 của ứng dụng KHÔNG tạo được bucket (không có Admin)" 403 "$(s3 "$APP_AK:$APP_SK" PUT "$APP-tu-tao-$(date +%s)")"
check "PUT /files/* qua gateway không có route (chỉ GET/HEAD)" 404 \
  "$(hc "$(req "$D" -X PUT -H 'Content-Type: image/jpeg' --data-binary @"$TMP/hien-truong.jpg" "$GW/files/$BUCKET/su-co/x.jpg")")"

# ---------- (2) Tải ảnh lên ----------
dem() { sql <<<"SELECT count(*) FROM cuu_tro.incident_media WHERE incident_id = '$INC_DOI'"; }
TRUOC=$(dem)
check "tải ảnh không token → 401" 401 "$(hc "$(tai - "$INC_DOI" "$TMP/hien-truong.jpg")")"
r=$(tai "$D" "$INC_DOI" "$TMP/hien-truong.jpg")
check "dieu-phoi tải JPEG cho tin $INC_DOI → 201" 201 "$(hc "$r")"
nho "$r"; ID1=${MEDIA[0]}; KEY1=${KEYS[0]}
check "object key theo quy ước su-co/<tin>/<id>.jpg" "su-co/$INC_DOI/$ID1.jpg" "$KEY1"
got=$(curl -s -K <(printf 'user = "%s:%s"\n' "$AK" "$SK") --aws-sigv4 "aws:amz:us-east-1:s3" "$S3/$BUCKET/$KEY1" | sha)
check "object trên SeaweedFS đúng nội dung (sha256)" "$(sha < "$TMP/hien-truong.jpg")" "$got"
check "dòng incident_media: đúng loại, kích thước, sha256, người tải" \
  "image/jpeg|$(wc -c < "$TMP/hien-truong.jpg" | tr -d ' ')|$(sha < "$TMP/hien-truong.jpg")|dieu-phoi|chua_quet" \
  "$(sql <<<"SELECT content_type, size_bytes, sha256, uploader_role, scan_status FROM cuu_tro.incident_media WHERE id = '$ID1'")"
r=$(tai "$D" "$INC_KHAC" "$TMP/hien-truong.png" application/octet-stream)
check "dieu-phoi tải PNG (Content-Type octet-stream) cho tin đội khác → 201, loại nhận từ nội dung" "201 image/png" \
  "$(hc "$r") $(jf 'd["content_type"]' <<<"$r")"
nho "$r"; ID2=${MEDIA[1]}
check "tệp giả mạo (.jpg, Content-Type image/jpeg, nội dung HTML) → 415" 415 "$(hc "$(tai "$D" "$INC_DOI" "$TMP/gia-mao.jpg")")"
check "ảnh vượt ANH_MAX_BYTES=$MAX → 413 (API)" 413 "$(hc "$(tai "$D" "$INC_DOI" "$TMP/qua-lon.jpg")")"
check "body vượt GW_UPLOAD_MAX_BODY_BYTES=$GW_MAX → 413 (gateway)" 413 \
  "$(hc "$(head -c $((GW_MAX + 1024)) /dev/zero | req "$D" -X POST -H 'Content-Type: image/jpeg' --data-binary @- "$GW/workflow/tai-len/su-co/$INC_DOI/anh")")"
check "không ghi dòng nào cho tệp bị từ chối (tin $INC_DOI chỉ thêm đúng 1 ảnh)" $((TRUOC + 1)) "$(dem)"

# ---------- (3) Quyền xem theo vai trò ----------
r=$(req "$C" "$GW/workflow/su-co/$INC_DOI/anh")
check "cuu-ho liệt kê ảnh tin của đội mình → 200, có ảnh vừa tải" "200 True" "$(hc "$r") $(jf "'$ID1' in [m['id'] for m in d['anh']]" <<<"$r")"
LINK=$(jf "[m['link']['url'] for m in d['anh'] if m['id'] == '$ID1'][0]" <<<"$r")
got=$(curl -s -K <(printf 'header = "Authorization: Bearer %s"\n' "$C") "$LINK" | sha)
check "cuu-ho mở link presigned qua gateway /files (kèm JWT) → đúng nội dung" "$(sha < "$TMP/hien-truong.jpg")" "$got"
check "cuu-ho liệt kê ảnh tin của đội khác → 403" 403 "$(hc "$(req "$C" "$GW/workflow/su-co/$INC_KHAC/anh")")"
check "cuu-ho xin link ảnh tin của đội khác → 403" 403 "$(hc "$(req "$C" "$GW/workflow/anh/$ID2/link")")"
check "cuu-ho xin link ảnh tin của đội mình → 200" 200 "$(hc "$(req "$C" "$GW/workflow/anh/$ID1/link")")"
check "tinh-nguyen liệt kê ảnh của tin → 403" 403 "$(hc "$(req "$T" "$GW/workflow/su-co/$INC_DOI/anh")")"
check "tinh-nguyen xin link ảnh người khác tải → 403" 403 "$(hc "$(req "$T" "$GW/workflow/anh/$ID1/link")")"
check "tinh-nguyen gửi ảnh cho tin không phải mình tạo → 403" 403 "$(hc "$(tai "$T" "$INC_DOI" "$TMP/hien-truong.jpg")")"
# tinh-nguyen tạo tin kêu cứu mới qua GraphQL (SĐT/tọa độ riêng để không trùng với tin seed)
# shellcheck disable=SC2016 # $o là biến GraphQL
gq='{"query":"mutation($o: incidents_insert_input!) { insert_incidents_one(object: $o) { id status } }","variables":{"o":{"description":"Smoke #27: nhà bị nước cuốn, gửi kèm ảnh","location":{"type":"Point","coordinates":[108.2%s,15.9%s]},"reporter_phone":"09%08d","source":"app"}}}'
# shellcheck disable=SC2059 # chuỗi định dạng có chủ đích
r=$(req "$T" -H 'Content-Type: application/json' -H 'X-Hasura-Role: tinh-nguyen' \
  -d "$(printf "$gq" "$((RANDOM % 1000))" "$((RANDOM % 1000))" "$((RANDOM * 3 % 100000000))")" "$GW/graphql")
INC_TN=$(jf 'd["data"]["insert_incidents_one"]["id"]' <<<"$r")
r=$(tai "$T" "$INC_TN" "$TMP/hien-truong.png" image/png)
check "tinh-nguyen gửi ảnh cho tin mình vừa tạo (tiep_nhan) → 201" 201 "$(hc "$r")"
nho "$r"; ID3=${MEDIA[2]}
check "tinh-nguyen xin link ảnh chính mình tải → 200" 200 "$(hc "$(req "$T" "$GW/workflow/anh/$ID3/link")")"
check "cuu-ho xin link ảnh của tin chưa phân công cho đội mình → 403" 403 "$(hc "$(req "$C" "$GW/workflow/anh/$ID3/link")")"
check "dieu-phoi liệt kê ảnh tin của tinh-nguyen → 200, 1 ảnh" "200 1" \
  "$(r=$(req "$D" "$GW/workflow/su-co/$INC_TN/anh"); echo "$(hc "$r") $(jf 'len(d["anh"])' <<<"$r")")"
sql >/dev/null <<<"UPDATE cuu_tro.incidents SET status = 'phan_cong', assigned_team_id = 'a0000000-0000-4000-8000-000000000001' WHERE id = '$INC_TN'"
check "tinh-nguyen gửi thêm ảnh khi tin đã phân công (không còn là tin mới) → 403" 403 "$(hc "$(tai "$T" "$INC_TN" "$TMP/hien-truong.jpg")")"

# ---------- (4) Link xem ngắn hạn, GraphQL ----------
check "link presigned không kèm JWT → 401 (gateway)" 401 "$(curl -s -o /dev/null -w '%{http_code}' "$LINK")"
DOI_KEY=${LINK/"su-co/$INC_DOI/$ID1.jpg"/"su-co/$INC_KHAC/$ID2.png"}
check "dùng chữ ký của ảnh này để mở ảnh khác → 403 (S3)" 403 \
  "$(curl -s -o /dev/null -w '%{http_code}' -K <(printf 'header = "Authorization: Bearer %s"\n' "$C") "$DOI_KEY")"
r=$(req "$C" "$GW/workflow/anh/$ID1/link?han_giay=2")
check "xin link hạn 2 giây → 200" 200 "$(hc "$r")"
NGAN=$(jf 'd["link"]["url"]' <<<"$r")
check "link hạn 2 giây mở ngay → 200" 200 \
  "$(curl -s -o /dev/null -w '%{http_code}' -K <(printf 'header = "Authorization: Bearer %s"\n' "$C") "$NGAN")"
sleep 4
check "link hết hạn → không truy cập được (403)" 403 \
  "$(curl -s -o /dev/null -w '%{http_code}' -K <(printf 'header = "Authorization: Bearer %s"\n' "$C") "$NGAN")"
check "xin link hạn quá ANH_LINK_HAN_GIAY → 422" 422 "$(hc "$(req "$C" "$GW/workflow/anh/$ID1/link?han_giay=999999")")"
gm='{"query":"mutation { insert_incident_media_one(object: {}) { id } }"}'
check "GraphQL không có mutation thêm incident_media (dieu-phoi)" validation-failed \
  "$(req "$D" -H 'Content-Type: application/json' -H 'X-Hasura-Role: dieu-phoi' -d "$gm" "$GW/graphql" | jf 'd["errors"][0]["extensions"]["code"]')"
gm='{"query":"{ incident_media { id incident_id } }"}'
check "GraphQL: cuu-ho chỉ thấy ảnh tin của đội mình" "True False" \
  "$(req "$C" -H 'Content-Type: application/json' -H 'X-Hasura-Role: cuu-ho' -d "$gm" "$GW/graphql" \
    | jf "' '.join(str(x in [m['id'] for m in d['data']['incident_media']]) for x in ('$ID1', '$ID2'))")"
check "GraphQL: tinh-nguyen chỉ thấy ảnh mình tải" "$ID3" \
  "$(req "$T" -H 'Content-Type: application/json' -H 'X-Hasura-Role: tinh-nguyen' -d "$gm" "$GW/graphql" \
    | jf "','.join(m['id'] for m in d['data']['incident_media'])")"

if [ "$fail" -ne 0 ]; then echo "smoke-anh: CÓ LỖI"; exit 1; fi
echo "smoke-anh: tất cả đều đạt"
