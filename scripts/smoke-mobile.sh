#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử đường gọi của app hiện trường React Native (#106, D-011) trên stack THẬT qua APISIX:
# (1) client Keycloak `dxos-mobile`: đăng nhập PKCE như app (trình duyệt → redirect org.disasterdxos.cuutro:/oauthredirect
#     → đổi code + code_verifier lấy token), token có claim Hasura + offline_access, làm mới được; sai redirect_uri,
#     thiếu PKCE, đăng nhập mật khẩu trực tiếp đều bị từ chối;
# (2) token của app dùng được qua gateway (/graphql với vai tinh-nguyen, /workflow/*);
# (3) Idempotency-Key trên POST /workflow/keu-cuu: gửi lại cùng khóa → 201 + Idempotent-Replayed, cùng mã tin,
#     đúng một tin trong CSDL; khóa dùng lại cho nội dung khác / khóa sai dạng → 422; không khóa thì gửi lại bị chặn
#     trùng (409); 3 yêu cầu đồng thời cùng khóa → 1 tin; khóa theo người dùng;
# (4) ảnh hiện trường: gửi lại cùng khóa không thêm ảnh, khóa mới thì thêm;
# (5) chuyển tin vào hàng chờ duyệt (#104) qua hàng đợi: gửi lại cùng khóa → cùng mục, phản hồi phát lại không có
#     SĐT; (6) vị trí đội (cuu-ho, GraphQL): chỉ ghi khi mới hơn vị trí đang có;
# (7) bảng khóa không lưu SĐT; log cuu-tro-api và APISIX không có SĐT, khóa.
# SĐT giả 0900106xxx, tọa độ giả ở Hà Nội (xa đội mẫu). Dữ liệu thử bị xóa, vị trí đội mẫu được trả lại khi kết thúc.
# Dùng: make up && make seed && bash scripts/smoke-mobile.sh
# shellcheck disable=SC2016 # biến GraphQL ($id, $p, $luc) cố ý nằm trong nháy đơn
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

KC="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-disaster}"
GW="http://localhost:${APISIX_PORT:-9080}"
CLIENT=dxos-mobile
REDIRECT='org.disasterdxos.cuutro:/oauthredirect'
fail=0

check() { # check <tên> <mong đợi> <thực tế>
  if [ "$2" = "$3" ]; then echo "PASS  $1 → $3"; else echo "FAIL  $1 → $3 (mong đợi $2)"; fail=1; fi
}
urlenc() { python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$1"; }
claims() { python3 -c 'import sys,json,base64; p=sys.argv[1].split(".")[1]; p+="="*(-len(p)%4); print(json.dumps(json.loads(base64.urlsafe_b64decode(p))))' "$1"; }
jget() { python3 -c 'import sys,json; d=json.loads(sys.stdin.read() or "null"); print(eval(sys.argv[1], {"d": d}))' "$1"; }

# dang_nhap_app <user> [redirect_uri] [co_pkce]: như react-native-app-auth, in "<redirect Keycloak trả về>"
TMP=$(mktemp -d)
VERIFIER=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')
CHALLENGE=$(python3 -c 'import sys,hashlib,base64; print(base64.urlsafe_b64encode(hashlib.sha256(sys.argv[1].encode()).digest()).rstrip(b"=").decode())' "$VERIFIER")
dang_nhap_app() {
  # Đọc nguyên header Location (curl tự "chuẩn hóa" URL scheme riêng thành scheme://… nên không dùng %{redirect_url})
  local jar="$TMP/jar-$1" page action pkce="" redir=${2:-$REDIRECT} vi_tri
  [ "${3:-co}" = co ] && pkce="&code_challenge=$CHALLENGE&code_challenge_method=S256"
  rm -f "$jar"
  page=$(curl -s -m 20 -c "$jar" -b "$jar" -D "$TMP/h1" \
    "$KC/realms/$REALM/protocol/openid-connect/auth?client_id=$CLIENT&response_type=code&scope=openid%20profile%20offline_access&redirect_uri=$(urlenc "$redir")&state=smoke106&nonce=n106$pkce")
  case "$(head -n1 "$TMP/h1")" in
    *" 302"*) tr -d '\r' <"$TMP/h1" | awk -F': ' 'tolower($1)=="location"{print $2}'; return ;;  # từ chối bằng redirect lỗi
    *" 400"*) echo "HTTP400"; return ;;
  esac
  action=$(python3 -c 'import sys,re,html; print(html.unescape(re.search(r"action=\"([^\"]+)\"", sys.stdin.read()).group(1)))' <<<"$page")
  vi_tri=$(curl -s -m 20 -c "$jar" -b "$jar" -o /dev/null -D - -X POST "$action" \
    -d username="$1" --data-urlencode password="${KC_DEMO_USER_PASSWORD:?}" | tr -d '\r' | awk -F': ' 'tolower($1)=="location"{print $2}')
  printf '%s\n' "$vi_tri"
}
doi_code() { # doi_code <redirect> → JSON token
  local code
  code=$(python3 -c 'import sys,urllib.parse; print(urllib.parse.parse_qs(urllib.parse.urlparse(sys.argv[1]).query)["code"][0])' "$1")
  curl -s -m 20 -X POST "$KC/realms/$REALM/protocol/openid-connect/token" \
    -d grant_type=authorization_code -d client_id=$CLIENT --data-urlencode code="$code" \
    --data-urlencode redirect_uri="$REDIRECT" -d code_verifier="$VERIFIER"
}
# goi <token> <đường dẫn> <body|@tệp> [khóa] [content-type]: in "<mã HTTP> <replayed?> <body>"
goi() {
  local out hdr code
  out=$(mktemp); hdr=$(mktemp)
  local args=(-s -m 60 -o "$out" -D "$hdr" -w '%{http_code}' -X POST -H "Content-Type: ${5:-application/json}")
  [ -n "${4:-}" ] && args+=(-H "Idempotency-Key: $4")
  if [[ "$3" == @* ]]; then args+=(--data-binary "$3"); else args+=(--data-binary "$3"); fi
  code=$(curl -K <(printf 'header = "Authorization: Bearer %s"\n' "$1") "${args[@]}" "$GW$2")
  printf '%s %s %s\n' "$code" "$(tr -d '\r' <"$hdr" | awk -F': ' 'tolower($1)=="idempotent-replayed"{print $2}' | grep -c true || true)" "$(cat "$out")"
  rm -f "$out" "$hdr"
}
ma() { printf '%s' "${1%% *}"; }
phat_lai() { local r=${1#* }; printf '%s' "${r%% *}"; }
than() { local r=${1#* }; printf '%s' "${r#* }"; }
gql() { # gql <token> <vai> <query> [biến JSON]
  local body
  body=$(python3 -c 'import sys,json; print(json.dumps({"query": sys.argv[1], "variables": json.loads(sys.argv[2])}))' "$3" "${4:-{\}}")
  curl -s -m 20 -K <(printf 'header = "Authorization: Bearer %s"\n' "$1") -H "X-Hasura-Role: $2" \
    -H 'Content-Type: application/json' -d "$body" "$GW/graphql"
}
khoa() { echo "smoke106-$(python3 -c 'import uuid; print(uuid.uuid4())')"; }
sql() { timeout 60 docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -q -v ON_ERROR_STOP=1'; }
temporal_cli() { timeout 30 docker compose exec -T temporal sh -c "temporal $* --address temporal:7233"; }
dem_tin() { sql <<<"SELECT count(*) FROM cuu_tro.incidents WHERE reporter_phone LIKE '0900106%'"; }

DOI_GOC=$(sql <<<"SELECT t.id || '|' || coalesce(ST_AsText(t.location::geometry), '') || '|' || coalesce(t.location_updated_at::text, '')
  FROM cuu_tro.team_members m JOIN cuu_tro.rescue_teams t ON t.id = m.team_id
  WHERE m.username = 'cuuho01' OR m.user_id = '9b000000-0000-4000-8000-000000000002' LIMIT 1")
reset() {
  local id
  for id in $(sql <<<"SELECT id FROM cuu_tro.incidents WHERE reporter_phone LIKE '0900106%'"); do
    temporal_cli workflow terminate -w "phan-cong-$id" --reason smoke-reset >/dev/null 2>&1 || true
  done
  sql >/dev/null <<<"DELETE FROM cuu_tro.idempotency_keys WHERE key LIKE 'smoke106-%';
DELETE FROM cuu_tro.ai_intake_reviews WHERE raw_text LIKE '%0900 106%';
DELETE FROM cuu_tro.incident_media WHERE incident_id IN (SELECT id FROM cuu_tro.incidents WHERE reporter_phone LIKE '0900106%');
DELETE FROM cuu_tro.incidents WHERE reporter_phone LIKE '0900106%';" || true
}
tra_doi() {
  local id=${DOI_GOC%%|*} r=${DOI_GOC#*|}
  local loc=${r%%|*} luc=${r#*|}
  [ -n "$id" ] || return 0
  if [ -n "$loc" ]; then
    sql >/dev/null <<<"UPDATE cuu_tro.rescue_teams SET location = ST_GeogFromText('SRID=4326;$loc'), location_updated_at = '$luc' WHERE id = '$id'" || true
  else
    sql >/dev/null <<<"UPDATE cuu_tro.rescue_teams SET location = NULL, location_updated_at = NULL WHERE id = '$id'" || true
  fi
}
reset
trap 'reset; tra_doi; rm -rf "$TMP"' EXIT

# ---------- (1) Đăng nhập PKCE với client dxos-mobile ----------
R=$(dang_nhap_app tinhnguyen01)
check "đăng nhập tinhnguyen01 qua trình duyệt → chuyển về app với code" "co-code" \
  "$(case "$R" in "$REDIRECT?"*code=*) echo co-code ;; *) echo "${R:0:80}" ;; esac)"
TOK=$(doi_code "$R")
T=$(jget 'd["access_token"]' <<<"$TOK")
C=$(claims "$T")
check "token: azp dxos-mobile, vai tinh-nguyen trong claim Hasura, issuer = KEYCLOAK_PUBLIC_URL" \
  "dxos-mobile True $KC/realms/$REALM" \
  "$(jget 'd["azp"], "tinh-nguyen" in d["https://hasura.io/jwt/claims"]["x-hasura-allowed-roles"], d["iss"]' <<<"$C" | tr -d "(),'")"
check "refresh token offline (offline_access: làm việc nhiều ngày ngoài hiện trường)" Offline \
  "$(claims "$(jget 'd["refresh_token"]' <<<"$TOK")" | jget 'd["typ"]')"
check "làm mới token bằng refresh token (như react-native-app-auth refresh)" True \
  "$(curl -s -m 20 -X POST "$KC/realms/$REALM/protocol/openid-connect/token" -d grant_type=refresh_token -d client_id=$CLIENT \
      --data-urlencode refresh_token="$(jget 'd["refresh_token"]' <<<"$TOK")" | jget '"access_token" in d')"
check "redirect_uri lạ (không phải scheme của app) → Keycloak từ chối" HTTP400 \
  "$(dang_nhap_app tinhnguyen01 'https://ke-xau.example/cb')"
check "thiếu PKCE (code_challenge) → Keycloak từ chối" "co-loi" \
  "$(case "$(dang_nhap_app tinhnguyen01 "$REDIRECT" khong)" in *error=invalid_request*) echo co-loi ;; *) echo khong ;; esac)"
check "đăng nhập mật khẩu trực tiếp với client app → bị từ chối" unauthorized_client \
  "$(curl -s -m 20 -X POST "$KC/realms/$REALM/protocol/openid-connect/token" -d grant_type=password -d client_id=$CLIENT \
      -d username=tinhnguyen01 --data-urlencode password="${KC_DEMO_USER_PASSWORD:?}" | jget 'd.get("error")')"
R2=$(dang_nhap_app cuuho01)
CH=$(jget 'd["access_token"]' <<<"$(doi_code "$R2")")
check "đăng nhập cuuho01 qua app → token vai cuu-ho" True \
  "$(claims "$CH" | jget '"cuu-ho" in d["https://hasura.io/jwt/claims"]["x-hasura-allowed-roles"]')"

# ---------- (2) Token của app qua gateway ----------
check "GraphQL qua gateway bằng token app (vai tinh-nguyen, đúng query màn Hiện trường)" True \
  "$(gql "$T" tinh-nguyen '{ incidents(order_by: {created_at: desc}, limit: 50, where: {status: {_nin: ["dong"]}}) { id status urgency description address_text people_count created_at location } }' | jget '"data" in d and isinstance(d["data"]["incidents"], list)')"

# ---------- (3) Idempotency-Key trên /workflow/keu-cuu ----------
TIN='{"lat": 21.1301, "lon": 105.9001, "reporter_phone": "0900106001", "description": "[smoke #106] ngập tới mái", "urgency": "khan_cap", "people_count": 3, "source": "app"}'
K1=$(khoa)
r1=$(goi "$T" /workflow/keu-cuu "$TIN" "$K1")
r2=$(goi "$T" /workflow/keu-cuu "$TIN" "$K1")
ID1=$(than "$r1" | jget 'd["id"]')
check "lần đầu → 201, không phải phát lại" "201 0" "$(ma "$r1") $(phat_lai "$r1")"
check "gửi lại CÙNG khóa → 201 + Idempotent-Replayed, cùng mã tin" "201 1 $ID1" \
  "$(ma "$r2") $(phat_lai "$r2") $(than "$r2" | jget 'd["id"]')"
check "CSDL: đúng 1 tin" 1 "$(dem_tin)"
r=$(goi "$T" /workflow/keu-cuu "${TIN/3,/4,}" "$K1")
check "cùng khóa, nội dung khác → 422 khoa_idempotency_dung_lai" "422 khoa_idempotency_dung_lai" \
  "$(ma "$r") $(than "$r" | jget 'd["detail"]["ma"]')"
check "khóa sai dạng → 422 khoa_idempotency_sai" "422 khoa_idempotency_sai" \
  "$(r=$(goi "$T" /workflow/keu-cuu "$TIN" 'co dau cach'); echo "$(ma "$r") $(than "$r" | jget 'd["detail"]["ma"]')")"
check "không khóa: gửi lại bị chốt chặn trùng (409, app không biết tin đã vào) — lý do cần khóa" 409 \
  "$(ma "$(goi "$T" /workflow/keu-cuu "$TIN")")"
D=$(curl -s -m 20 -X POST "$KC/realms/$REALM/protocol/openid-connect/token" -d grant_type=password -d client_id=dxos-dev-cli \
  -d scope=openid -d username=dieuphoi01 --data-urlencode password="${KC_DEMO_USER_PASSWORD:?}" | jget 'd["access_token"]')
check "khóa theo người dùng: dieuphoi01 dùng trùng khóa không nhận lại tin của người khác (xử lý mới → 409 trùng)" "409 0" \
  "$(r=$(goi "$D" /workflow/keu-cuu "$TIN" "$K1"); echo "$(ma "$r") $(phat_lai "$r")")"
TIN2='{"lat": 21.1501, "lon": 105.9201, "reporter_phone": "0900106002", "description": "[smoke #106] đồng thời", "people_count": 2}'
K2=$(khoa)
for i in 1 2 3; do goi "$T" /workflow/keu-cuu "$TIN2" "$K2" >"$TMP/dt$i" & done
wait
check "3 yêu cầu đồng thời cùng khóa → cả 3 là 201, cùng một mã tin" "201 201 201 1" \
  "$(for i in 1 2 3; do ma "$(cat "$TMP/dt$i")"; printf ' '; done)$(for i in 1 2 3; do than "$(cat "$TMP/dt$i")" | jget 'd["id"]'; done | sort -u | wc -l | tr -d ' ')"
check "CSDL: đúng 1 tin cho SĐT 0900106002" 1 \
  "$(sql <<<"SELECT count(*) FROM cuu_tro.incidents WHERE reporter_phone = '0900106002'")"

# ---------- (4) Ảnh hiện trường ----------
{ printf '\xff\xd8\xff\xe0'; head -c 200 /dev/zero; } >"$TMP/anh.jpg"
KA=$(khoa)
a1=$(goi "$T" "/workflow/tai-len/su-co/$ID1/anh" @"$TMP/anh.jpg" "$KA" image/jpeg)
a2=$(goi "$T" "/workflow/tai-len/su-co/$ID1/anh" @"$TMP/anh.jpg" "$KA" image/jpeg)
check "ảnh: gửi lại cùng khóa → 201 phát lại, cùng mã ảnh, link xem mới" "201 201 1 True True" \
  "$(ma "$a1") $(ma "$a2") $(phat_lai "$a2") $(python3 -c 'import sys,json; a=json.loads(sys.argv[1]); b=json.loads(sys.argv[2]); print(a["id"]==b["id"], b["link"]["url"].startswith("http"))' "$(than "$a1")" "$(than "$a2")")"
check "CSDL: 1 ảnh cho tin" 1 "$(sql <<<"SELECT count(*) FROM cuu_tro.incident_media WHERE incident_id = '$ID1'")"
check "khóa mới → ảnh mới (2 ảnh)" "201 2" \
  "$(ma "$(goi "$T" "/workflow/tai-len/su-co/$ID1/anh" @"$TMP/anh.jpg" "$(khoa)" image/jpeg)") $(sql <<<"SELECT count(*) FROM cuu_tro.incident_media WHERE incident_id = '$ID1'")"

# ---------- (5) Chuyển tin cho điều phối duyệt (hàng chờ #104) ----------
VB=$(python3 -c 'import json; print(json.dumps({"van_ban": "Cuu voi, nha o thon 6 ngap sau, 2 nguoi, goi 0900 106 003", "nguon": "zalo", "vao_hang_cho": True}))')
KH=$(khoa)
h1=$(goi "$T" /workflow/ai/boc-tach "$VB" "$KH")
h2=$(goi "$T" /workflow/ai/boc-tach "$VB" "$KH")
check "chuyển tin: gửi lại cùng khóa → cùng mục hàng chờ, phát lại" "200 200 1 True" \
  "$(ma "$h1") $(ma "$h2") $(phat_lai "$h2") $(python3 -c 'import sys,json; a=json.loads(sys.argv[1]); b=json.loads(sys.argv[2]); print(a["hang_cho"]["id"]==b["hang_cho"]["id"])' "$(than "$h1")" "$(than "$h2")")"
check "phản hồi phát lại không có đề xuất/SĐT; CSDL đúng 1 mục" "False False 1" \
  "$(python3 -c 'import sys,json; d=json.loads(sys.argv[1]); print("de_xuat" in d, "0900" in json.dumps(d))' "$(than "$h2")") $(sql <<<"SELECT count(*) FROM cuu_tro.ai_intake_reviews WHERE raw_text LIKE '%0900 106 003%'")"

# ---------- (6) Vị trí đội (cuu-ho, GraphQL như app) ----------
# Đặt đội ở TP.HCM, xa mọi tin thử (Hà Nội, Đà Nẵng) để luồng phân công tự động không giao đội cho tin thử
DOI=$(gql "$CH" cuu-ho '{ team_members { team { id name } } }' | jget 'd["data"]["team_members"][0]["team"]["id"]')
# Đúng mutation của app (src/services/graphql.ts M_VI_TRI_DOI): không dùng _is_null vì WAF chặn
M='mutation ViTriDoi($id: uuid!, $p: geography!, $luc: timestamptz!) { update_rescue_teams(where: {id: {_eq: $id}, location_updated_at: {_lt: $luc}}, _set: {location: $p, location_updated_at: $luc}) { affected_rows } }'
MOI=$(python3 -c 'import datetime; print((datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=1)).isoformat())')
CU=$(python3 -c 'import datetime; print((datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(days=30)).isoformat())')
check "vị trí đội mới hơn → ghi (1 dòng)" 1 \
  "$(gql "$CH" cuu-ho "$M" "{\"id\": \"$DOI\", \"p\": {\"type\": \"Point\", \"coordinates\": [105.95, 21.12]}, \"luc\": \"$MOI\"}" | jget 'd["data"]["update_rescue_teams"]["affected_rows"]')"
check "bản ghi cũ trong hàng đợi gửi muộn → không đè vị trí mới (0 dòng)" 0 \
  "$(gql "$CH" cuu-ho "$M" "{\"id\": \"$DOI\", \"p\": {\"type\": \"Point\", \"coordinates\": [105.0, 21.0]}, \"luc\": \"$CU\"}" | jget 'd["data"]["update_rescue_teams"]["affected_rows"]')"
check "tinh-nguyen không cập nhật được vị trí đội" ERR \
  "$(gql "$T" tinh-nguyen "$M" "{\"id\": \"$DOI\", \"p\": {\"type\": \"Point\", \"coordinates\": [105.0, 21.0]}, \"luc\": \"$MOI\"}" | jget '"ERR" if "errors" in d else "OK"')"

# ---------- (7) Không lộ dữ liệu cá nhân ----------
check "bảng khóa idempotency không lưu SĐT" 0 \
  "$(sql <<<"SELECT count(*) FROM cuu_tro.idempotency_keys WHERE response::text LIKE '%0900106%' OR response::text LIKE '%0900 106%'")"
check "log cuu-tro-api và apisix không có SĐT hay khóa" 0 \
  "$(docker compose logs --no-log-prefix cuu-tro-api apisix 2>&1 | grep -c '0900106\|0900 106\|smoke106-' || true)"

if [ "$fail" -eq 0 ]; then echo "OK: smoke app hiện trường đạt"; else echo "CÓ LỖI: xem các dòng FAIL"; exit 1; fi
