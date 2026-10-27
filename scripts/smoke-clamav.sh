#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử quét mã độc ảnh hiện trường (#111) với ClamAV THẬT (profile sec), gọi qua APISIX như client:
# (1) cấu hình: clamav ở profile sec, image ghim phiên bản, không mở cổng ra host; tự bật profile sec, chờ clamd
#     nạp xong bộ chữ ký; cuu-tro-api tới được clamav:3310 trong mạng nội bộ (VERSION);
# (2) tệp thử EICAR (chuẩn ngành, vô hại) → 422 anh_nhiem_ma_doc kèm tên chữ ký: 422 chứ không 415 nghĩa là quét
#     chạy trước bước kiểm magic bytes; không có dòng incident_media nào. (Theo chuẩn EICAR, chuỗi thử chỉ có hiệu
#     lực ở đầu tệp: ClamAV không báo EICAR nằm sau phần đầu JPEG, nên không dùng EICAR để thử tệp "đội lốt ảnh");
# (3) ảnh sạch → 201 scan_status sach, scan_engine "ClamAV <phiên bản>/<bộ chữ ký>", scanned_at trong CSDL;
# (4) log cuu-tro-api có tên chữ ký nhưng không có nội dung tệp, không có SĐT;
# (5) tắt clamav → ảnh vẫn nhận với chua_quet (mặc định, ANH_QUET_BAT_BUOC=0), log cảnh báo; cuối cùng dừng
#     clamav để các smoke sau chạy như khi không bật profile sec.
# SĐT giả 0900111xxx; tin thử bị xóa khi kết thúc. Dùng: make up && make seed && bash scripts/smoke-clamav.sh
# shellcheck disable=SC2016 # biến của psql trong container và chuỗi thử EICAR cố ý nằm trong nháy đơn
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

KC="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-disaster}"
GW="http://localhost:${APISIX_PORT:-9080}"
fail=0
check() { if [ "$2" = "$3" ]; then echo "PASS  $1 → $3"; else echo "FAIL  $1 → $3 (mong đợi $2)"; fail=1; fi; }
token() {
  curl -s -m 20 -X POST "$KC/realms/$REALM/protocol/openid-connect/token" -d grant_type=password -d client_id=dxos-dev-cli \
    -d scope=openid -d username="$1" --data-urlencode password="${KC_DEMO_USER_PASSWORD:?}" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])'
}
# tai <tệp> → "<mã HTTP> <body>"
tai() {
  local out code
  out=$(mktemp)
  code=$(curl -s -m 90 -o "$out" -w '%{http_code}' -K <(printf 'header = "Authorization: Bearer %s"\n' "$D") \
    -X POST -H 'Content-Type: image/jpeg' --data-binary @"$1" "$GW/workflow/tai-len/su-co/$INC/anh")
  printf '%s %s\n' "$code" "$(cat "$out")"
  rm -f "$out"
}
ma() { printf '%s' "${1%% *}"; }
jf() { python3 -c 'import sys,json; d=json.loads(sys.stdin.read().split(" ", 1)[1]); print(eval(sys.argv[1], {"d": d}))' "$1"; }
sql() { timeout 60 docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -q -v ON_ERROR_STOP=1'; }
temporal_cli() { timeout 30 docker compose exec -T temporal sh -c "temporal $* --address temporal:7233"; }
dem_anh() { sql <<<"SELECT count(*) FROM cuu_tro.incident_media WHERE incident_id = '$INC'"; }

TMP=$(mktemp -d)
INC=""
don_dep() {
  if [ -n "$INC" ]; then
    temporal_cli workflow terminate -w "phan-cong-$INC" --reason smoke-reset >/dev/null 2>&1 || true
    sql >/dev/null <<<"DELETE FROM cuu_tro.incident_media WHERE incident_id = '$INC'; DELETE FROM cuu_tro.incidents WHERE id = '$INC';" || true
  fi
  sql >/dev/null <<<"DELETE FROM cuu_tro.incidents WHERE reporter_phone LIKE '0900111%' AND NOT EXISTS (SELECT 1 FROM cuu_tro.incident_media m WHERE m.incident_id = incidents.id);" || true
  timeout 120 docker compose --profile sec stop clamav >/dev/null 2>&1 || true
  rm -rf "$TMP"
}
trap don_dep EXIT

# ---------- (1) Cấu hình, bật profile sec ----------
cfg=$(docker compose --profile sec config --format json)
check "clamav ở profile sec, image ghim phiên bản, không mở cổng ra host" "['sec'] True True" \
  "$(python3 -c 'import sys,json; s=json.load(sys.stdin)["services"]["clamav"]; i=s["image"]; print(s.get("profiles"), i.startswith("clamav/clamav:1.") and "latest" not in i, not s.get("ports"))' <<<"$cfg")"
timeout 900 docker compose --profile core --profile app --profile sec up -d clamav >/dev/null 2>&1
ok=""
for _ in $(seq 1 120); do
  st=$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose --profile sec ps -q clamav)" 2>/dev/null || true)
  [ "$st" = healthy ] && { ok=1; break; }
  sleep 5
done
check "clamd nạp xong bộ chữ ký (healthy)" 1 "${ok:-0}"
check "cổng clamd 3310 không mở ra host" dong \
  "$(python3 -c 'import socket; s=socket.socket(); s.settimeout(2); print("mo" if s.connect_ex(("127.0.0.1", 3310)) == 0 else "dong")')"
PHIEN_BAN=$(timeout 60 docker compose exec -T cuu-tro-api python -c '
import asyncio
from cuu_tro_workflow.quet_ma_doc import MayQuet, rut_gon_phien_ban
print(rut_gon_phien_ban(asyncio.run(MayQuet("clamav", 3310, 20).phien_ban())))' 2>&1 | tail -n 1)
check "cuu-tro-api tới clamav:3310 trong mạng nội bộ (VERSION)" True \
  "$(case "$PHIEN_BAN" in "ClamAV 1."*/*) echo True ;; *) echo "$PHIEN_BAN" ;; esac)"

# ---------- Tin thử để gắn ảnh ----------
D=$(token dieuphoi01)
out=$(curl -s -m 30 -K <(printf 'header = "Authorization: Bearer %s"\n' "$D") -X POST -H 'Content-Type: application/json' \
  -d '{"lat": 21.2101, "lon": 105.9501, "reporter_phone": "0900111001", "description": "[smoke #111] ảnh hiện trường"}' \
  "$GW/workflow/keu-cuu")
INC=$(python3 -c 'import sys,json; print(json.loads(sys.argv[1])["id"])' "$out")
OBJ_TRUOC=$(sql <<<"SELECT count(*) FROM cuu_tro.incident_media")

# ---------- (2) Tệp nhiễm ----------
# Chuỗi thử EICAR ghép từ hai nửa để chính tệp script không bị phần mềm diệt virus trên máy dev chặn
printf '%s%s' 'X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-' 'ANTIVIRUS-TEST-FILE!$H+H*' >"$TMP/eicar.com"
out=$(tai "$TMP/eicar.com")
check "tệp thử EICAR → 422 anh_nhiem_ma_doc (không phải 415: quét trước kiểm magic bytes), có tên chữ ký" \
  "422 anh_nhiem_ma_doc True" \
  "$(ma "$out") $(jf 'd["detail"]["ma"]' <<<"$out") $(jf '"eicar" in d["detail"]["chu_ky"].lower()' <<<"$out")"
check "tệp nhiễm không có dòng incident_media nào" "0 $OBJ_TRUOC" "$(dem_anh) $(sql <<<"SELECT count(*) FROM cuu_tro.incident_media")"

# ---------- (3) Ảnh sạch ----------
python3 -c 'import sys; sys.stdout.buffer.write(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + bytes(range(256)) * 4 + b"\xff\xd9")' >"$TMP/sach.jpg"
out=$(tai "$TMP/sach.jpg")
check "ảnh sạch → 201 sach, scan_engine = phiên bản ClamAV/bộ chữ ký" "201 sach True" \
  "$(ma "$out") $(jf 'd["scan_status"]' <<<"$out") $(jf 'd["scan_engine"] == "'"$PHIEN_BAN"'"' <<<"$out")"
check "CSDL: scan_status sach, có scanned_at, scan_engine" "sach|true|$PHIEN_BAN" \
  "$(sql <<<"SELECT scan_status || '|' || (scanned_at IS NOT NULL)::text || '|' || scan_engine FROM cuu_tro.incident_media WHERE incident_id = '$INC'")"

# ---------- (4) Log ----------
LOG=$(docker compose logs --no-log-prefix cuu-tro-api 2>&1)
check "log cuu-tro-api ghi tên chữ ký, không ghi nội dung tệp hay SĐT" "True 0" \
  "$(grep -qi 'mã độc (.*eicar' <<<"$LOG" && echo True || echo False) $(grep -c 'STANDARD-ANTIVIRUS\|0900111' <<<"$LOG" || true)"

# ---------- (5) Máy quét tắt: mặc định vẫn nhận ảnh ----------
timeout 120 docker compose --profile sec stop clamav >/dev/null 2>&1
out=$(tai "$TMP/sach.jpg")
check "clamav tắt → ảnh vẫn nhận với chua_quet (ANH_QUET_BAT_BUOC=0)" "201 chua_quet None" \
  "$(ma "$out") $(jf 'd["scan_status"]' <<<"$out") $(jf 'd["scanned_at"]' <<<"$out")"
check "log cảnh báo không quét được" True \
  "$(docker compose logs --no-log-prefix --since 2m cuu-tro-api 2>&1 | grep -q 'không quét được ảnh, nhận với scan_status chua_quet' && echo True || echo False)"

if [ "$fail" -eq 0 ]; then echo "OK: smoke quét mã độc ClamAV đạt"; else echo "CÓ LỖI: xem các dòng FAIL"; exit 1; fi
