#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử Grafana OSS dashboard điều hành (#92). Tự bật profile bi nếu Grafana chưa chạy, gọi THẬT qua APISIX:
# (1) Grafana image gốc, không mở cổng ra host, sống qua gateway /grafana/api/health; chưa đăng nhập → 401;
#     sai mật khẩu → 401; không đăng ký được; WAF vẫn chặn XSS trong tham số;
# (2) đăng nhập admin (mật khẩu từ OpenBao): datasource provisioned dùng role chỉ đọc cuu_tro_bi, không sửa
#     được trên giao diện; dashboard "Điều hành cứu trợ" đã nạp từ tệp, đủ panel;
# (3) mọi truy vấn của mọi panel chạy được qua /api/ds/query (không lỗi); một truy vấn trả đúng số liệu CSDL;
# (4) datasource không đọc được SĐT/họ tên, không ghi được (read-only).
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
  bash scripts/openbao-init.sh >/dev/null
  docker compose --profile core --profile app --profile bi up -d grafana >/dev/null 2>&1
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

if [ "$fail" -ne 0 ]; then echo "smoke-grafana: CÓ LỖI"; exit 1; fi
echo "smoke-grafana: tất cả đều đạt"
