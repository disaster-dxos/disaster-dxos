# SPDX-License-Identifier: Apache-2.0
"""Lưu trữ lịch sử (#91): xuất dữ liệu cũ của apps/cuu-tro ra Parquet trên SeaweedFS, truy vấn bằng DuckDB.

Chạy (container cuu-tro-luu-tru, profile luu-tru; xem Makefile):
  python -m cuu_tro_workflow.luu_tru xuat [--den YYYY-MM-DD]   xuất mọi dòng có thời điểm < --den
                                                                (mặc định: đầu tháng hiện tại, giờ Việt Nam)
  python -m cuu_tro_workflow.luu_tru truy-van "<SQL>"          tải Parquet về thư mục tạm, chạy SQL DuckDB
                                                                trên các view su_co, so_do, phan_phoi, khoan_tien

Bảng xuất (mỗi bảng phân vùng theo tháng giờ Việt Nam, kiểu Hive: <bảng>/thang=YYYY-MM/du-lieu.parquet):
  su_co       tin kêu cứu đã xong (da_cuu, dong): mức khẩn, trạng thái, nguồn, số người, tọa độ LÀM TRÒN
              2 chữ số (~1 km), thời điểm tạo / nhận nhiệm vụ / đóng, thời gian phản hồi, số lần giao, đội
  so_do       chuỗi đo trạm cảm biến: mã trạm, đại lượng, đơn vị, thời điểm, giá trị, mức
  phan_phoi   phiếu xuất kho (phân phát hàng): mặt hàng, đơn vị, số lượng, kho, điểm nhận, chỉ số lá sổ cái
  khoan_tien  bút toán tiền cứu trợ thu/chi (#89): số tiền, hạng mục, nội dung, điểm nhận, chỉ số lá sổ cái
Khử định danh: đọc bằng role chỉ đọc <app>_bi (migration 0012), role này KHÔNG có quyền đọc SĐT, họ tên,
mô tả tự do, địa chỉ, người lập/người nhận nhiệm vụ; câu SQL dưới đây cũng không chọn các cột đó.
Idempotent: mỗi lần chạy dựng lại toàn bộ phân vùng < --den, sắp xếp cố định → cùng dữ liệu ra cùng tệp
(cùng SHA-256). _manifest.json ghi số dòng + SHA-256 từng tệp; tệp không đổi thì không ghi lại, phân vùng
không còn dữ liệu thì xóa. Dữ liệu gốc trong PostgreSQL KHÔNG bị xóa (tách nóng/lịch sử, nguyên lý B1).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import duckdb

GIO_VN = timezone(timedelta(hours=7))
PHIEN_BAN = "cuu-tro.luu-tru/v1"
TEN_TEP = "du-lieu.parquet"
MANIFEST = "_manifest.json"
# Cột không bao giờ được có trong tệp xuất (kiểm ở pytest và smoke)
COT_CAM = ("reporter_phone", "reporter_name", "description", "address_text", "created_by", "responded_by",
           "contact_phone", "contact_name", "note")


@dataclass(frozen=True)
class Bang:
    ten: str
    sql: str            # $1 = mốc --den (timestamptz)
    cot_thoi_gian: str  # cột dùng để chia tháng
    schema: str         # DDL cột của bảng DuckDB, đúng thứ tự cột của câu SQL
    sap_xep: str


BANG = (
    Bang("su_co", """
SELECT i.id::text AS id, i.urgency AS muc_khan, i.status AS trang_thai, i.source AS nguon, i.people_count AS so_nguoi,
       round(ST_Y(i.location::geometry)::numeric, 2)::float8 AS vi_do,
       round(ST_X(i.location::geometry)::numeric, 2)::float8 AS kinh_do,
       i.created_at AS tao_luc, a.nhan_luc, i.updated_at AS dong_luc,
       extract(epoch FROM a.nhan_luc - i.created_at)::bigint AS phan_hoi_giay,
       coalesce(a.so_lan_giao, 0)::int AS so_lan_giao, i.assigned_team_id::text AS doi_id
  FROM cuu_tro.incidents i
  LEFT JOIN LATERAL (SELECT min(responded_at) FILTER (WHERE result = 'da_nhan') AS nhan_luc, count(*) AS so_lan_giao
                       FROM cuu_tro.incident_assignments WHERE incident_id = i.id) a ON true
 WHERE i.status IN ('da_cuu', 'dong') AND i.created_at < $1""", "tao_luc",
         "id VARCHAR, muc_khan VARCHAR, trang_thai VARCHAR, nguon VARCHAR, so_nguoi INTEGER, vi_do DOUBLE, "
         "kinh_do DOUBLE, tao_luc TIMESTAMPTZ, nhan_luc TIMESTAMPTZ, dong_luc TIMESTAMPTZ, phan_hoi_giay BIGINT, "
         "so_lan_giao INTEGER, doi_id VARCHAR", "tao_luc, id"),
    Bang("so_do", """
SELECT s.code AS ma_tram, s.kind AS dai_luong, s.unit AS don_vi, r.observed_at AS thoi_diem, r.value AS gia_tri,
       r.level AS muc
  FROM cuu_tro.sensor_readings r JOIN cuu_tro.sensors s ON s.id = r.sensor_id
 WHERE r.observed_at < $1""", "thoi_diem",
         "ma_tram VARCHAR, dai_luong VARCHAR, don_vi VARCHAR, thoi_diem TIMESTAMPTZ, gia_tri DECIMAL(10,2), muc VARCHAR",
         "thoi_diem, ma_tram"),
    Bang("phan_phoi", """
SELECT m.id::text AS id, s.item_name AS mat_hang, s.unit AS don_vi, m.quantity AS so_luong, s.storage_name AS kho,
       sh.name AS diem_nhan, m.created_at AS thoi_diem, m.ledger_index AS chi_so_la
  FROM cuu_tro.supply_movements m JOIN cuu_tro.supplies s ON s.id = m.supply_id
  LEFT JOIN cuu_tro.shelters sh ON sh.id = m.shelter_id
 WHERE m.direction = 'xuat' AND m.created_at < $1""", "thoi_diem",
         "id VARCHAR, mat_hang VARCHAR, don_vi VARCHAR, so_luong DECIMAL(14,2), kho VARCHAR, diem_nhan VARCHAR, "
         "thoi_diem TIMESTAMPTZ, chi_so_la BIGINT", "thoi_diem, id"),
    Bang("khoan_tien", """
SELECT k.id::text AS id, k.direction AS chieu, k.amount AS so_tien, k.currency AS don_vi, k.category AS hang_muc,
       k.purpose AS noi_dung, sh.name AS diem_nhan, k.created_at AS thoi_diem, k.ledger_index AS chi_so_la
  FROM cuu_tro.relief_fund_entries k LEFT JOIN cuu_tro.shelters sh ON sh.id = k.shelter_id
 WHERE k.created_at < $1""", "thoi_diem",
         "id VARCHAR, chieu VARCHAR, so_tien DECIMAL(16,0), don_vi VARCHAR, hang_muc VARCHAR, noi_dung VARCHAR, "
         "diem_nhan VARCHAR, thoi_diem TIMESTAMPTZ, chi_so_la BIGINT", "thoi_diem, id"),
)


def moc_mac_dinh(hom_nay: date | None = None) -> datetime:
    """Đầu tháng hiện tại (giờ Việt Nam): tháng đang diễn ra chưa "cũ", không xuất."""
    d = hom_nay or datetime.now(GIO_VN).date()
    return datetime(d.year, d.month, 1, tzinfo=GIO_VN)


def thang_cua(t: datetime) -> str:
    return t.astimezone(GIO_VN).strftime("%Y-%m")


def chia_thang(dong: list[dict[str, Any]], cot: str) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for d in dong:
        out.setdefault(thang_cua(d[cot]), []).append(d)
    return dict(sorted(out.items()))


def ghi_parquet(bang: Bang, dong: list[dict[str, Any]], duong_dan: Path) -> None:
    """Ghi một phân vùng: bảng DuckDB tạm theo schema cố định, sắp xếp cố định, nén zstd."""
    cot = [c.split()[0] for c in bang.schema.split(", ")]
    con = duckdb.connect()
    try:
        con.execute("SET TimeZone = 'UTC'")
        con.execute(f"CREATE TABLE t ({bang.schema})")
        if dong:
            con.executemany(f"INSERT INTO t VALUES ({', '.join('?' * len(cot))})", [[d[c] for c in cot] for d in dong])
        duong_dan.parent.mkdir(parents=True, exist_ok=True)
        con.execute(f"COPY (SELECT * FROM t ORDER BY {bang.sap_xep}) TO '{duong_dan}' "
                    "(FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 100000)")
    finally:
        con.close()


def sha256_tep(duong_dan: Path) -> str:
    return hashlib.sha256(duong_dan.read_bytes()).hexdigest()


def khoa_phan_vung(ten: str, thang: str) -> str:
    return f"{ten}/thang={thang}/{TEN_TEP}"


def dung_phan_vung(dong_theo_bang: dict[str, list[dict[str, Any]]], thu_muc: Path, den: datetime
                   ) -> tuple[dict[str, Any], dict[str, Path]]:
    """Ghi mọi phân vùng ra thư mục; trả (manifest, {khóa S3: tệp})."""
    manifest: dict[str, Any] = {"phien_ban": PHIEN_BAN, "den": den.isoformat(), "bang": {}}
    tep: dict[str, Path] = {}
    for bang in BANG:
        pv: dict[str, Any] = {}
        for thang, dong in chia_thang(dong_theo_bang.get(bang.ten, []), bang.cot_thoi_gian).items():
            k = khoa_phan_vung(bang.ten, thang)
            p = thu_muc / k
            ghi_parquet(bang, dong, p)
            pv[thang] = {"so_dong": len(dong), "sha256": sha256_tep(p), "kich_thuoc": p.stat().st_size}
            tep[k] = p
        manifest["bang"][bang.ten] = {"cot": [c.split()[0] for c in bang.schema.split(", ")], "phan_vung": pv}
    return manifest, tep


def can_ghi(manifest_moi: dict[str, Any], manifest_cu: dict[str, Any] | None) -> tuple[list[str], list[str]]:
    """(khóa phải ghi, khóa phải xóa) so với manifest đã có trên S3."""
    cu: dict[str, str] = {}
    for ten, b in ((manifest_cu or {}).get("bang") or {}).items():
        for thang, x in b.get("phan_vung", {}).items():
            cu[khoa_phan_vung(ten, thang)] = x["sha256"]
    moi = {khoa_phan_vung(ten, thang): x["sha256"]
           for ten, b in manifest_moi["bang"].items() for thang, x in b["phan_vung"].items()}
    return sorted(k for k, h in moi.items() if cu.get(k) != h), sorted(set(cu) - set(moi))


def json_manifest(m: dict[str, Any]) -> bytes:
    return json.dumps(m, ensure_ascii=False, sort_keys=True, indent=2).encode()


async def doc_csdl(db_url: str, den: datetime) -> dict[str, list[dict[str, Any]]]:
    import asyncpg

    con = await asyncpg.connect(db_url)
    try:
        return {b.ten: [dict(r) for r in await con.fetch(b.sql, den)] for b in BANG}
    finally:
        await con.close()


async def xuat(db_url: str, kho, den: datetime) -> dict[str, Any]:
    """Xuất mọi phân vùng < den lên bucket lưu trữ. Trả tóm tắt (để in và kiểm thử)."""
    dong = await doc_csdl(db_url, den)
    with tempfile.TemporaryDirectory() as tmp:
        manifest, tep = dung_phan_vung(dong, Path(tmp), den)
        cu_raw = await kho.doc(MANIFEST)
        cu = json.loads(cu_raw) if cu_raw else None
        ghi, xoa = can_ghi(manifest, cu)
        for k in ghi:
            await kho.ghi(k, tep[k].read_bytes(), "application/vnd.apache.parquet")
        for k in xoa:
            await kho.xoa(k)
        moi = json_manifest(manifest)
        if cu_raw != moi:
            await kho.ghi(MANIFEST, moi, "application/json")
    return {"den": den.isoformat(), "ghi": ghi, "xoa": xoa, "khong_doi": len(tep) - len(ghi),
            "so_dong": {b: sum(x["so_dong"] for x in m["phan_vung"].values()) for b, m in manifest["bang"].items()},
            "manifest_doi": cu_raw != moi}


def mo_duckdb(thu_muc: Path, manifest: dict[str, Any]) -> duckdb.DuckDBPyConnection:
    """DuckDB trong bộ nhớ, mỗi bảng một view đọc Parquet phân vùng Hive (cột thang)."""
    con = duckdb.connect()
    con.execute("SET TimeZone = 'Asia/Ho_Chi_Minh'")
    for bang in BANG:
        if manifest["bang"].get(bang.ten, {}).get("phan_vung"):
            mau = (thu_muc / bang.ten / "thang=*" / TEN_TEP).as_posix()
            con.execute(f"CREATE VIEW {bang.ten} AS SELECT * FROM read_parquet('{mau}', hive_partitioning = true)")
        else:  # chưa có dữ liệu: view rỗng đúng schema để câu SQL mẫu vẫn chạy
            cot = ", ".join(f"NULL::{c.split(' ', 1)[1]} AS {c.split()[0]}" for c in bang.schema.split(", "))
            con.execute(f"CREATE VIEW {bang.ten} AS SELECT * FROM (SELECT {cot}, NULL::VARCHAR AS thang) WHERE false")
    return con


async def truy_van(kho, sql: str) -> list[tuple]:
    raw = await kho.doc(MANIFEST)
    if raw is None:
        raise SystemExit("Chưa có dữ liệu lưu trữ: chạy trước 'python -m cuu_tro_workflow.luu_tru xuat'")
    manifest = json.loads(raw)
    with tempfile.TemporaryDirectory() as tmp:
        for ten, b in manifest["bang"].items():
            for thang in b["phan_vung"]:
                k = khoa_phan_vung(ten, thang)
                p = Path(tmp) / k
                p.parent.mkdir(parents=True, exist_ok=True)
                du_lieu = await kho.doc(k)
                if du_lieu is None:
                    raise SystemExit(f"Thiếu tệp {k} so với manifest")
                if hashlib.sha256(du_lieu).hexdigest() != b["phan_vung"][thang]["sha256"]:
                    raise SystemExit(f"Tệp {k} khác SHA-256 trong manifest (bị sửa?)")
                p.write_bytes(du_lieu)
        con = mo_duckdb(Path(tmp), manifest)
        try:
            cur = con.execute(sql)
            ten_cot = [d[0] for d in cur.description] if cur.description else []
            return [tuple(ten_cot), *cur.fetchall()]
        finally:
            con.close()


def _kho_tu_env(http):
    from .s3 import KhoAnh

    return KhoAnh(endpoint=os.environ.get("S3_ENDPOINT", "http://seaweedfs:8333"),
                  bucket=os.environ.get("LUU_TRU_BUCKET", "cuu-tro-lakehouse"),
                  access_key=os.environ.get("S3_ACCESS_KEY", ""), secret_key=os.environ.get("S3_SECRET_KEY", ""),
                  gateway_public_url=os.environ.get("GATEWAY_PUBLIC_URL", "http://localhost:9080"), http=http)


def _in_bang(hang: list[tuple]) -> None:
    def s(v: Any) -> str:
        return "NULL" if v is None else str(v)
    if not hang:
        return
    rong = [max(len(s(h[i])) for h in hang) for i in range(len(hang[0]))]
    for j, h in enumerate(hang):
        print(" | ".join(s(v).ljust(rong[i]) for i, v in enumerate(h)))
        if j == 0:
            print("-+-".join("-" * w for w in rong))


async def _main(argv: list[str]) -> int:
    import httpx

    ap = argparse.ArgumentParser(prog="luu_tru", description="Lưu trữ lịch sử ra Parquet + truy vấn DuckDB")
    sub = ap.add_subparsers(dest="lenh", required=True)
    x = sub.add_parser("xuat", help="xuất dữ liệu cũ ra Parquet trên SeaweedFS")
    x.add_argument("--den", type=date.fromisoformat, help="xuất dòng có thời điểm trước ngày này (giờ Việt Nam)")
    q = sub.add_parser("truy-van", help="chạy SQL DuckDB trên các view su_co, so_do, phan_phoi, khoan_tien")
    q.add_argument("sql")
    q.add_argument("--json", action="store_true", help="in kết quả dạng JSON (mỗi dòng một object)")
    a = ap.parse_args(argv)
    async with httpx.AsyncClient(timeout=60) as http:
        kho = _kho_tu_env(http)
        if a.lenh == "xuat":
            db_url = os.environ.get("BI_DB_URL", "")
            if not db_url:
                raise SystemExit("Thiếu BI_DB_URL (bao agent chưa render bí mật?)")
            den = datetime(a.den.year, a.den.month, a.den.day, tzinfo=GIO_VN) if a.den else moc_mac_dinh()
            print(json.dumps(await xuat(db_url, kho, den), ensure_ascii=False))
        else:
            hang = await truy_van(kho, a.sql)
            if a.json:
                for h in hang[1:]:
                    print(json.dumps(dict(zip(hang[0], h)), ensure_ascii=False, default=str))
            else:
                _in_bang(hang)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(sys.argv[1:])))
