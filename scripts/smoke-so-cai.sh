#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử sổ cái minh bạch mở rộng (#89), gọi THẬT qua APISIX:
# (1) bút toán tiền mẫu (seed) được worker tự niêm phong; tổng hợp quỹ công khai khớp CSDL;
# (2) luồng đầu cuối: nhập kho → xuất tới điểm nhận (phân phát) → thu tiền ủng hộ → chi tiền mua hàng
#     (gắn phiếu nhập) → xác minh công khai từng mã (không đăng nhập) qua /workflow/minh-bach/xac-minh;
#     không lộ người lập; danh sách đã niêm phong + tổng hợp quỹ;
# (3) CLI ledger-verify độc lập (chỉ dùng checkpoint + tile công khai) xác minh bút toán tiền; bản ghi giả
#     mạo phía client (sửa số tiền) → KHÔNG KHỚP;
# (4) sửa tay số tiền trong CSDL (tắt trigger bất biến bằng superuser) → xác minh báo không hợp lệ, CLI
#     không khớp; khôi phục → lại hợp lệ;
# (5) sổ cái dừng: bút toán vẫn lập được (202, chờ niêm phong, outbox); sổ cái chạy lại → worker tự
#     niêm phong bù, xác minh hợp lệ;
# (6) quyền và dữ liệu vào: cuu-ho/không token không lập được, chi vượt số dư 409, nội dung có số dạng
#     SĐT 422; dieu-phoi đọc bút toán qua /graphql, không thấy người lập; cuu-ho không thấy bảng.
# Bút toán bất biến nên các bút toán thử ở lại trong CSDL và sổ cái; thu = chi để số dư quỹ không đổi.
# Dùng: make up && make seed && bash scripts/smoke-so-cai.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

KC="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-disaster}"
GW="http://localhost:${APISIX_PORT:-9080}"
NET="${COMPOSE_PROJECT_NAME:-disaster-dxos}_default"
LEDGER_IMAGE=disaster-dxos/ledger:0.1.0
HANG=d0000000-0000-4000-8000-000000000004      # Mì tôm (seed)
DIEM=c0000000-0000-4000-8000-000000000001      # Trường THCS An Lạc (seed)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
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
req() { # req <token|-> <tham số curl...>: in "<mã HTTP> <body>"; token đi qua file cấu hình curl
  local tok=$1 out code; shift
  out=$(mktemp)
  if [ "$tok" = - ]; then code=$(curl -s -o "$out" -w '%{http_code}' "$@")
  else code=$(curl -s -o "$out" -w '%{http_code}' -K <(printf 'header = "Authorization: Bearer %s"\n' "$tok") "$@"); fi
  printf '%s %s\n' "$code" "$(tr -d '\n' <"$out")"
  rm -f "$out"
}
hc() { printf '%s' "${1%% *}"; }
jf() { python3 -c 'import sys,json; d=json.loads(sys.stdin.read().split(" ", 1)[1]); print(eval(sys.argv[1], {"d": d}))' "$1"; }
sql() { docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -q -v ON_ERROR_STOP=1'; }
post() { req "$1" -X POST -H 'Content-Type: application/json' -d "$3" "$GW/workflow/$2"; }
phieu() { post "$1" kho/phieu "{\"supply_id\":\"$HANG\",\"direction\":\"$2\",\"quantity\":\"$3\",\"note\":\"Phiếu thử smoke #89\"${4:+,\"shelter_id\":\"$4\"}}"; }
khoan() { # khoan <token|-> <thu|chi> <số tiền> <hạng mục> [nội dung] [json thêm]
  post "$1" quy/khoan "{\"direction\":\"$2\",\"amount\":$3,\"category\":\"$4\",\"purpose\":\"${5:-Bút toán thử smoke #89}\"${6:+,$6}}"
}
xac_minh() { req - "$GW/workflow/minh-bach/xac-minh/$1"; }
verify_cli() { # verify_cli <index> <file bản ghi>: CLI kiểm chứng độc lập, chỉ thấy gateway
  docker run --rm -i --network "$NET" --entrypoint /ledger-verify "$LEDGER_IMAGE" \
    -log http://apisix:9080/ledger/ -verifier "$VK" -index "$1" -record - <"$2"
}
tamper() { # tamper <id> <delta>: sửa số tiền bằng superuser, vượt trigger bất biến (mô phỏng sửa trái phép CSDL)
  sql <<SQL >/dev/null
BEGIN;
ALTER TABLE cuu_tro.relief_fund_entries DISABLE TRIGGER relief_fund_entries_immutable;
UPDATE cuu_tro.relief_fund_entries SET amount = amount + ($2) WHERE id = '$1';
ALTER TABLE cuu_tro.relief_fund_entries ENABLE TRIGGER relief_fund_entries_immutable;
COMMIT;
SQL
}
cho_niem_phong() { # cho_niem_phong <bảng> <id> [giây]: chờ worker điền ledger_index, in index hoặc "chua"
  local i r
  for i in $(seq 1 "${3:-40}"); do
    r=$(sql <<<"SELECT ledger_index FROM cuu_tro.$1 WHERE id = '$2';")
    [ -n "$r" ] && { echo "$r"; return; }
    [ "$i" -lt "${3:-40}" ] && sleep 1
  done
  echo chua
}

D=$(get_token dieuphoi01)
C=$(get_token cuuho01)
VK=$(req - "$GW/ledger/verifier" | cut -d' ' -f2-)

# ---------------- (1) Seed + tổng hợp quỹ ----------------
for m in e1000000-0000-4000-8000-000000000001 e1000000-0000-4000-8000-000000000004; do
  check "bút toán seed $m được worker niêm phong (outbox)" True \
    "$([ "$(cho_niem_phong relief_fund_entries "$m" 40)" != chua ] && echo True || echo False)"
done
r=$(req - "$GW/workflow/minh-bach/quy")
check "tổng hợp quỹ công khai (không token) khớp CSDL" \
  "200 $(sql <<<"SELECT coalesce(sum(amount) FILTER (WHERE direction='thu'),0) || ' ' || coalesce(sum(amount) FILTER (WHERE direction='chi'),0) || ' VND' FROM cuu_tro.relief_fund_entries;")" \
  "$(hc "$r") $(jf 'd["tong_thu"] + " " + d["tong_chi"] + " " + d["don_vi"]' <<<"$r")"

# ---------------- (2) Luồng nhập → xuất → thu → chi → xác minh ----------------
r=$(phieu "$D" nhap 100); check "nhập kho 100 → 201, đã ghi sổ" "201 da_ghi" "$(hc "$r") $(jf 'd["so_cai"]["trang_thai"]' <<<"$r")"
P_NHAP=$(jf 'd["ban_ghi_chuan_hoa"]["id"]' <<<"$r")
r=$(phieu "$D" xuat 40 "$DIEM"); check "xuất 40 tới điểm nhận (phân phát) → 201" "201 da_ghi" "$(hc "$r") $(jf 'd["so_cai"]["trang_thai"]' <<<"$r")"
P_XUAT=$(jf 'd["ban_ghi_chuan_hoa"]["id"]' <<<"$r")
r=$(khoan "$D" thu 5000000 ung_ho "Ủng hộ của hội chữ thập đỏ (thử)"); check "thu 5.000.000 đ ủng hộ → 201" "201 da_ghi" "$(hc "$r") $(jf 'd["so_cai"]["trang_thai"]' <<<"$r")"
K_THU=$(jf 'd["ban_ghi_chuan_hoa"]["id"]' <<<"$r"); I_THU=$(jf 'd["so_cai"]["index"]' <<<"$r")
r=$(khoan "$D" chi 5000000 mua_hang "Mua mì tôm (thử)" "\"supply_movement_id\":\"$P_NHAP\"")
check "chi 5.000.000 đ mua hàng, gắn phiếu nhập → 201" "201 da_ghi $P_NHAP" \
  "$(hc "$r") $(jf 'd["so_cai"]["trang_thai"] + " " + d["ban_ghi_chuan_hoa"]["supply_movement_id"]' <<<"$r")"
K_CHI=$(jf 'd["ban_ghi_chuan_hoa"]["id"]' <<<"$r")
for m in "$P_NHAP:phieu_kho" "$P_XUAT:phieu_kho" "$K_THU:khoan_tien" "$K_CHI:khoan_tien"; do
  r=$(xac_minh "${m%%:*}")
  check "xác minh công khai ${m##*:} ${m%%:*} (không đăng nhập) → hợp lệ" "200 True da_xac_minh ${m##*:}" \
    "$(hc "$r") $(jf '"%s %s %s" % (d["hop_le"], d["trang_thai"], d["loai"])' <<<"$r")"
done
r=$(xac_minh "$K_THU")
printf '%s' "${r#* }" >"$TMP/thu.json"
check "phản hồi công khai không lộ người lập (dieuphoi01)" 0 "$(grep -c 'dieuphoi01' "$TMP/thu.json" || true)"
check "phản hồi có đủ bằng chứng tự kiểm (lá, inclusion proof, checkpoint đã ký)" True \
  "$(jf 'all(k in d["bang_chung"] for k in ("leaf_hash", "inclusion_proof", "checkpoint", "tree_size")) and "\n\n— " in d["bang_chung"]["checkpoint"]' <<<"$r")"
check "lá chỉ có mã, chiều, số tiền, đơn vị, thời điểm" "amount,at,currency,direction cuu-tro.khoan-tien $K_THU" \
  "$(jf '(lambda l: ",".join(sorted(l["attrs"])) + " " + l["type"] + " " + l["ref"])(__import__("json").loads(d["so_cai"]["la"]))' <<<"$r")"
r=$(xac_minh "$P_XUAT")
check "phiếu xuất hiển thị mặt hàng, đơn vị, điểm nhận" "Mì tôm thùng Trường THCS An Lạc (giả định)" \
  "$(jf 'd["hien_thi"]["mat_hang"].split(" (")[0] + " " + d["hien_thi"]["don_vi"] + " " + str(d["hien_thi"]["diem_nhan"])' <<<"$r")"
check "xuất nốt 60 (cân lại tồn kho thử) → 201" 201 "$(hc "$(phieu "$D" xuat 60 "$DIEM")")"
r=$(req - "$GW/workflow/minh-bach/so-cai?loai=khoan_tien&gioi_han=5")
check "danh sách bút toán đã niêm phong (công khai): mới nhất trước, có 2 bút toán vừa lập" "200 $K_CHI $K_THU" \
  "$(hc "$r") $(jf '" ".join(x["ma"] for x in d["muc"][:2])' <<<"$r")"
check "danh sách không lộ người lập" 0 "$(grep -c 'dieuphoi01' <<<"$r" || true)"
# Route công khai chỉ nhận GET; POST rơi sang route /workflow/* (bắt buộc JWT) → 401, có JWT thì API không có đường ghi
check "POST vào đường công khai /workflow/minh-bach/* không ghi được" "401 405" \
  "$(hc "$(req - -X POST "$GW/workflow/minh-bach/quy")") $(hc "$(req "$D" -X POST "$GW/workflow/minh-bach/quy")")"

# ---------------- (3) CLI kiểm chứng độc lập ----------------
out=$(verify_cli "$I_THU" "$TMP/thu.json" 2>&1) && code=0 || code=$?
check "ledger-verify độc lập xác minh bút toán tiền → mã 0, ĐÃ XÁC MINH" "0 1" "$code $(grep -c 'ĐÃ XÁC MINH' <<<"$out" || true)"
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); d["ban_ghi_chuan_hoa"]["amount"]="50000000"; json.dump(d, open(sys.argv[2], "w"))' "$TMP/thu.json" "$TMP/gia.json"
verify_cli "$I_THU" "$TMP/gia.json" >"$TMP/cli.txt" 2>&1 && code=0 || code=$?
check "bản ghi giả mạo phía client (sửa số tiền) → ledger-verify mã 1, KHÔNG KHỚP" "1 1" "$code $(grep -c 'KHÔNG KHỚP' "$TMP/cli.txt" || true)"

# ---------------- (4) Sửa tay CSDL → không hợp lệ ----------------
tamper "$K_THU" 45000000
r=$(xac_minh "$K_THU")
check "sửa số tiền trong CSDL → xác minh không hợp lệ" "False khong_khop" "$(jf '"%s %s" % (d["hop_le"], d["trang_thai"])' <<<"$r")"
check "chi tiết nói rõ bản ghi đã bị sửa" True "$(jf 'any("đã bị sửa" in x for x in d["chi_tiet"])' <<<"$r")"
printf '%s' "${r#* }" >"$TMP/sua.json"
verify_cli "$I_THU" "$TMP/sua.json" >"$TMP/cli.txt" 2>&1 && code=0 || code=$?
check "ledger-verify với bản ghi trong CSDL đã sửa → mã 1" 1 "$code"
tamper "$K_THU" -45000000
check "khôi phục → lại hợp lệ" True "$(xac_minh "$K_THU" | jf 'd["hop_le"]')"

# ---------------- (5) Sổ cái dừng → outbox → worker niêm phong bù ----------------
docker compose stop ledger >/dev/null 2>&1
r=$(khoan "$D" thu 1000000 ung_ho "Ủng hộ lúc sổ cái dừng (thử)")
check "sổ cái dừng: bút toán vẫn lập (202, chờ niêm phong)" "202 chua_ghi_so" "$(hc "$r") $(jf 'd["so_cai"]["trang_thai"]' <<<"$r")"
K_CHO=$(jf 'd["ban_ghi_chuan_hoa"]["id"]' <<<"$r")
check "xác minh lúc chờ: chua_ghi_so, chưa hợp lệ" "False chua_ghi_so" "$(xac_minh "$K_CHO" | jf '"%s %s" % (d["hop_le"], d["trang_thai"])')"
check "tổng hợp quỹ đếm bút toán chờ niêm phong" True "$(req - "$GW/workflow/minh-bach/quy" | jf 'd["khoan_tien_cho_niem_phong"] >= 1')"
docker compose start ledger >/dev/null 2>&1
for _ in $(seq 1 30); do [ "$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -q ledger)")" = healthy ] && break; sleep 2; done
check "sổ cái chạy lại → worker tự niêm phong bù (không ai gọi ghi-so)" True \
  "$([ "$(cho_niem_phong relief_fund_entries "$K_CHO" 60)" != chua ] && echo True || echo False)"
check "bút toán niêm phong bù xác minh hợp lệ" True "$(xac_minh "$K_CHO" | jf 'd["hop_le"]')"
check "log worker ghi lần niêm phong bù" True \
  "$(l=$(docker compose logs --since 5m cuu-tro-worker 2>/dev/null); [[ $l == *"đã niêm phong bù khoan_tien $K_CHO"* ]] && echo True || echo False)"
r=$(khoan "$D" chi 1000000 khac "Cân lại bút toán thử (smoke)")
check "chi cân lại khoản thu lúc sổ cái dừng → 201" 201 "$(hc "$r")"

# ---------------- (6) Quyền, dữ liệu vào, GraphQL ----------------
check "cuu-ho lập bút toán → 403" 403 "$(hc "$(khoan "$C" thu 1 ung_ho)")"
check "không token lập bút toán → 401" 401 "$(hc "$(khoan - thu 1 ung_ho)")"
check "chi vượt số dư quỹ → 409" 409 "$(hc "$(khoan "$D" chi 999999999999 mua_hang)")"
check "nội dung có số dạng SĐT/tài khoản → 422 (nội dung công khai)" 422 "$(hc "$(khoan "$D" thu 1 ung_ho 'Chuyển khoản 0905123456')")"
check "thu với hạng mục chi → 422" 422 "$(hc "$(khoan "$D" thu 1 mua_hang)")"
Q='{ relief_fund_entries(order_by: {created_at: desc}, limit: 1) { amount direction ledger_index } }'
gq() { req "$1" -H 'Content-Type: application/json' -d "$(python3 -c 'import sys,json; print(json.dumps({"query": sys.argv[1]}))' "$2")" "$GW/graphql"; }
check "dieu-phoi đọc bút toán qua /graphql (đã niêm phong)" "200 True" \
  "$(r=$(gq "$D" "$Q"); echo "$(hc "$r") $(jf 'd["data"]["relief_fund_entries"][0]["ledger_index"] is not None' <<<"$r")")"
check "GraphQL không lộ người lập bút toán" validation-failed \
  "$(gq "$D" '{ relief_fund_entries(limit: 1) { created_by } }' | jf 'd["errors"][0]["extensions"]["code"] if "errors" in d else "doc-duoc"')"
check "cuu-ho không thấy bảng bút toán" validation-failed \
  "$(gq "$C" "$Q" | jf 'd["errors"][0]["extensions"]["code"] if "errors" in d else "doc-duoc"')"
check "GraphQL không có đường lập bút toán (dieu-phoi)" validation-failed \
  "$(gq "$D" 'mutation { insert_relief_fund_entries_one(object: {direction: "thu", amount: 1, category: "ung_ho"}) { id } }' | jf 'd["errors"][0]["extensions"]["code"] if "errors" in d else "ghi-duoc"')"

if [ "$fail" -ne 0 ]; then echo "smoke-so-cai: CÓ LỖI"; exit 1; fi
echo "smoke-so-cai: tất cả đều đạt"
