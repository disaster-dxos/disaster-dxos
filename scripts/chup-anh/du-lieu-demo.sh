#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Dữ liệu GIẢ cho ảnh chụp và GIF demo README (#65), chạy trên stack đã `make up && make seed`:
# (1) 8 tin kêu cứu quanh Đại Lộc, Điện Bàn (Quảng Nam) qua POST /workflow/keu-cuu như người dân báo tin:
#     mô tả, địa chỉ đều bịa, SĐT dạng 0900065xxx không phải số thật; workflow tự phân công đội gần nhất;
# (2) trận lũ mẫu (#84, giả lập) của 9 trạm từ giờ 0 tới đỉnh (giờ DINH), mỗi bước cách nhau 1 giờ và bước
#     cuối là bây giờ: bản đồ có đủ màu trạm, popup có biểu đồ 24 giờ nước lên.
# Chạy lại được: tin trùng SĐT trong bán kính 200 m bị Poka-yoke chặn (409), bỏ qua.
# Dùng: bash scripts/chup-anh/du-lieu-demo.sh   (từ gốc repo)
set -euo pipefail
cd "$(dirname "$0")/../.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

KC="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-disaster}"
GW="http://localhost:${APISIX_PORT:-9080}"
DINH="${DINH:-30}"

TOK=$(curl -s -X POST "$KC/realms/$REALM/protocol/openid-connect/token" \
  -d grant_type=password -d client_id=dxos-dev-cli -d scope=openid \
  -d username=tinhnguyen01 --data-urlencode password="${KC_DEMO_USER_PASSWORD:?}" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

# vĩ độ|kinh độ|mức khẩn|số người|SĐT giả|mô tả|địa chỉ (đều là dữ liệu giả)
while IFS='|' read -r lat lon muc nguoi sdt mo_ta dia_chi; do
  body=$(python3 -c 'import json,sys; a=sys.argv[1:]; print(json.dumps({"lat": float(a[0]), "lon": float(a[1]), "urgency": a[2], "people_count": int(a[3]), "reporter_phone": a[4], "description": a[5], "address_text": a[6]}, ensure_ascii=False))' \
    "$lat" "$lon" "$muc" "$nguoi" "$sdt" "$mo_ta" "$dia_chi")
  code=$(curl -s -o /dev/null -w '%{http_code}' -K <(printf 'header = "Authorization: Bearer %s"\n' "$TOK") \
    -H 'Content-Type: application/json' -d "$body" "$GW/workflow/keu-cuu")
  echo "tin $sdt → $code"
done <<'TIN'
15.8512|108.1093|khan_cap|4|0900065001|Nước ngập tới mái, có người già và trẻ nhỏ trên gác|Thôn 1, xã An Lạc (giả định)
15.8468|108.1178|cao|3|0900065002|Nhà bị cô lập, cần thuyền đưa ra điểm tránh lũ|Bến đò thôn 2 (giả định)
15.8571|108.1022|trung_binh|2|0900065003|Hết nước uống và mì tôm từ tối qua|Xóm Đồng, thôn 3 (giả định)
15.8795|108.1201|khan_cap|5|0900065004|Có người bị thương ở chân, nước đang lên nhanh|Ái Nghĩa, Đại Lộc (giả định)
15.8402|108.1305|cao|2|0900065005|Mất điện, điện thoại sắp hết pin, xin hỗ trợ di dời|Giao Thủy, Đại Lộc (giả định)
15.8661|108.2605|trung_binh|6|0900065006|Gia đình 6 người cần áo phao và đèn pin|Thôn Câu Lâu, Duy Xuyên (giả định)
15.8890|108.2310|thap|1|0900065007|Cần thuốc huyết áp cho người già|Điện Bàn (giả định)
15.8529|108.0951|cao|3|0900065008|Đường vào xóm bị sạt, xe không vào được|Thôn 4, xã An Lạc (giả định)
TIN

# Trận lũ mẫu từ giờ 0 tới đỉnh, kết thúc ở bây giờ (cùng hàm của bộ giả lập, gửi qua MQTT có xác thực)
docker compose --profile core --profile app run --rm --no-deps -T cuu-tro-gia-lap python - "$DINH" <<'PY' 2>/dev/null | tail -1
import os, sys
from datetime import datetime, timezone
from cuu_tro_workflow import gia_lap as g

dinh = int(sys.argv[1])
rng = g.random.Random(0)
c = g.ket_noi(os.environ["MQTT_HOST"], int(os.environ["MQTT_PORT"]), os.environ.get("MQTT_USERNAME"), os.environ.get("MQTT_PASSWORD"))
n = 0
for t in g.TRAM_MAU:
    buoc = range(0, min(dinh, len(t.chuoi) - 1) + 1)
    for b, td in zip(buoc, g.thoi_diem_phat_lai(datetime.now(timezone.utc), len(buoc), 1.0)):
        topic, payload = g.ban_tin(t, g.gia_tri_kich_ban(t, "tran-lu", b, 6, rng), td)
        c.publish(topic, payload, qos=1).wait_for_publish(10)
        n += 1
c.disconnect(); c.loop_stop()
print(f"trận lũ mẫu: đã gửi {n} bản tin (giờ 0 → {dinh})")
PY
