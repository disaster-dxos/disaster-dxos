#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử Grafana OSS dashboard điều hành (#92). Tự bật profile bi nếu Grafana chưa chạy, gọi THẬT qua APISIX:
# (1) Grafana image gốc, không mở cổng ra host, sống qua gateway /grafana/api/health; chưa đăng nhập → 401;
#     sai mật khẩu → 401; không đăng ký được; WAF vẫn chặn XSS trong tham số;
# (2) đăng nhập admin (mật khẩu từ OpenBao): datasource provisioned dùng role chỉ đọc cuu_tro_bi, không sửa
#     được trên giao diện; dashboard "Điều hành cứu trợ" đã nạp từ tệp, đủ panel;
# (3) mọi truy vấn của mọi panel chạy được qua /api/ds/query (không lỗi); một truy vấn trả đúng số liệu CSDL;
# (4) datasource không đọc được SĐT/họ tên, không ghi được (read-only);
# (5) SSO Keycloak (#126): client dxos-grafana do keycloak-grafana-client tạo (idempotent, chạy lại được, secret
#     khớp OpenBao), PKCE S256 bắt buộc, form đăng nhập tắt; đăng nhập như trình duyệt qua APISIX: dieu-phoi
#     (user tạm, bị bắt cài OTP) → Editor, cuu-ho → Viewer, cả hai lấy được dashboard; tinh-nguyen bị từ chối;
#     không ai thành Grafana Admin; đăng xuất chuyển sang Keycloak.
# Dùng: make up && bash scripts/smoke-grafana.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

GW="http://localhost:${APISIX_PORT:-9080}"
G="$GW/grafana"
ADDR="http://127.0.0.1:${OPENBAO_PORT:-8200}"
DIR="${OPENBAO_LOCAL_DIR:-./.data/openbao}"
UID_DB=cuu-tro-dieu-hanh
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail=0

check() { # check <tên> <mong đợi> <thực tế>
  if [ "$2" = "$3" ]; then echo "PASS  $1 → $3"; else echo "FAIL  $1 → $3 (mong đợi $2)"; fail=1; fi
}
kv() { # kv <đường dẫn> <khóa>: đọc MỘT trường bí mật OpenBao bằng root token máy dev
  curl -s -K <(printf 'header = "X-Vault-Token: %s"\n' "$(cat "$DIR/root.token")") "$ADDR/v1/secret/data/$1" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["data"]["data"].get(sys.argv[1], ""))' "$2"
}
sql() { docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -q -v ON_ERROR_STOP=1'; }
# ga <user:mật khẩu|-> <đường dẫn sau /grafana> [tham số curl]: in "<mã HTTP> <body>"; mật khẩu qua file cấu hình curl
ga() {
  local auth=$1 path=$2 out code
  shift 2
  out=$(mktemp)
  if [ "$auth" = - ]; then code=$(curl -s -o "$out" -w '%{http_code}' "$@" "$G$path")
  else code=$(curl -s -o "$out" -w '%{http_code}' -K <(printf 'user = "%s"\n' "$auth") "$@" "$G$path"); fi
  printf '%s %s\n' "$code" "$(tr -d '\n' <"$out")"
  rm -f "$out"
}
hc() { printf '%s' "${1%% *}"; }
jf() { python3 -c 'import sys,json; d=json.loads(sys.stdin.read().split(" ", 1)[1]); print(eval(sys.argv[1], {"d": d}))' "$1"; }
# q <SQL>: chạy một truy vấn qua datasource provisioned (như panel), in "<mã HTTP> <body>"
q() {
  ga "$ADMIN" /api/ds/query -X POST -H 'Content-Type: application/json' -d "$(python3 -c '
import json, sys
print(json.dumps({"from": "now-30d", "to": "now", "queries": [{"refId": "A", "datasource": {"uid": "dxos-app-pg"},
      "rawSql": sys.argv[1], "format": "table", "rawQuery": True}]}))' "$1")"
}

# ---------------- (1) Dịch vụ, gateway, đăng nhập ----------------
if [ "$(docker compose ps --format '{{.Health}}' grafana 2>/dev/null)" != healthy ]; then
  # make up-bi: openbao-init, tạo lại bao agent nếu còn cấu hình cũ (#126), client Keycloak, rồi Grafana
  make -s up-bi >/dev/null 2>&1
  for _ in $(seq 1 60); do [ "$(docker compose ps --format '{{.Health}}' grafana)" = healthy ] && break; sleep 2; done
fi
check "grafana healthy (profile bi)" healthy "$(docker compose ps --format '{{.Health}}' grafana)"
check "grafana dùng image gốc grafana/grafana-oss, ghim phiên bản" True \
  "$(i=$(docker inspect -f '{{.Config.Image}}' "$(docker compose ps -q grafana)"); [[ $i == grafana/grafana-oss:[0-9]* ]] && echo True || echo "$i")"
check "grafana không mở cổng ra host" "" "$(docker port "$(docker compose ps -q grafana)" 2>/dev/null || true)"
r=$(ga - /api/health)
check "GET /grafana/api/health qua APISIX → 200, CSDL ok" "200 ok" "$(hc "$r") $(jf 'd["database"]' <<<"$r")"
check "chưa đăng nhập: /grafana/api/search → 401" 401 "$(hc "$(ga - /api/search)")"
check "sai mật khẩu admin → 401" 401 "$(hc "$(ga 'admin:sai-mat-khau' /api/search)")"
check "không tự đăng ký được tài khoản" True \
  "$(c=$(hc "$(ga - /api/user/signup -X POST -H 'Content-Type: application/json' -d '{"email":"x@example.invalid"}')"); [ "$c" != 200 ] && echo True || echo "$c")"
check "WAF vẫn chặn XSS trong tham số /grafana/" 403 "$(hc "$(ga - '/?q=%3Cscript%3Ealert(1)%3C/script%3E')")"
ADMIN="admin:$(kv core/grafana admin_password)"
r=$(ga "$ADMIN" /api/user)
check "đăng nhập admin (mật khẩu từ OpenBao) qua gateway" "200 admin" "$(hc "$r") $(jf 'd["login"]' <<<"$r")"

# ---------------- (2) Provisioning ----------------
r=$(ga "$ADMIN" /api/datasources/uid/dxos-app-pg)
check "datasource provisioned: PostgreSQL, role chỉ đọc cuu_tro_bi, không sửa trên giao diện" \
  "200 grafana-postgresql-datasource ${APP_BI_DB_USER:-cuu_tro_bi} True" \
  "$(hc "$r") $(jf '"%s %s %s" % (d["type"], d["user"], d["readOnly"])' <<<"$r")"
r=$(ga "$ADMIN" "/api/dashboards/uid/$UID_DB")
printf '%s' "${r#* }" >"$TMP/db.json"
check "dashboard Điều hành cứu trợ đã nạp từ tệp (provisioned, thư mục Điều hành)" "200 Điều hành cứu trợ True Điều hành" \
  "$(hc "$r") $(jf '"%s %s %s" % (d["dashboard"]["title"], d["meta"]["provisioned"], d["meta"]["folderTitle"])' <<<"$r")"
check "dashboard có đủ panel điều hành" True \
  "$(jf 'all(any(k in p["title"] for p in d["dashboard"]["panels"]) for k in ("trạng thái", "phản hồi", "Mực nước", "Tồn kho", "Quỹ", "Thu / chi"))' <<<"$r")"

# ---------------- (3) Truy vấn ----------------
loi=$(python3 - "$TMP/db.json" "$G" "$ADMIN" <<'PY'
import base64, json, sys, urllib.request
db, g, auth = json.load(open(sys.argv[1]))["dashboard"], sys.argv[2], sys.argv[3]
hong = []
for p in db["panels"]:
    for t in p.get("targets", []):
        body = json.dumps({"from": "now-30d", "to": "now", "queries": [{**t, "refId": "A"}]}).encode()
        req = urllib.request.Request(g + "/api/ds/query", data=body, headers={
            "Content-Type": "application/json", "Authorization": "Basic " + base64.b64encode(auth.encode()).decode()})
        try:
            r = json.load(urllib.request.urlopen(req, timeout=30))
            e = r["results"]["A"].get("error")
        except Exception as ex:  # noqa: BLE001
            e = str(ex)
        if e:
            hong.append(f"{p['title']}: {e[:120]}")
print("; ".join(hong) if hong else "khong-loi")
PY
)
check "mọi truy vấn của mọi panel chạy được qua datasource" khong-loi "$loi"
r=$(q "SELECT count(*) AS n FROM cuu_tro.incidents WHERE status NOT IN ('da_cuu', 'dong')")
check "panel 'Tin kêu cứu đang mở' trả đúng số liệu CSDL" \
  "200 $(sql <<<"SELECT count(*) FROM cuu_tro.incidents WHERE status NOT IN ('da_cuu','dong');")" \
  "$(hc "$r") $(jf 'd["results"]["A"]["frames"][0]["data"]["values"][0][0]' <<<"$r")"
r=$(q "SELECT coalesce(sum(CASE direction WHEN 'thu' THEN amount ELSE -amount END), 0) AS so_du FROM cuu_tro.relief_fund_entries")
check "số dư quỹ qua Grafana khớp CSDL" "$(sql <<<"SELECT coalesce(sum(CASE direction WHEN 'thu' THEN amount ELSE -amount END),0)::bigint FROM cuu_tro.relief_fund_entries;")" \
  "$(jf 'int(float(d["results"]["A"]["frames"][0]["data"]["values"][0][0]))' <<<"$r")"

# ---------------- (4) Chỉ đọc, không định danh ----------------
check "datasource không đọc được SĐT người báo" True \
  "$(q 'SELECT reporter_phone FROM cuu_tro.incidents LIMIT 1' | jf '"permission denied" in (d["results"]["A"].get("error") or "")')"
check "datasource không đọc được họ tên người báo" True \
  "$(q 'SELECT reporter_name FROM cuu_tro.incidents LIMIT 1' | jf '"permission denied" in (d["results"]["A"].get("error") or "")')"
check "datasource không ghi được (read-only / không quyền)" True \
  "$(q "UPDATE cuu_tro.supplies SET quantity = quantity" | jf '(lambda e: "read-only" in e or "permission denied" in e)(d["results"]["A"].get("error") or "")')"
check "datasource không đọc được bảng ngoài danh sách (thành viên đội)" True \
  "$(q 'SELECT * FROM cuu_tro.team_members LIMIT 1' | jf '"permission denied" in (d["results"]["A"].get("error") or "")')"

# ---------------- (5) SSO Keycloak (#126) ----------------
KC="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-disaster}"
# Token Admin REST của admin bootstrap (mật khẩu từ OpenBao, đi qua biến môi trường của python, không lên dòng lệnh)
KC_ADMIN_PASSWORD=$(kv core/keycloak-admin password) KC_URL=$KC python3 -c '
import json, os, urllib.parse, urllib.request
d = urllib.parse.urlencode({"grant_type": "password", "client_id": "admin-cli",
    "username": os.environ.get("KC_BOOTSTRAP_ADMIN_USERNAME", "admin"), "password": os.environ["KC_ADMIN_PASSWORD"]}).encode()
print(json.load(urllib.request.urlopen(os.environ["KC_URL"] + "/realms/master/protocol/openid-connect/token", d, timeout=30))["access_token"])
' >"$TMP/kc_token"
# kca <phương thức> <đường dẫn sau /admin/realms/$REALM> [body JSON]: in "<mã HTTP> <body>"
kca() {
  local out code
  out=$(mktemp)
  code=$(curl -s -m 30 -o "$out" -w '%{http_code}' -K <(printf 'header = "Authorization: Bearer %s"\n' "$(cat "$TMP/kc_token")") \
    -H 'Content-Type: application/json' -X "$1" ${3:+-d "$3"} "$KC/admin/realms/$REALM$2")
  printf '%s %s\n' "$code" "$(tr -d '\n' <"$out")"
  rm -f "$out"
}
check "keycloak-grafana-client chạy xong (exit 0)" "exited 0" \
  "$(docker compose ps -a --format '{{.State}} {{.ExitCode}}' keycloak-grafana-client)"
r=$(kca GET "/clients?clientId=dxos-grafana")
check "client dxos-grafana: một, confidential, chỉ standard flow, PKCE S256, redirect đúng /grafana/login/generic_oauth" \
  "200 1 False True False False S256 ${GATEWAY_PUBLIC_URL:-http://localhost:9080}/grafana/login/generic_oauth" \
  "$(hc "$r") $(jf '"%d %s %s %s %s %s %s" % (len(d), d[0]["publicClient"], d[0]["standardFlowEnabled"], d[0]["directAccessGrantsEnabled"], d[0]["implicitFlowEnabled"], d[0]["attributes"].get("pkce.code.challenge.method"), ",".join(d[0]["redirectUris"]))' <<<"$r")"
CID=$(jf 'd[0]["id"]' <<<"$r")
check "client dxos-grafana có mapper vai realm → claim roles (id token + userinfo)" True \
  "$(jf 'any(m["name"] == "dxos-realm-roles" and m["config"].get("claim.name") == "roles" and m["config"].get("userinfo.token.claim") == "true" for m in d[0].get("protocolMappers", []))' <<<"$r")"
check "secret client trong Keycloak khớp OpenBao secret/core/grafana-oauth (không in ra)" True \
  "$([ "$(kca GET "/clients/$CID/client-secret" | jf 'd["value"]')" = "$(kv core/grafana-oauth client_secret)" ] && echo True || echo False)"
# Idempotent: chạy lại container (như máy có realm cũ bật lại profile bi) → vẫn một client, cùng id
lan2=$(docker compose --profile core --profile app --profile bi run --rm --no-deps keycloak-grafana-client 2>&1 | tail -n 3 | tr '\n' ' ')
check "chạy lại keycloak-grafana-client: cập nhật, không tạo trùng" "True 1 $CID" \
  "$([[ $lan2 == *"đã cập nhật"* && $lan2 == *"dxos-realm-roles: đã có"* ]] && echo True || echo "$lan2") $(kca GET "/clients?clientId=dxos-grafana" | jf '"%d %s" % (len(d), d[0]["id"])')"
CB=$(python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$G/login/generic_oauth")
# Thiếu code_challenge: Keycloak không hiện trang đăng nhập, trả lỗi về redirect_uri (error=invalid_request)
check "Keycloak từ chối yêu cầu đăng nhập dxos-grafana không có PKCE" "302 invalid_request code_challenge" \
  "$(curl -s -m 15 -o /dev/null -w '%{http_code} %{redirect_url}' "$KC/realms/$REALM/protocol/openid-connect/auth?client_id=dxos-grafana&response_type=code&scope=openid&redirect_uri=$CB&state=x" \
     | python3 -c 'import sys,urllib.parse as u; c,l=sys.stdin.read().split(" ",1); q=dict(u.parse_qsl(u.urlsplit(l.strip()).query)); print(c, q.get("error"), "code_challenge" if "code_challenge" in q.get("error_description","") else q.get("error_description"))')"
check "Keycloak từ chối redirect_uri lạ cho dxos-grafana" 400 \
  "$(curl -s -m 15 -o /dev/null -w '%{http_code}' "$KC/realms/$REALM/protocol/openid-connect/auth?client_id=dxos-grafana&response_type=code&scope=openid&redirect_uri=http%3A%2F%2Fevil.example.invalid%2Fcb&state=x&code_challenge=abcdefghijklmnopqrstuvwxyzabcdefghijklmnopq&code_challenge_method=S256")"
check "GET /grafana/login: form tắt, tự chuyển sang SSO" "307 $G/login/generic_oauth" \
  "$(curl -s -m 15 -o /dev/null -w '%{http_code} %{redirect_url}' "$G/login" | cut -d'?' -f1)"
check "form đăng nhập tắt: POST /grafana/login bằng mật khẩu admin không tạo phiên" True \
  "$(c=$(curl -s -m 15 -o /dev/null -w '%{http_code}' -c "$TMP/form.jar" -H 'Content-Type: application/json' \
      -d "$(python3 -c 'import json,sys; print(json.dumps({"user": "admin", "password": sys.argv[1]}))' "${ADMIN#admin:}")" "$G/login")
     grep -q grafana_session "$TMP/form.jar" 2>/dev/null && echo "co-phien $c" || echo True)"
check "admin khẩn cấp vẫn gọi được API bằng Basic auth (mật khẩu OpenBao)" 200 "$(hc "$(ga "$ADMIN" /api/user)")"

# User dieu-phoi tạm (không đụng OTP của dieuphoi01 mà smoke-jwt kiểm), xóa khi kết thúc
SU="smoke-grafana-$(openssl rand -hex 3)"
SP=$(openssl rand -hex 16)
kca POST /users "$(python3 -c 'import json,sys; print(json.dumps({"username": sys.argv[1], "enabled": True, "email": sys.argv[1] + "@example.invalid", "emailVerified": True, "firstName": "Smoke", "lastName": "Grafana", "credentials": [{"type": "password", "value": sys.argv[2], "temporary": False}]}))' "$SU" "$SP")" >/dev/null
SUID=$(kca GET "/users?username=$SU&exact=true" | jf 'd[0]["id"]')
trap 'kca DELETE "/users/$SUID" >/dev/null 2>&1 || true; rm -rf "$TMP"' EXIT
kca POST "/users/$SUID/role-mappings/realm" "[$(kca GET /roles/dieu-phoi | cut -d' ' -f2-)]" >/dev/null
sso() { SSO_PASSWORD=$2 python3 scripts/grafana-sso.py "$G" "$1" "$UID_DB"; }

r="0 $(sso "$SU" "$SP")"
echo "      ${r#0 }"
check "SSO dieu-phoi: /grafana/login/generic_oauth → Keycloak, client dxos-grafana, PKCE S256, quay về qua gateway" \
  "True dxos-grafana S256 $G/login/generic_oauth" \
  "$(jf '"%s %s %s %s" % (d["chuyen_keycloak"], d["client_id"], d["pkce"], d["redirect_uri"])' <<<"$r")"
check "SSO dieu-phoi: bị bắt cài OTP, xong OTP thì có phiên Grafana" "True True" "$(jf '"%s %s" % (d.get("otp"), d.get("co_phien"))' <<<"$r")"
check "SSO dieu-phoi → vai Editor, không phải Grafana Admin, tên đăng nhập theo preferred_username" "Editor False $SU" \
  "$(jf '"%s %s %s" % (d.get("role"), d.get("grafana_admin"), d.get("login"))' <<<"$r")"
check "SSO dieu-phoi lấy được dashboard Điều hành cứu trợ qua APISIX" "Điều hành cứu trợ True" \
  "$(jf '"%s %s" % (d.get("dashboard"), d.get("so_panel", 0) > 0)' <<<"$r")"
check "SSO dieu-phoi (Editor) có quyền tạo dashboard riêng" True "$(jf 'd.get("tao_dashboard")' <<<"$r")"
check "đăng xuất Grafana chuyển sang trang đăng xuất Keycloak" "302 $KC/realms/$REALM/protocol/openid-connect/logout" \
  "$(jf 'd.get("dang_xuat")' <<<"$r")"

r="0 $(sso cuuho01 "${KC_DEMO_USER_PASSWORD:?}")"
echo "      ${r#0 }"
check "SSO cuu-ho: không hỏi OTP → vai Viewer, lấy được dashboard" "False Viewer Điều hành cứu trợ" \
  "$(jf '"%s %s %s" % (d.get("otp"), d.get("role"), d.get("dashboard"))' <<<"$r")"
check "SSO cuu-ho (Viewer) không có quyền tạo dashboard" False "$(jf 'd.get("tao_dashboard")' <<<"$r")"

r="0 $(sso tinhnguyen01 "${KC_DEMO_USER_PASSWORD:?}")"
echo "      ${r#0 }"
check "SSO tinh-nguyen: Keycloak cho qua nhưng Grafana từ chối (không có phiên)" "True False" \
  "$(jf '"%s %s" % (d.get("ve_grafana"), d.get("co_phien"))' <<<"$r")"
check "không tạo tài khoản Grafana cho tinh-nguyen" 404 "$(hc "$(ga "$ADMIN" '/api/users/lookup?loginOrEmail=tinhnguyen01')")"
# Dọn tài khoản Grafana của user tạm (user Keycloak xóa trong trap). Gateway không cho DELETE: gọi thẳng Grafana
# trong container, mật khẩu admin đọc từ tệp bí mật đã render, không lên dòng lệnh.
gid=$(ga "$ADMIN" "/api/users/lookup?loginOrEmail=$SU" | jf 'd.get("id", "")' 2>/dev/null || true)
if [ -n "$gid" ]; then
  docker compose exec -T grafana sh -c 'curl -s -m 15 -o /dev/null -K - -X DELETE "http://127.0.0.1:3000/grafana/api/admin/users/$1"' _ "$gid" \
    < <(printf 'user = "admin:%s"\n' "${ADMIN#admin:}")
fi
check "đã dọn tài khoản Grafana của user tạm" 404 "$(hc "$(ga "$ADMIN" "/api/users/lookup?loginOrEmail=$SU")")"

if [ "$fail" -ne 0 ]; then echo "smoke-grafana: CÓ LỖI"; exit 1; fi
echo "smoke-grafana: tất cả đều đạt"
