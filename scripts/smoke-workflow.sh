#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử workflow Temporal của apps/cuu-tro (#29, #67), gọi THẬT qua APISIX /workflow/* bằng token
# Keycloak của 3 user mẫu, kiểm kết quả trong PostgreSQL và Temporal (CLI trong container temporal):
# (1) workflow Hello qua gateway → API → Temporal → worker;
# (2) không token → 401; tinh-nguyen, cuu-ho khởi chạy phân công → 403;
# (3) dieu-phoi khởi chạy tay PhanCongCuuHo cho tin seed b…04 (seed không tự khởi chạy) → đội sẵn sàng
#     gần nhất (seed: Đội xung kích thôn 1) được giao, tin phan_cong, đội dang_lam_nhiem_vu, lịch sử
#     giao cho_nhan; khởi chạy trùng → 409;
# (4) cuu-ho đội khác không xem/nhận/xác nhận được (403); cuu-ho của đội được giao nhận nhiệm vụ → tin
#     dang_cuu, lịch sử da_nhan; hủy sau khi đã nhận → 409; xác nhận đã cứu → tin dong, đội san_sang;
#     workflow COMPLETED trong Temporal; tin đã đóng không phân công lại (409);
# (5) TỰ KHỞI CHẠY (#67): dieu-phoi tạo tin khan_cap mới qua /graphql → không gọi API, workflow
#     phan-cong-<id> tự chạy (outbox assignment_queue), giao đội gần nhất; khởi chạy tay → 409; đội từ
#     chối → workflow tự giao đội gần nhất kế tiếp, lịch sử tu_choi; đội cũ bấm nhận muộn → 403;
#     điều phối hủy → tin về tiep_nhan, đội trở lại san_sang. (Quá hạn nhận / hết lần giao / ưu tiên
#     urgency kiểm bằng pytest time-skipping: hạn thật tính bằng phút.)
# Tin seed, đội và thành viên đội được đặt lại trạng thái seed trước và sau khi chạy; tin của (5) bị xóa.
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

# cho_wf <workflow_id> <biểu thức python trên d (phản hồi GET)>: chờ tối đa 30 giây, in phản hồi cuối
cho_wf() {
  local out=""
  for _ in $(seq 1 30); do
    out=$(api "$D" GET "/$1")
    [ "$(jf "$2" <<<"$out" 2>/dev/null || true)" = True ] && break
    sleep 1
  done
  printf '%s' "$out"
}
# lich_su_giao <incident_id>: "đội:kết quả:người,…" theo thứ tự giao (bảng incident_assignments, #67)
lich_su_giao() {
  sql <<<"SELECT coalesce(string_agg(team_id || ':' || result || ':' || coalesce(responded_by, '-'), ',' ORDER BY assigned_at, attempt_no), '') FROM cuu_tro.incident_assignments WHERE incident_id = '$1'"
}

D=$(get_token dieuphoi01); C=$(get_token cuuho01); T=$(get_token tinhnguyen01)
C_SUB=$(sub_of "$C")
NEW=''
reset() {
  temporal_cli workflow terminate -w "$WF" --reason smoke-reset >/dev/null 2>&1 || true
  local xoa_new=""
  if [ -n "$NEW" ]; then
    temporal_cli workflow terminate -w "phan-cong-$NEW" --reason smoke-reset >/dev/null 2>&1 || true
    xoa_new="DELETE FROM cuu_tro.incidents WHERE id = '$NEW';"
  fi
  sql >/dev/null <<SQL
UPDATE cuu_tro.incidents SET status = 'tiep_nhan', assigned_team_id = NULL WHERE id = '$INC';
DELETE FROM cuu_tro.incident_assignments WHERE incident_id = '$INC';
DELETE FROM cuu_tro.assignment_queue WHERE incident_id = '$INC';
$xoa_new
UPDATE cuu_tro.rescue_teams SET status = 'san_sang' WHERE id IN ('$TEAM_GAN', '$TEAM_CANO');
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

# ---------- (3) dieu-phoi khởi chạy tay ----------
out=$(api "$D" POST "/phan-cong/$INC")
check "dieu-phoi khởi chạy PhanCongCuuHo" "202 $WF" "$(http_code "$out") $(jf 'd["workflow_id"]' <<<"$out")"
out=$(cho_wf "$WF" 'd["chi_tiet"]["buoc"] == "cho_nhan"')
check "workflow tới bước chờ nhận, giao đội gần nhất, hạn nhận theo urgency cao" "cho_nhan $TEAM_GAN ${PHAN_CONG_HAN_NHAN_GIAY_CAO:-600}" \
  "$(jf 'd["chi_tiet"]["buoc"] + " " + str(d["chi_tiet"]["doi_id"]) + " " + str(d["chi_tiet"]["han_nhan_giay"])' <<<"$out")"
check "DB: tin phan_cong, gán Đội xung kích thôn 1; đội dang_lam_nhiem_vu" "phan_cong|$TEAM_GAN|dang_lam_nhiem_vu" \
  "$(sql <<<"SELECT i.status || '|' || i.assigned_team_id || '|' || t.status FROM cuu_tro.incidents i JOIN cuu_tro.rescue_teams t ON t.id = i.assigned_team_id WHERE i.id = '$INC'")"
check "DB: lịch sử giao lần 1 cho_nhan, hạn nhận sau lúc giao" "$TEAM_GAN:cho_nhan:-|t" \
  "$(lich_su_giao "$INC")|$(sql <<<"SELECT bool_and(deadline_at > assigned_at) FROM cuu_tro.incident_assignments WHERE incident_id = '$INC'")"
check "khởi chạy lần hai khi tin đã phân công" 409 "$(http_code "$(api "$D" POST "/phan-cong/$INC")")"

# ---------- (4) Nhận nhiệm vụ, xác nhận ----------
check "cuu-ho đội khác xem workflow" 403 "$(http_code "$(api "$C" GET "/$WF")")"
check "cuu-ho đội khác nhận nhiệm vụ" 403 "$(http_code "$(api "$C" POST "/$WF/nhan")")"
check "cuu-ho đội khác xác nhận" 403 "$(http_code "$(api "$C" POST "/$WF/xac-nhan")")"
check "tinh-nguyen xác nhận" 403 "$(http_code "$(api "$T" POST "/$WF/xac-nhan")")"
check "cuu-ho hủy (chỉ dieu-phoi)" 403 "$(http_code "$(api "$C" POST "/$WF/huy")")"
# cuuho01 chuyển sang đội được giao (điều phối đổi đội, có hiệu lực ngay ở truy vấn kế tiếp, #26)
sql >/dev/null <<<"UPDATE cuu_tro.team_members SET team_id = '$TEAM_GAN' WHERE user_id = '$C_SUB'"
check "cuu-ho của đội được giao xem workflow" 200 "$(http_code "$(api "$C" GET "/$WF")")"
check "cuu-ho của đội được giao nhận nhiệm vụ" 202 "$(http_code "$(api "$C" POST "/$WF/nhan" '{"ghi_chu":"dang di ca no toi"}')")"
out=$(cho_wf "$WF" 'd["chi_tiet"]["buoc"] == "cho_xac_nhan"')
check "workflow sang bước chờ xác nhận đã cứu" cho_xac_nhan "$(jf 'd["chi_tiet"]["buoc"]' <<<"$out")"
check "DB: tin dang_cuu; lịch sử da_nhan bởi cuuho01" "dang_cuu|$TEAM_GAN:da_nhan:cuuho01" \
  "$(sql <<<"SELECT status FROM cuu_tro.incidents WHERE id = '$INC'")|$(lich_su_giao "$INC")"
check "hủy khi đội đã nhận" 409 "$(http_code "$(api "$D" POST "/$WF/huy")")"
check "cuu-ho của đội được giao xác nhận đã cứu" 202 "$(http_code "$(api "$C" POST "/$WF/xac-nhan" '{"ghi_chu":"da dua nguoi bi thuong len tram y te"}')")"
out=$(cho_wf "$WF" 'd["trang_thai"] == "COMPLETED"')
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

# ---------- (5) Tự khởi chạy khi có tin mới, từ chối → phân công lại, hủy (#67) ----------
# cuuho01 vẫn thuộc Đội xung kích thôn 1 (đội gần nhất của tin mới). SĐT giả riêng mỗi lần chạy.
PHONE="0968$(date +%H%M%S | cut -c1-6)"
# shellcheck disable=SC2016 # $o là biến GraphQL
body=$(python3 -c 'import json,sys; print(json.dumps({"query": "mutation($o: incidents_insert_input!) { insert_incidents_one(object: $o) { id status } }", "variables": {"o": {"description": "[smoke #67] nuoc dang len nhanh, 3 nguoi tren mai", "location": {"type": "Point", "coordinates": [108.1003, 15.8528]}, "urgency": "khan_cap", "people_count": 3, "reporter_phone": sys.argv[1], "source": "web"}}}))' "$PHONE")
out=$(curl -s -K <(printf 'header = "Authorization: Bearer %s"\n' "$D") -H 'Content-Type: application/json' -H 'X-Hasura-Role: dieu-phoi' -d "$body" "$GW/graphql")
NEW=$(python3 -c 'import sys,json; print(json.load(sys.stdin)["data"]["insert_incidents_one"]["id"])' <<<"$out" 2>/dev/null || true)
check "dieu-phoi tạo tin khan_cap qua /graphql (không gọi /workflow)" True "$([[ $NEW =~ ^[0-9a-f-]{36}$ ]] && echo True || echo "$out")"
WF2="phan-cong-$NEW"
out=$(cho_wf "$WF2" 'd["chi_tiet"]["buoc"] == "cho_nhan"')
check "workflow $WF2 TỰ khởi chạy, giao đội gần nhất, hạn nhận khan_cap" "cho_nhan $TEAM_GAN ${PHAN_CONG_HAN_NHAN_GIAY_KHAN_CAP:-300} True" \
  "$(jf 'd["chi_tiet"]["buoc"] + " " + str(d["chi_tiet"]["doi_id"]) + " " + str(d["chi_tiet"]["han_nhan_giay"]) + " " + str("tu-dong" in d["chi_tiet"]["lich_su"][0])' <<<"$out" 2>/dev/null || echo "$out")"
check "DB: outbox đã khởi chạy (started_at), tin phan_cong" "t|phan_cong" \
  "$(sql <<<"SELECT (q.started_at IS NOT NULL)::text || '|' || i.status FROM cuu_tro.assignment_queue q JOIN cuu_tro.incidents i ON i.id = q.incident_id WHERE q.incident_id = '$NEW'")"
check "khởi chạy tay khi đã tự chạy" 409 "$(http_code "$(api "$D" POST "/phan-cong/$NEW")")"
check "đội được giao từ chối" 202 "$(http_code "$(api "$C" POST "/$WF2/tu-choi" '{"ghi_chu":"ca no dang sua"}')")"
out=$(cho_wf "$WF2" 'd["chi_tiet"]["buoc"] == "cho_nhan" and d["chi_tiet"]["doi_id"] != "'"$TEAM_GAN"'"')
check "workflow tự giao đội gần nhất kế tiếp (Đội ca nô)" "cho_nhan $TEAM_CANO 2" \
  "$(jf 'd["chi_tiet"]["buoc"] + " " + str(d["chi_tiet"]["doi_id"]) + " " + str(len(d["chi_tiet"]["giao"]))' <<<"$out")"
check "DB: lịch sử tu_choi (cuuho01) rồi cho_nhan; đội từ chối trở lại san_sang" "$TEAM_GAN:tu_choi:cuuho01,$TEAM_CANO:cho_nhan:-|san_sang" \
  "$(lich_su_giao "$NEW")|$(sql <<<"SELECT status FROM cuu_tro.rescue_teams WHERE id = '$TEAM_GAN'")"
check "đội cũ bấm nhận muộn sau khi đã bị thay" 403 "$(http_code "$(api "$C" POST "/$WF2/nhan")")"
check "dieu-phoi hủy khi đội mới chưa nhận" 202 "$(http_code "$(api "$D" POST "/$WF2/huy" '{"ly_do":"smoke"}')")"
out=$(cho_wf "$WF2" 'd["trang_thai"] == "COMPLETED"')
check "workflow kết thúc da_huy" "COMPLETED da_huy" "$(jf 'd["trang_thai"] + " " + str(d["chi_tiet"]["ket_qua"])' <<<"$out")"
check "DB: tin về tiep_nhan không đội, Đội ca nô san_sang, lịch sử huy bởi dieuphoi01" "tiep_nhan||san_sang|$TEAM_CANO:huy:dieuphoi01" \
  "$(sql <<<"SELECT i.status || '|' || coalesce(i.assigned_team_id::text, '') || '|' || t.status FROM cuu_tro.incidents i, cuu_tro.rescue_teams t WHERE i.id = '$NEW' AND t.id = '$TEAM_CANO'")|$(lich_su_giao "$NEW" | cut -d, -f2)"
exit $fail
