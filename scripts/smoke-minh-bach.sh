#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử trang Minh bạch cứu trợ công khai của web (#63), gọi THẬT qua APISIX như trình duyệt KHÔNG đăng nhập:
# (1) trang /minh-bach và /minh-bach/<mã> trả HTML; preflight/GET CORS từ origin của web tới các API trang dùng
#     (xác minh, sổ cái, quỹ, khóa công khai sổ cái) không cần token;
# (2) một phiếu xuất kho và một bút toán thu (seed, worker đã niêm phong) → /minh-bach/xac-minh trả hợp lệ kèm
#     bằng chứng (lá, leaf hash, inclusion proof, checkpoint đã ký); phản hồi không có người lập, SĐT;
# (3) CHẠY CHÍNH MÃ TỰ KIỂM CỦA WEB (apps/cuu-tro/web/utils/tu-kiem.ts, Node bỏ kiểu TypeScript) trên bằng chứng
#     thật của sổ cái Tessera + khóa /ledger/verifier: đủ 5 bước đạt cho cả hai mã; bản ghi bị sửa (số tiền)
#     hoặc proof bị sửa → trình duyệt phát hiện sai lệch;
# (4) sổ cái gần đây + quỹ: mã vừa kiểm có trong danh sách, số dư = thu − chi.
# Chỉ đọc: không tạo dữ liệu mới. Cần node ≥ 22.6 trên máy chạy smoke.
# Dùng: make up && make seed && bash scripts/smoke-minh-bach.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

GW="http://localhost:${APISIX_PORT:-9080}"
ORIGIN="${GW_CORS_ALLOW_ORIGINS:-http://localhost:3000}"; ORIGIN="${ORIGIN%%,*}"
PHIEU=e0000000-0000-4000-8000-000000000002   # xuất 300 đơn vị tới Trường THCS (seed)
KHOAN=e1000000-0000-4000-8000-000000000001   # thu 50.000.000 đ ủng hộ (seed)
TU_KIEM=apps/cuu-tro/web/utils/tu-kiem.ts
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail=0

check() { # check <tên> <mong đợi> <thực tế>
  if [ "$2" = "$3" ]; then echo "PASS  $1 → $3"; else echo "FAIL  $1 → $3 (mong đợi $2)"; fail=1; fi
}
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
jf() { python3 -c 'import sys,json; d=json.load(open(sys.argv[2])); print(eval(sys.argv[1], {"d": d}))' "$1" "$2"; }
sql() { docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -q -v ON_ERROR_STOP=1'; }
cho_niem_phong() { # cho_niem_phong <bảng> <id>: chờ worker niêm phong (tối đa 40 giây)
  local _
  for _ in $(seq 1 40); do
    [ -n "$(sql <<<"SELECT ledger_index FROM cuu_tro.$1 WHERE id = '$2';")" ] && { echo True; return; }
    sleep 1
  done
  echo False
}
# Node < 23 cần cờ để chạy thẳng tệp .ts (bỏ kiểu)
NODE_TS=()
node -e 'process.exit(+process.versions.node.split(".")[0] >= 23 ? 0 : 1)' || NODE_TS=(--experimental-strip-types)
# tu_kiem <tệp phản hồi xác-minh> <tệp khóa> [sua-so-tien|sua-proof]: chạy tuKiem của web, in "ok,ok,…|kết luận"
tu_kiem() {
  # shellcheck disable=SC2016 # mã JavaScript, ${…} là template literal của JS
  node "${NODE_TS[@]}" --no-warnings --input-type=module -e '
const [, , phanHoi, khoa, sua, tep] = process.argv
const fs = await import("node:fs")
const { tuKiem, ketLuan } = await import(new URL(tep, `file://${process.cwd()}/`).href)
const kq = JSON.parse(fs.readFileSync(phanHoi, "utf8"))
const d = { loai: kq.loai, ma: kq.ma, ban_ghi_chuan_hoa: { ...kq.ban_ghi_chuan_hoa }, bang_chung: kq.bang_chung && { ...kq.bang_chung, inclusion_proof: [...kq.bang_chung.inclusion_proof] }, la: kq.so_cai.la }
if (sua === "sua-so-tien") d.ban_ghi_chuan_hoa.amount = String(Number(d.ban_ghi_chuan_hoa.amount) + 1)
if (sua === "sua-proof") d.bang_chung.inclusion_proof[0] = "00".repeat(32)
const b = await tuKiem(d, fs.readFileSync(khoa, "utf8").trim())
console.log(b.map((x) => x.ok).join(",") + "|" + ketLuan(b))' x "$1" "$2" "${3:-}" "$TU_KIEM"
}

# ---------------- (1) Trang và CORS ----------------
check "GET /minh-bach (không đăng nhập) qua gateway → HTML" "200 text/html" \
  "$(curl -s -o /dev/null -w '%{http_code} %{content_type}' "$GW/minh-bach" | cut -d';' -f1)"
check "GET /minh-bach/<mã bút toán> → HTML" 200 "$(code "$GW/minh-bach/$KHOAN")"
for p in "/workflow/minh-bach/xac-minh/$KHOAN" /workflow/minh-bach/so-cai /workflow/minh-bach/quy /ledger/verifier; do
  check "CORS từ origin web, không token: GET $p" "200 $ORIGIN" \
    "$(curl -s -o /dev/null -D "$TMP/h" -w '%{http_code}' -H "Origin: $ORIGIN" "$GW$p"; printf ' %s' "$(tr -d '\r' <"$TMP/h" | sed -n 's/^[Aa]ccess-[Cc]ontrol-[Aa]llow-[Oo]rigin: //p')")"
done

# ---------------- (2) Xác minh công khai ----------------
check "phiếu xuất kho seed đã được worker niêm phong" True "$(cho_niem_phong supply_movements "$PHIEU")"
check "bút toán thu seed đã được worker niêm phong" True "$(cho_niem_phong relief_fund_entries "$KHOAN")"
curl -s "$GW/ledger/verifier" >"$TMP/khoa"
check "khóa công khai sổ cái dạng note Ed25519" True "$(python3 -c 'import sys; p=open(sys.argv[1]).read().strip().split("+",2); print(len(p)==3 and len(p[1])==8)' "$TMP/khoa")"
for m in "phieu_kho:$PHIEU" "khoan_tien:$KHOAN"; do
  loai=${m%%:*}; ma=${m#*:}
  c=$(curl -s -o "$TMP/$loai.json" -w '%{http_code}' "$GW/workflow/minh-bach/xac-minh/$ma")
  check "xác minh $loai (không token) → 200, hợp lệ, có bằng chứng" "200 True $loai True" \
    "$c $(jf '"%s %s %s" % (d["hop_le"], d["loai"], bool(d["bang_chung"] and d["bang_chung"]["inclusion_proof"] is not None and d["bang_chung"]["checkpoint"] and d["so_cai"]["la"]))' "$TMP/$loai.json")"
  check "phản hồi $loai không có người lập hay SĐT" True \
    "$(python3 -c 'import sys,re; s=open(sys.argv[1]).read(); print(not any(k in s for k in ("created_by","reporter_phone","responded_by")) and not re.search(r"(^|[^0-9a-f])0[0-9]{9,10}([^0-9a-f]|$)", s))' "$TMP/$loai.json")"
done

# ---------------- (3) Mã tự kiểm của web trên bằng chứng thật ----------------
for loai in phieu_kho khoan_tien; do
  check "tu-kiem.ts của web: $loai đủ 5 bước đạt (băm, lá, leaf hash, inclusion, chữ ký Ed25519)" "true,true,true,true,true|hop_le" \
    "$(tu_kiem "$TMP/$loai.json" "$TMP/khoa" 2>&1 | tail -1)"
done
check "tu-kiem.ts: bản ghi bị sửa số tiền → phát hiện ở bước băm" "false,true,true,true,true|khong_hop_le" \
  "$(tu_kiem "$TMP/khoan_tien.json" "$TMP/khoa" sua-so-tien 2>&1 | tail -1)"
check "tu-kiem.ts: proof bị sửa → phát hiện ở bước inclusion" "true,true,true,false,true|khong_hop_le" \
  "$(tu_kiem "$TMP/phieu_kho.json" "$TMP/khoa" sua-proof 2>&1 | tail -1)"

# ---------------- (4) Sổ cái gần đây, quỹ ----------------
curl -s "$GW/workflow/minh-bach/so-cai?gioi_han=100" >"$TMP/so-cai.json"
check "sổ cái công khai có cả hai mã vừa kiểm, không có người lập" "True True" \
  "$(jf '"%s %s" % ({m["ma"] for m in d["muc"]} >= {"'"$PHIEU"'", "'"$KHOAN"'"} or len(d["muc"]) == 100, all("created_by" not in m for m in d["muc"]))' "$TMP/so-cai.json")"
curl -s "$GW/workflow/minh-bach/quy" >"$TMP/quy.json"
check "quỹ: số dư = tổng thu − tổng chi, khớp CSDL" "True $(sql <<<"SELECT coalesce(sum(CASE direction WHEN 'thu' THEN amount ELSE -amount END),0)::bigint FROM cuu_tro.relief_fund_entries;")" \
  "$(jf '"%s %s" % (int(d["so_du"]) == int(d["tong_thu"]) - int(d["tong_chi"]), d["so_du"])' "$TMP/quy.json")"

if [ "$fail" -ne 0 ]; then echo "smoke-minh-bach: CÓ LỖI"; exit 1; fi
echo "smoke-minh-bach: tất cả đều đạt"
