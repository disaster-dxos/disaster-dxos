#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Chạy lại từng luồng demo 15 phút (#130) trên stack THẬT qua APISIX, theo thứ tự của
# docs/trinh-bay/kich-ban-demo.md. Dùng khi trình bày (bấm thay cho thao tác tay) và làm phương án dự phòng
# khi giao diện hỏng: mỗi bước in ra đúng điều cần nói. Mọi dữ liệu là dữ liệu giả (SĐT 090013xxxx, mỗi lần chạy
# một số mới nên chạy lại được).
#   chuan-bi  dữ liệu nền: seed + 8 tin kêu cứu + trận lũ mẫu (scripts/chup-anh/du-lieu-demo.sh), nhập kho,
#             thu quỹ, bật Grafana (profile bi)
#   1  ai         tình nguyện viên dán tin tự do → AI bóc tách → hàng chờ duyệt (thêm --duyet: điều phối duyệt qua API)
#   2  ban-do     tin kêu cứu mới qua API → hiện ngay trên bản đồ (subscription), tự phân công
#   3  phan-cong  trạng thái workflow phân công của tin vừa tạo (thêm --nhan: đội nhận nhiệm vụ)
#   4  offline    app hiện trường gửi lại từ hàng đợi offline: cùng Idempotency-Key 2 lần → 1 tin
#   5  canh-bao   trạm đo vượt ngưỡng (giả lập MQTT) → workflow cảnh báo → hộp thư thông báo
#   6  minh-bach  phiếu xuất kho → sổ cái → trang công khai + ledger-verify tự kiểm
#   7  grafana    dashboard điều hành (SSO Keycloak)
#   tat-ca    chuan-bi rồi 1 → 7 (1 có --duyet, 3 có --nhan)
# Dùng (từ gốc repo, sau make up): bash scripts/demo/luong.sh <bước> [--duyet|--nhan]
set -euo pipefail
cd "$(dirname "$0")/../.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

KC="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-disaster}"
GW="http://localhost:${APISIX_PORT:-9080}"
TRANG_THAI=.data/demo
mkdir -p "$TRANG_THAI" && chmod 700 "$TRANG_THAI"   # token tạm, bí mật TOTP

xanh() { printf '\033[1;36m▶ %s\033[0m\n' "$*"; }
noi() { printf '\033[0;33m  🗣  %s\033[0m\n' "$*"; }
# tok <user>: access token qua client dxos-dev-cli (CHỈ DÙNG KHI DEV). Giữ token trong .data/demo/ tới gần hết
# hạn (10 phút): điều phối viên đã cài OTP (lần đăng nhập web đầu) thì phải kèm mã TOTP, mà Keycloak không nhận
# lại một mã trong cùng 30 giây. Bí mật TOTP do quay-video.mjs ghi ở .data/demo/totp-<user>.txt (ngoài git).
tok() {
  local tep="$TRANG_THAI/tok-$1" otp=()
  if [ -s "$tep" ] && [ $(( $(date +%s) - $(stat -f %m "$tep" 2>/dev/null || stat -c %Y "$tep") )) -lt 600 ]; then
    cat "$tep"; return
  fi
  if [ -s "$TRANG_THAI/totp-$1.txt" ]; then
    otp=(-d "totp=$(python3 -c '
import base64, hashlib, hmac, struct, sys, time
k = base64.b32decode(sys.argv[1].upper() + "=" * (-len(sys.argv[1]) % 8))
h = hmac.new(k, struct.pack(">Q", int(time.time() // 30)), hashlib.sha1).digest()
o = h[-1] & 15
print("%06d" % ((struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % 1000000))' "$(tr -d ' \n' <"$TRANG_THAI/totp-$1.txt")")")
  fi
  curl -s -m 20 -X POST "$KC/realms/$REALM/protocol/openid-connect/token" \
    -d grant_type=password -d client_id=dxos-dev-cli -d scope=openid "${otp[@]}" \
    -d username="$1" --data-urlencode password="${KC_DEMO_USER_PASSWORD:?Thiếu KC_DEMO_USER_PASSWORD}" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])' >"$tep.moi"
  mv "$tep.moi" "$tep"
  cat "$tep"
}
# goi <user> <GET|POST> <đường dẫn> [body] [Idempotency-Key]: in "<mã HTTP> <phát lại 0|1> <body>"
goi() {
  local out hdr code args
  out=$(mktemp); hdr=$(mktemp)
  args=(-s -m 60 -o "$out" -D "$hdr" -w '%{http_code}' -X "$2" -H 'Content-Type: application/json')
  [ -n "${4:-}" ] && args+=(--data-binary "$4")
  [ -n "${5:-}" ] && args+=(-H "Idempotency-Key: $5")
  code=$(curl -K <(printf 'header = "Authorization: Bearer %s"\n' "$(tok "$1")") "${args[@]}" "$GW$3")
  printf '%s %s %s\n' "$code" "$(tr -d '\r' <"$hdr" | awk -F': ' 'tolower($1)=="idempotent-replayed"{print $2}' | grep -c true || true)" \
    "$(tr -d '\n' <"$out")"
  rm -f "$out" "$hdr"
}
ma() { printf '%s' "${1%% *}"; }
than() { local r=${1#* }; printf '%s' "${r#* }"; }
jf() { python3 -c 'import sys,json; d=json.loads(sys.stdin.read()); print(eval(sys.argv[1], {"d": d}))' "$1"; }
# shellcheck disable=SC2016 # biến của psql expand trong container, không phải trên máy host
sql() { timeout 60 docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -q -v ON_ERROR_STOP=1'; }
# SĐT GIẢ mỗi lần chạy một số mới (090013xxxx) để chạy lại không bị Poka-yoke chặn trùng
sdt() { printf '090013%04d' "$(( (RANDOM * 32768 + RANDOM) % 10000 ))"; }
luu() { printf '%s' "$2" >"$TRANG_THAI/$1"; }
doc() { cat "$TRANG_THAI/$1" 2>/dev/null || true; }

chuan_bi() {
  xanh "Dữ liệu nền: seed, 8 tin kêu cứu quanh Đại Lộc/Điện Bàn, trận lũ mẫu tới giờ 30 (đều giả lập)"
  make -s seed >/dev/null
  # Seed chỉ có 2 đội sẵn sàng; 8 tin nền sẽ giữ hết. Thêm 10 đội GIẢ quanh Đại Lộc/Điện Bàn để mọi tin nền có đội
  # và còn đội trống gần xã An Lạc cho các tin tạo khi trình bày (chạy lại không thêm trùng, theo tên).
  sql <<'SQL'
INSERT INTO cuu_tro.rescue_teams (name, member_count, location, location_updated_at, status, contact_name, contact_phone)
SELECT v.ten, v.so, ST_MakePoint(v.lon, v.lat)::geography, now(), 'san_sang', v.lien_he, v.sdt
FROM (VALUES
  ('Đội ca nô thôn 2 (giả định)', 5, 108.1150, 15.8450, 'Đội trưởng A (giả định)', '0900130101'),
  ('Đội xuồng thôn 3 (giả định)', 4, 108.1035, 15.8580, 'Đội trưởng B (giả định)', '0900130102'),
  ('Đội cứu hộ Ái Nghĩa (giả định)', 7, 108.1190, 15.8790, 'Đội trưởng C (giả định)', '0900130103'),
  ('Đội cứu hộ Giao Thủy (giả định)', 6, 108.1290, 15.8410, 'Đội trưởng D (giả định)', '0900130104'),
  ('Đội ca nô Duy Xuyên (giả định)', 5, 108.2590, 15.8670, 'Đội trưởng E (giả định)', '0900130105'),
  ('Đội cứu hộ Điện Bàn (giả định)', 8, 108.2300, 15.8880, 'Đội trưởng F (giả định)', '0900130106'),
  ('Đội xung kích thôn 4 (giả định)', 6, 108.0960, 15.8540, 'Đội trưởng G (giả định)', '0900130107'),
  ('Đội thanh niên An Lạc (giả định)', 10, 108.1120, 15.8500, 'Đội trưởng H (giả định)', '0900130108'),
  ('Đội ca nô Biên phòng 2 (giả định)', 6, 108.0930, 15.8610, 'Đội trưởng I (giả định)', '0900130109'),
  ('Đội cứu hộ Đại Lộc (giả định)', 9, 108.1100, 15.8650, 'Đội trưởng K (giả định)', '0900130110')
) AS v(ten, so, lon, lat, lien_he, sdt)
WHERE NOT EXISTS (SELECT 1 FROM cuu_tro.rescue_teams t WHERE t.name = v.ten);
SQL
  bash scripts/chup-anh/du-lieu-demo.sh | tail -n 3
  # Nhập kho + thu quỹ để bước 6 có hàng xuất và trang Minh bạch có số liệu
  for h in 'd0000000-0000-4000-8000-000000000001|nhap|800|Nhập gạo từ nhà hảo tâm (giả định)' \
           'd0000000-0000-4000-8000-000000000002|nhap|120|Nhập nước uống (giả định)'; do
    IFS='|' read -r sp chieu sl ghi <<<"$h"
    r=$(goi dieuphoi01 POST /workflow/kho/phieu "$(python3 -c 'import json,sys; a=sys.argv[1:]; print(json.dumps({"supply_id": a[0], "direction": a[1], "quantity": float(a[2]), "note": a[3]}, ensure_ascii=False))' "$sp" "$chieu" "$sl" "$ghi")")
    echo "  phiếu $chieu $sl → $(ma "$r")"
  done
  r=$(goi dieuphoi01 POST /workflow/quy/khoan '{"direction": "thu", "amount": 250000000, "category": "ung_ho", "purpose": "Ủng hộ đồng bào vùng lũ (giả định)"}')
  echo "  khoản thu quỹ → $(ma "$r")"
  xanh "Grafana (profile bi, SSO Keycloak)"
  make -s up-bi >/dev/null 2>&1 && echo "  $GW/grafana/ sẵn sàng"
  noi "Sẵn sàng: mở $GW/ bằng dieuphoi01 (OTP), tab thứ hai bằng cuuho01."
}

b1_ai() {
  xanh "1. Tình nguyện viên dán tin nhắn tự do → AI bóc tách → hàng chờ duyệt"
  local van_ban
  van_ban="Cuu voi!! nha toi o thon 2 xa An Lac nuoc len toi mai roi, co 3 nguoi trong do 1 ba cu 80 tuoi. Toa do 15.8455, 108.1162. SDT $(sdt)"
  r=$(goi tinhnguyen01 POST /workflow/ai/boc-tach "$(python3 -c 'import json,sys; print(json.dumps({"van_ban": sys.argv[1], "nguon": "zalo", "vao_hang_cho": True}))' "$van_ban")")
  echo "  HTTP $(ma "$r")"
  than "$r" | jf '"  đề xuất: lat=%s lon=%s người=%s mức=%s SĐT=%s · Poka-yoke hợp lệ=%s · hàng chờ %s" % (d["de_xuat"].get("lat"), d["de_xuat"].get("lon"), d["de_xuat"].get("people_count"), d["de_xuat"].get("urgency"), d["de_xuat"].get("reporter_phone"), d["poka_yoke"]["hop_le"], d["hang_cho"]["id"])'
  luu hang_cho "$(than "$r" | jf 'd["hang_cho"]["id"]')"
  noi "AI chỉ đề xuất. Tin chưa tồn tại cho tới khi điều phối viên duyệt ở trang Duyệt tin AI."
  if [ "${1:-}" = --duyet ]; then
    r=$(goi dieuphoi01 POST "/workflow/hang-cho/$(doc hang_cho)/duyet" '{}')
    echo "  duyệt → HTTP $(ma "$r"), tin $(than "$r" | jf 'd.get("incident_id")'), phân công $(than "$r" | jf 'd.get("phan_cong")')"
    [ "$(ma "$r")" = 201 ] && luu tin "$(than "$r" | jf 'd["incident_id"]')"
    noi "Duyệt xong mới có tin thật; vết duyệt ghi AI đề xuất gì, ai duyệt, lúc nào."
  fi
}

b2_ban_do() {
  xanh "2. Tin kêu cứu mới qua API → bản đồ cập nhật ngay"
  local so
  so=$(sdt)
  r=$(goi tinhnguyen01 POST /workflow/keu-cuu "{\"lat\": 15.8442, \"lon\": 108.1171, \"urgency\": \"khan_cap\", \"people_count\": 2, \"reporter_phone\": \"$so\", \"description\": \"Hai vợ chồng già mắc kẹt trên mái nhà (giả định)\", \"address_text\": \"Bến đò thôn 2, xã An Lạc (giả định)\", \"source\": \"app\"}")
  echo "  HTTP $(ma "$r") · tin $(than "$r" | jf 'd.get("id", d)')"
  [ "$(ma "$r")" = 201 ] && luu tin "$(than "$r" | jf 'd["id"]')"
  noi "Không ai bấm tải lại: bản đồ nhận tin qua GraphQL subscription; tin khẩn cấp đỏ, nhấp nháy."
  r=$(goi tinhnguyen01 POST /workflow/keu-cuu "{\"lat\": 15.8443, \"lon\": 108.1172, \"urgency\": \"khan_cap\", \"people_count\": 2, \"reporter_phone\": \"$so\", \"description\": \"Báo lại lần nữa\", \"source\": \"app\"}")
  echo "  gửi trùng SĐT trong 200 m → HTTP $(ma "$r") ($(than "$r" | jf 'd["detail"]["ma"] if isinstance(d.get("detail"), dict) else d.get("detail")'))"
  noi "Poka-yoke: cùng SĐT trong 200 m và 6 giờ bị CSDL chặn, không có cứu trợ trùng."
}

b3_phan_cong() {
  local tin=${TIN_ID:-$(doc tin)}
  [ -n "$tin" ] && [ "$tin" != None ] || { echo "Chưa có tin: chạy bước 2 trước"; return 1; }
  xanh "3. Phân công tự động: workflow Temporal phan-cong-$tin"
  for _ in $(seq 1 15); do
    r=$(goi dieuphoi01 GET "/workflow/phan-cong-$tin")
    [ "$(than "$r" | jf '(d.get("chi_tiet") or {}).get("buoc")')" = cho_nhan ] && break
    sleep 2
  done
  than "$r" | jf '(lambda c: "  bước %s · đội %s · cách %s m · hạn nhận %s giây · lần tìm %s" % (c.get("buoc"), c.get("doi_ten"), c.get("khoang_cach_m"), c.get("han_nhan_giay"), c.get("so_lan_tim")))(d.get("chi_tiet") or {})'
  noi "Không ai chọn đội bằng tay: PostGIS tìm đội sẵn sàng gần nhất, hạn nhận theo mức khẩn, quá hạn giao đội kế tiếp."
  if [ "${1:-}" = --nhan ]; then
    r=$(goi dieuphoi01 POST "/workflow/phan-cong-$tin/nhan" '{"ghi_chu": "Demo: nhận thay đội"}')
    echo "  nhận nhiệm vụ → HTTP $(ma "$r")"
  fi
}

b4_offline() {
  xanh "4. App hiện trường: gửi lại từ hàng đợi offline với Idempotency-Key"
  local k body r1 r2 so
  k="demo130-$(python3 -c 'import uuid; print(uuid.uuid4())')"
  so=$(sdt)
  body="{\"lat\": 15.8601, \"lon\": 108.0942, \"urgency\": \"cao\", \"people_count\": 4, \"reporter_phone\": \"$so\", \"description\": \"Gửi từ app lúc mất sóng, có mạng lại thì tự gửi (giả định)\", \"address_text\": \"Thôn 4, xã An Lạc (giả định)\", \"source\": \"app\"}"
  r1=$(goi tinhnguyen01 POST /workflow/keu-cuu "$body" "$k")
  r2=$(goi tinhnguyen01 POST /workflow/keu-cuu "$body" "$k")
  echo "  lần 1 → HTTP $(ma "$r1"), tin $(than "$r1" | jf 'd.get("id")')"
  echo "  lần 2 (mạng chập chờn, app gửi lại) → HTTP $(ma "$r2"), Idempotent-Replayed=$( [ "$(r=${r2#* }; printf '%s' "${r%% *}")" = 1 ] && echo true || echo false), tin $(than "$r2" | jf 'd.get("id")')"
  echo "  số tin của SĐT này trong CSDL: $(sql <<<"SELECT count(*) FROM cuu_tro.incidents WHERE reporter_phone = '$so'")"
  noi "App lưu mọi thao tác vào hàng đợi mã hóa trên máy; gửi lại bao nhiêu lần cũng chỉ một tin."
}

b5_canh_bao() {
  xanh "5. Trạm đo vượt ngưỡng (giả lập MQTT) → Temporal → thông báo"
  make -s gia-lap-vuot-nguong 2>/dev/null | tail -n 2
  sleep 6
  sql <<<"SELECT '  ' || sensor_code || ' · ' || step || ' · ' || value || ' ' || unit || ' (ngưỡng ' || coalesce(threshold::text, '-') || ') · kênh ' || channel || ' · ' || status FROM cuu_tro.sensor_alert_notifications ORDER BY created_at DESC LIMIT 3"
  noi "Mỗi đợt vượt ngưỡng là một workflow: báo đúng một lần khi vượt, khi lên nguy hiểm, khi về dưới ngưỡng. Web nhận qua Centrifugo; đặt token thì gửi Telegram."
}

b6_minh_bach() {
  xanh "6. Phiếu xuất kho → sổ cái Tessera → ai cũng tự kiểm"
  r=$(goi dieuphoi01 POST /workflow/kho/phieu '{"supply_id": "d0000000-0000-4000-8000-000000000001", "direction": "xuat", "quantity": 50, "note": "Xuất gạo cho điểm tránh lũ (giả định)", "shelter_id": "c0000000-0000-4000-8000-000000000001"}')
  local m
  m=$(than "$r" | jf 'd["ban_ghi_chuan_hoa"]["id"]')
  luu phieu "$m"
  echo "  HTTP $(ma "$r") · phiếu $m · lá sổ cái #$(than "$r" | jf 'd["so_cai"].get("index")') · sha256 $(than "$r" | jf 'd["sha256"][:16]')…"
  echo "  trang công khai (không đăng nhập): $GW/minh-bach/$m"
  curl -s -m 20 "$GW/workflow/minh-bach/phieu/$m" -o "$TRANG_THAI/phieu.json"
  local vk idx
  vk=$(curl -s -m 10 "$GW/ledger/verifier")
  idx=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["so_cai"]["index"])' "$TRANG_THAI/phieu.json")
  echo "  ledger-verify (chỉ dùng dữ liệu công khai):"
  docker run --rm -i --network "${COMPOSE_PROJECT_NAME:-disaster-dxos}_default" --entrypoint /ledger-verify disaster-dxos/ledger:0.1.0 \
    -log http://apisix:9080/ledger/ -verifier "$vk" -index "$idx" -record - <"$TRANG_THAI/phieu.json" | sed 's/^/    /'
  noi "Không cần tin máy chủ: trình duyệt hoặc CLI tự dựng proof từ checkpoint đã ký."
}

b7_grafana() {
  xanh "7. Dashboard điều hành Grafana (SSO Keycloak, vai theo realm)"
  echo "  $GW/grafana/ → $(curl -s -m 10 -o /dev/null -w '%{http_code} %{redirect_url}' "$GW/grafana/login" | cut -d'?' -f1)"
  noi "Đăng nhập cùng tài khoản Keycloak: điều phối là Editor, cứu hộ là Viewer, tình nguyện viên không vào được. Dữ liệu đọc bằng role chỉ đọc, không thấy SĐT."
}

case "${1:-}" in
  chuan-bi) chuan_bi ;;
  1|ai) b1_ai "${2:-}" ;;
  2|ban-do) b2_ban_do ;;
  3|phan-cong) b3_phan_cong "${2:-}" ;;
  4|offline) b4_offline ;;
  5|canh-bao) b5_canh_bao ;;
  6|minh-bach) b6_minh_bach ;;
  7|grafana) b7_grafana ;;
  tat-ca) chuan_bi; b1_ai --duyet; b2_ban_do; b3_phan_cong --nhan; b4_offline; b5_canh_bao; b6_minh_bach; b7_grafana ;;
  *) sed -n '3,17p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
