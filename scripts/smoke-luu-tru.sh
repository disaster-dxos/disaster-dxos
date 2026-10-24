#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử lưu trữ lịch sử Parquet + DuckDB (#91), chạy THẬT trên CSDL và SeaweedFS của stack:
# (1) xuất mọi dữ liệu tới hết hôm nay (--den ngày mai) ra bucket cuu-tro-lakehouse: tệp Parquet phân vùng
#     theo tháng + _manifest.json; số dòng từng bảng khớp CSDL;
# (2) chạy lại → không ghi lại tệp nào (idempotent), manifest không đổi;
# (3) DuckDB đọc lại: số dòng, tổng số tiền, thời gian phản hồi khớp CSDL; không có cột/giá trị định danh
#     (SĐT người báo trong CSDL không xuất hiện trong bất kỳ tệp nào); tọa độ làm tròn 2 chữ số;
# (4) bucket riêng tư: không chữ ký → không đọc được qua gateway; role chỉ đọc cuu_tro_bi không ghi được.
# Dùng: make up && make seed && bash scripts/smoke-luu-tru.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

GW="http://localhost:${APISIX_PORT:-9080}"
DEN=$(python3 -c 'from datetime import date, timedelta; print(date.today() + timedelta(days=2))')
fail=0

check() { # check <tên> <mong đợi> <thực tế>
  if [ "$2" = "$3" ]; then echo "PASS  $1 → $3"; else echo "FAIL  $1 → $3 (mong đợi $2)"; fail=1; fi
}
sql() { docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -q -v ON_ERROR_STOP=1'; }
luu_tru() { docker compose --profile core --profile app --profile luu-tru run --rm --no-deps -T cuu-tro-luu-tru python -m cuu_tro_workflow.luu_tru "$@" 2>/dev/null; }
tv() { luu_tru truy-van --json "$1" | tail -1; }   # một dòng kết quả, dạng JSON
jf() { python3 -c 'import sys,json; d=json.loads(sys.stdin.read()); print(eval(sys.argv[1], {"d": d}))' "$1"; }
num() { python3 -c 'import sys; print(float(sys.argv[1]))' "$1"; }
den_ts="'$DEN 00:00+07'::timestamptz"

# ---------------- (1) Xuất ----------------
kq1=$(luu_tru xuat --den "$DEN" | tail -1)
# Volume mới: lần 1 ghi mọi tệp; chạy lại smoke trên volume cũ thì lần 1 cũng có thể không phải ghi gì
check "xuất lần 1 chạy xong, có phân vùng" True "$(jf '(len(d["ghi"]) + d["khong_doi"]) > 0' <<<"$kq1")"
for b in "su_co:SELECT count(*) FROM cuu_tro.incidents WHERE status IN ('da_cuu','dong') AND created_at < $den_ts" \
         "so_do:SELECT count(*) FROM cuu_tro.sensor_readings WHERE observed_at < $den_ts" \
         "phan_phoi:SELECT count(*) FROM cuu_tro.supply_movements WHERE direction = 'xuat' AND created_at < $den_ts" \
         "khoan_tien:SELECT count(*) FROM cuu_tro.relief_fund_entries WHERE created_at < $den_ts"; do
  check "số dòng xuất ${b%%:*} khớp CSDL" "$(sql <<<"${b#*:};")" "$(jf "d['so_dong']['${b%%:*}']" <<<"$kq1")"
done

# ---------------- (2) Idempotent ----------------
kq2=$(luu_tru xuat --den "$DEN" | tail -1)
check "xuất lần 2: không ghi lại tệp nào, không xóa, manifest không đổi" "[] [] False" \
  "$(jf '"%s %s %s" % (d["ghi"], d["xoa"], d["manifest_doi"])' <<<"$kq2")"
check "lần 2 đếm đủ tệp không đổi" True \
  "$(python3 -c 'import json,sys; a=json.loads(sys.argv[1]); b=json.loads(sys.argv[2]); print(b["khong_doi"] == len(a["ghi"]) + a["khong_doi"])' "$kq1" "$kq2")"

# ---------------- (3) DuckDB đọc lại ----------------
check "DuckDB: số tin kêu cứu đã xong" "$(sql <<<"SELECT count(*) FROM cuu_tro.incidents WHERE status IN ('da_cuu','dong') AND created_at < $den_ts;")" \
  "$(tv 'SELECT count(*) AS n FROM su_co' | jf 'd["n"]')"
check "DuckDB: tổng tiền thu khớp CSDL" "$(sql <<<"SELECT coalesce(sum(amount),0)::bigint FROM cuu_tro.relief_fund_entries WHERE direction='thu' AND created_at < $den_ts;")" \
  "$(tv "SELECT coalesce(sum(so_tien),0)::BIGINT AS t FROM khoan_tien WHERE chieu = 'thu'" | jf 'd["t"]')"
check "DuckDB: giá trị đo lớn nhất của QN-CL-01 khớp CSDL" "$(num "$(sql <<<"SELECT coalesce(max(r.value),0)::float8 FROM cuu_tro.sensor_readings r JOIN cuu_tro.sensors s ON s.id=r.sensor_id WHERE s.code='QN-CL-01' AND r.observed_at < $den_ts;")")" \
  "$(num "$(tv "SELECT coalesce(max(gia_tri),0)::DOUBLE AS m FROM so_do WHERE ma_tram = 'QN-CL-01'" | jf 'd["m"]')")"
check "DuckDB: số phiếu phân phát theo điểm nhận khớp CSDL" "$(sql <<<"SELECT count(*) FROM cuu_tro.supply_movements WHERE direction='xuat' AND shelter_id IS NOT NULL AND created_at < $den_ts;")" \
  "$(tv 'SELECT count(*) AS n FROM phan_phoi WHERE diem_nhan IS NOT NULL' | jf 'd["n"]')"
check "DuckDB: thời gian phản hồi trung vị (giây) khớp CSDL" \
  "$(num "$(sql <<<"SELECT coalesce(percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM a.n - i.created_at)::bigint), -1)::float8 FROM cuu_tro.incidents i JOIN LATERAL (SELECT min(responded_at) FILTER (WHERE result='da_nhan') n FROM cuu_tro.incident_assignments WHERE incident_id=i.id) a ON a.n IS NOT NULL WHERE i.status IN ('da_cuu','dong') AND i.created_at < $den_ts;")")" \
  "$(num "$(tv 'SELECT coalesce(quantile_cont(phan_hoi_giay, 0.5), -1)::DOUBLE AS m FROM su_co WHERE phan_hoi_giay IS NOT NULL' | jf 'd["m"]')")"
check "DuckDB: tọa độ đã làm tròn 2 chữ số (không còn vị trí chính xác)" 0 \
  "$(tv 'SELECT count(*) AS n FROM su_co WHERE round(vi_do, 2) <> vi_do OR round(kinh_do, 2) <> kinh_do' | jf 'd["n"]')"
cot=$(luu_tru truy-van --json "SELECT column_name FROM (DESCRIBE SELECT * FROM su_co) UNION ALL SELECT column_name FROM (DESCRIBE SELECT * FROM phan_phoi) UNION ALL SELECT column_name FROM (DESCRIBE SELECT * FROM khoan_tien)" \
  | python3 -c 'import sys,json; print(",".join(json.loads(l)["column_name"] for l in sys.stdin if l.strip()))')
check "không có cột định danh trong tệp xuất" True \
  "$(python3 -c 'import sys; c=set(sys.argv[1].split(",")); cam={"reporter_phone","reporter_name","description","address_text","created_by","responded_by","contact_phone","contact_name","note"}; print(bool(c) and not (c & cam))' "$cot")"
# SĐT thật trong CSDL (seed + tin smoke tạo) không được xuất hiện trong bất kỳ tệp Parquet nào
sdt=$(sql <<<"SELECT string_agg(DISTINCT reporter_phone::text, ',') FROM cuu_tro.incidents;")
check "SĐT người báo trong CSDL không có trong bất kỳ tệp Parquet nào" 0 "$(
  docker compose --profile core --profile app --profile luu-tru run --rm --no-deps -T cuu-tro-luu-tru python - "$sdt" <<'PY' 2>/dev/null | tail -1
import asyncio, json, sys
import httpx
from cuu_tro_workflow import luu_tru as lt
async def main():
    async with httpx.AsyncClient(timeout=60) as h:
        kho = lt._kho_tu_env(h)
        m = json.loads(await kho.doc(lt.MANIFEST))
        sdt = [s for s in sys.argv[1].split(",") if s]
        trung = 0
        for ten, b in m["bang"].items():
            for thang in b["phan_vung"]:
                du = await kho.doc(lt.khoa_phan_vung(ten, thang))
                trung += sum(s.encode() in du for s in sdt)
        print(trung if sdt else "khong-co-sdt-de-so")
asyncio.run(main())
PY
)"

# ---------------- (4) Riêng tư, chỉ đọc ----------------
check "bucket lưu trữ riêng tư: đọc qua gateway không chữ ký bị từ chối" True \
  "$(c=$(curl -s -o /dev/null -w '%{http_code}' "$GW/files/cuu-tro-lakehouse/_manifest.json"); [ "$c" = 401 ] || [ "$c" = 403 ] && echo True || echo "$c")"
check "role cuu_tro_bi (dùng để xuất) không ghi được CSDL" True \
  "$(docker compose --profile core --profile app --profile luu-tru run --rm --no-deps -T cuu-tro-luu-tru python -c '
import asyncio, os, asyncpg
async def main():
    c = await asyncpg.connect(os.environ["BI_DB_URL"])
    try:
        await c.execute("UPDATE cuu_tro.supplies SET quantity = quantity")
        print("ghi-duoc")
    except (asyncpg.InsufficientPrivilegeError, asyncpg.ReadOnlySQLTransactionError):
        print(True)
    finally:
        await c.close()
asyncio.run(main())' 2>/dev/null | tail -1)"

if [ "$fail" -ne 0 ]; then echo "smoke-luu-tru: CÓ LỖI"; exit 1; fi
echo "smoke-luu-tru: tất cả đều đạt"
