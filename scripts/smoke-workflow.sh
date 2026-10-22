#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử workflow Temporal của apps/cuu-tro (#29), gọi THẬT qua APISIX /workflow/* bằng token
# Keycloak của 3 user mẫu, kiểm kết quả trong PostgreSQL và Temporal (CLI trong container temporal):
# (1) workflow Hello qua gateway → API → Temporal → worker;
# (2) không token → 401; tinh-nguyen, cuu-ho khởi chạy phân công → 403;
# (3) dieu-phoi khởi chạy PhanCongCuuHo cho tin seed b…04 → đội sẵn sàng gần nhất (seed: Đội xung kích
#     thôn 1) được gán, tin phan_cong, đội dang_lam_nhiem_vu; khởi chạy trùng → 409;
# (4) cuu-ho đội khác không xem/xác nhận được (403); cuu-ho của đội được gán gửi xác nhận → tin dong,
#     đội trở lại san_sang; workflow COMPLETED trong Temporal; tin đã đóng không phân công lại (409).
# Tin seed, đội và thành viên đội được đặt lại trạng thái seed trước và sau khi chạy.
# Dùng: make up && make seed && bash scripts/smoke-workflow.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

KC="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-disaster}"
GW="http://localhost:${APISIX_PORT:-9080}"
INC=b0000000-0000-4000-8000-000000000004     # "Người bị thương ở chân" (seed, tiep_nhan)
TEAM_GAN=a0000000-0000-4000-8000-000000000001 # Đội xung kích thôn 1: sẵn sàng, gần nhất (~430 m)
TEAM_CANO=a0000000-0000-4000-8000-000000000002 # đội của cuuho01 trong seed
WF="phan-cong-$INC"
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
sub_of() { python3 -c 'import sys,json,base64; p=sys.argv[1].split(".")[1]; p+="="*(-len(p)%4); print(json.loads(base64.urlsafe_b64decode(p))["sub"])' "$1"; }
# api <token|-> <METHOD> <đường dẫn sau /workflow> [body JSON]: in "<mã HTTP> <body>"
api() {
  local tok=$1 method=$2 path=$3 body=${4:-} out code
  out=$(mktemp)
  local args=(-s -o "$out" -w '%{http_code}' -X "$method" -H 'Content-Type: application/json')
  [ -n "$body" ] && args+=(-d "$body")
  if [ "$tok" = - ]; then code=$(curl "${args[@]}" "$GW/workflow$path")
  else code=$(curl -K <(printf 'header = "Authorization: Bearer %s"\n' "$tok") "${args[@]}" "$GW/workflow$path"); fi
  printf '%s %s\n' "$code" "$(cat "$out")"
  rm -f "$out"
}
http_code() { printf '%s' "${1%% *}"; }
# jf <biểu thức python trên d>: đọc phần body JSON (sau mã HTTP) của kết quả api từ stdin
jf() { python3 -c 'import sys,json; d=json.loads(sys.stdin.read().split(" ", 1)[1]); print(eval(sys.argv[1], {"d": d}))' "$1"; }
sql() { docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -q -v ON_ERROR_STOP=1'; }
temporal_cli() { docker compose exec -T temporal sh -c "temporal $* --address temporal:7233"; }

D=$(get_token dieuphoi01); C=$(get_token cuuho01); T=$(get_token tinhnguyen01)
C_SUB=$(sub_of "$C")
reset() {
  temporal_cli workflow terminate -w "$WF" --reason smoke-reset >/dev/null 2>&1 || true
  sql >/dev/null <<SQL
UPDATE cuu_tro.incidents SET status = 'tiep_nhan', assigned_team_id = NULL WHERE id = '$INC';
UPDATE cuu_tro.rescue_teams SET status = 'san_sang' WHERE id = '$TEAM_GAN';
INSERT INTO cuu_tro.team_members (user_id, team_id, username) VALUES ('$C_SUB', '$TEAM_CANO', 'cuuho01')
  ON CONFLICT (user_id) DO UPDATE SET team_id = EXCLUDED.team_id;
SQL
}
reset
trap reset EXIT

# ---------- (1) Hello ----------
out=$(api "$C" POST /hello '{"ten":"smoke"}')
check "POST /workflow/hello (cuu-ho) → worker trả lời" "200 True" \
  "$(http_code "$out") $(jf '"Xin chào smoke" in d["ket_qua"]' <<<"$out")"

# ---------- (2) Từ chối ----------
check "phân công không token (APISIX chặn)" 401 "$(http_code "$(api - POST "/phan-cong/$INC")")"
check "phân công bằng tinh-nguyen" 403 "$(http_code "$(api "$T" POST "/phan-cong/$INC")")"
check "phân công bằng cuu-ho" 403 "$(http_code "$(api "$C" POST "/phan-cong/$INC")")"
check "phân công tin không tồn tại" 404 "$(http_code "$(api "$D" POST /phan-cong/b0000000-0000-4000-8000-0000000000ff)")"
check "workflow_id không đúng dạng" 404 "$(http_code "$(api "$D" GET /khong-co)")"

# ---------- (3) dieu-phoi khởi chạy ----------
out=$(api "$D" POST "/phan-cong/$INC")
check "dieu-phoi khởi chạy PhanCongCuuHo" "202 $WF" "$(http_code "$out") $(jf 'd["workflow_id"]' <<<"$out")"
buoc=""
for _ in $(seq 1 30); do
  out=$(api "$D" GET "/$WF")
  buoc=$(jf 'd["chi_tiet"]["buoc"]' <<<"$out" 2>/dev/null || true)
  [ "$buoc" = cho_xac_nhan ] && break
  sleep 1
done
check "workflow tới bước chờ xác nhận, gán đội gần nhất" "cho_xac_nhan $TEAM_GAN" \
  "$buoc $(jf 'd["chi_tiet"]["doi_id"]' <<<"$out")"
check "DB: tin phan_cong, gán Đội xung kích thôn 1; đội dang_lam_nhiem_vu" "phan_cong|$TEAM_GAN|dang_lam_nhiem_vu" \
  "$(sql <<<"SELECT i.status || '|' || i.assigned_team_id || '|' || t.status FROM cuu_tro.incidents i JOIN cuu_tro.rescue_teams t ON t.id = i.assigned_team_id WHERE i.id = '$INC'")"
check "khởi chạy lần hai khi tin đã phân công" 409 "$(http_code "$(api "$D" POST "/phan-cong/$INC")")"

# ---------- (4) Xác nhận ----------
check "cuu-ho đội khác xem workflow" 403 "$(http_code "$(api "$C" GET "/$WF")")"
check "cuu-ho đội khác xác nhận" 403 "$(http_code "$(api "$C" POST "/$WF/xac-nhan")")"
check "tinh-nguyen xác nhận" 403 "$(http_code "$(api "$T" POST "/$WF/xac-nhan")")"
# cuuho01 chuyển sang đội được gán (điều phối đổi đội, có hiệu lực ngay ở truy vấn kế tiếp, #26)
sql >/dev/null <<<"UPDATE cuu_tro.team_members SET team_id = '$TEAM_GAN' WHERE user_id = '$C_SUB'"
check "cuu-ho của đội được gán xem workflow" 200 "$(http_code "$(api "$C" GET "/$WF")")"
check "cuu-ho của đội được gán xác nhận đã cứu" 202 "$(http_code "$(api "$C" POST "/$WF/xac-nhan" '{"ghi_chu":"da dua nguoi bi thuong len tram y te"}')")"
for _ in $(seq 1 30); do
  out=$(api "$D" GET "/$WF")
  [ "$(jf 'd["trang_thai"]' <<<"$out" 2>/dev/null || true)" = COMPLETED ] && break
  sleep 1
done
check "workflow kết thúc: da_dong, người xác nhận cuuho01" "COMPLETED da_dong cuuho01" \
  "$(jf 'd["trang_thai"] + " " + str(d["chi_tiet"]["ket_qua"]) + " " + d["chi_tiet"]["xac_nhan"]["nguoi"]' <<<"$out")"
check "DB: tin dong, đội trở lại san_sang" "dong|san_sang" \
  "$(sql <<<"SELECT i.status || '|' || t.status FROM cuu_tro.incidents i JOIN cuu_tro.rescue_teams t ON t.id = i.assigned_team_id WHERE i.id = '$INC'")"
check "xác nhận lần hai khi workflow đã xong" 409 "$(http_code "$(api "$D" POST "/$WF/xac-nhan")")"
check "phân công lại tin đã đóng" 409 "$(http_code "$(api "$D" POST "/phan-cong/$INC")")"
check "Temporal (CLI): workflow PhanCongCuuHo COMPLETED trên task queue cuu-tro" "PhanCongCuuHo COMPLETED ${CUU_TRO_TASK_QUEUE:-cuu-tro}" \
  "$(temporal_cli workflow describe -w "$WF" -o json | python3 -c '
import sys, json
i = json.load(sys.stdin)["workflowExecutionInfo"]
print(i["type"]["name"], i["status"].replace("WORKFLOW_EXECUTION_STATUS_", ""), i.get("taskQueue", ""))')"
exit $fail
