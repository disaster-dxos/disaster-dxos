# SPDX-License-Identifier: Apache-2.0
"""Lưu trữ lịch sử Parquet + DuckDB (#91): khử định danh (câu SQL và schema không có cột định danh, tệp
không chứa SĐT), phân vùng theo tháng giờ Việt Nam, idempotent (cùng dữ liệu → cùng tệp, lần chạy lại
không ghi gì), xóa phân vùng không còn, truy vấn DuckDB, phát hiện tệp bị sửa so với manifest."""

import asyncio
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from cuu_tro_workflow import luu_tru as lt

UTC = timezone.utc


def su_co(n: int, t: datetime) -> dict:
    return {"id": str(uuid.UUID(int=n)), "muc_khan": "cao", "trang_thai": "dong", "nguon": "web", "so_nguoi": 3,
            "vi_do": 15.85, "kinh_do": 108.1, "tao_luc": t, "nhan_luc": t + timedelta(minutes=4),
            "dong_luc": t + timedelta(hours=2), "phan_hoi_giay": 240, "so_lan_giao": 1, "doi_id": None}


def du_lieu() -> dict[str, list[dict]]:
    t9 = datetime(2026, 9, 15, 2, 0, tzinfo=UTC)
    bien = datetime(2026, 9, 30, 20, 0, tzinfo=UTC)   # 03:00 ngày 1/10 giờ Việt Nam → tháng 10
    return {
        "su_co": [su_co(1, t9), su_co(2, bien), su_co(3, t9 + timedelta(days=1))],
        "so_do": [{"ma_tram": "QN-CL-01", "dai_luong": "muc_nuoc", "don_vi": "cm", "thoi_diem": t9 + timedelta(hours=h),
                   "gia_tri": Decimal(f"{300 + h}.50"), "muc": "canh_bao"} for h in range(5)],
        "phan_phoi": [{"id": str(uuid.UUID(int=10)), "mat_hang": "Mì tôm", "don_vi": "thùng", "so_luong": Decimal("40.00"),
                       "kho": "Kho xã", "diem_nhan": "Trường THCS", "thoi_diem": bien, "chi_so_la": 7}],
        "khoan_tien": [{"id": str(uuid.UUID(int=20)), "chieu": "thu", "so_tien": Decimal("50000000"), "don_vi": "VND",
                        "hang_muc": "ung_ho", "noi_dung": "Ủng hộ", "diem_nhan": None, "thoi_diem": t9, "chi_so_la": 3}],
    }


DEN = datetime(2026, 11, 1, tzinfo=lt.GIO_VN)


# ---------------- Khử định danh ----------------
@pytest.mark.parametrize("bang", lt.BANG, ids=lambda b: b.ten)
def test_khong_chon_va_khong_xuat_cot_dinh_danh(bang):
    cot = [c.split()[0] for c in bang.schema.split(", ")]
    assert not set(cot) & set(lt.COT_CAM)
    sql = bang.sql.lower()
    for c in lt.COT_CAM:
        assert c not in sql, f"{bang.ten}: câu SQL nhắc tới cột {c}"
    assert "$1" in bang.sql  # luôn có mốc --den


def test_toa_do_su_co_lam_tron_trong_sql():
    sql = next(b for b in lt.BANG if b.ten == "su_co").sql
    assert sql.count("round(ST_") == 2 and "::numeric, 2)" in sql


def test_tep_parquet_khong_chua_sdt(tmp_path):
    d = du_lieu()
    d["su_co"][0]["sdt_lot_vao"] = "0905123456"   # cột thừa trong dữ liệu nguồn: không được ra tệp
    manifest, tep = lt.dung_phan_vung(d, tmp_path, DEN)
    for p in tep.values():
        assert b"0905123456" not in p.read_bytes()
    con = duckdb.connect()
    cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{tep['su_co/thang=2026-09/du-lieu.parquet']}', hive_partitioning = false)").fetchall()]
    assert cols == manifest["bang"]["su_co"]["cot"] and "sdt_lot_vao" not in cols


# ---------------- Phân vùng ----------------
def test_phan_vung_theo_thang_gio_viet_nam(tmp_path):
    manifest, tep = lt.dung_phan_vung(du_lieu(), tmp_path, DEN)
    assert manifest["phien_ban"] == lt.PHIEN_BAN and manifest["den"] == "2026-11-01T00:00:00+07:00"
    assert manifest["bang"]["su_co"]["phan_vung"]["2026-09"]["so_dong"] == 2
    assert manifest["bang"]["su_co"]["phan_vung"]["2026-10"]["so_dong"] == 1   # 20:00 UTC 30/9 = 1/10 giờ VN
    assert set(tep) == {"su_co/thang=2026-09/du-lieu.parquet", "su_co/thang=2026-10/du-lieu.parquet",
                        "so_do/thang=2026-09/du-lieu.parquet", "phan_phoi/thang=2026-10/du-lieu.parquet",
                        "khoan_tien/thang=2026-09/du-lieu.parquet"}


def test_moc_mac_dinh_la_dau_thang_gio_viet_nam():
    assert lt.moc_mac_dinh(date(2026, 10, 24)) == datetime(2026, 10, 1, tzinfo=lt.GIO_VN)
    assert lt.thang_cua(datetime(2026, 10, 31, 17, 0, tzinfo=UTC)) == "2026-11"


# ---------------- Idempotent ----------------
def test_cung_du_lieu_cung_tep_va_cung_manifest(tmp_path):
    d1, d2 = du_lieu(), du_lieu()
    d2["so_do"].reverse()   # thứ tự đọc từ CSDL khác: tệp vẫn giống (sắp xếp cố định)
    m1, _ = lt.dung_phan_vung(d1, tmp_path / "a", DEN)
    m2, _ = lt.dung_phan_vung(d2, tmp_path / "b", DEN)
    assert lt.json_manifest(m1) == lt.json_manifest(m2)


def test_can_ghi_chi_phan_vung_doi_va_xoa_phan_vung_mat(tmp_path):
    m1, _ = lt.dung_phan_vung(du_lieu(), tmp_path / "a", DEN)
    ghi, xoa = lt.can_ghi(m1, None)
    assert len(ghi) == 5 and xoa == []
    assert lt.can_ghi(m1, json.loads(lt.json_manifest(m1))) == ([], [])
    d = du_lieu()
    d["so_do"].append({**d["so_do"][0], "thoi_diem": d["so_do"][0]["thoi_diem"] + timedelta(days=1)})
    d["phan_phoi"] = []
    m2, _ = lt.dung_phan_vung(d, tmp_path / "b", DEN)
    assert lt.can_ghi(m2, m1) == (["so_do/thang=2026-09/du-lieu.parquet"], ["phan_phoi/thang=2026-10/du-lieu.parquet"])


class KhoGia:
    def __init__(self):
        self.obj: dict[str, bytes] = {}
        self.goi: list[tuple[str, str]] = []

    async def doc(self, k):
        return self.obj.get(k)

    async def ghi(self, k, b, ct):
        self.goi.append(("ghi", k))
        self.obj[k] = b

    async def xoa(self, k):
        self.goi.append(("xoa", k))
        self.obj.pop(k, None)


def test_xuat_hai_lan_lan_sau_khong_ghi_gi(monkeypatch):
    async def doc_csdl(db_url, den):
        return du_lieu()
    monkeypatch.setattr(lt, "doc_csdl", doc_csdl)
    kho = KhoGia()
    kq1 = asyncio.run(lt.xuat("postgres://x", kho, DEN))
    assert len(kq1["ghi"]) == 5 and kq1["manifest_doi"] and kq1["so_dong"]["su_co"] == 3
    n = len(kho.goi)
    kq2 = asyncio.run(lt.xuat("postgres://x", kho, DEN))
    assert kq2["ghi"] == [] and kq2["xoa"] == [] and kq2["khong_doi"] == 5 and not kq2["manifest_doi"]
    assert len(kho.goi) == n   # không một lệnh ghi nào lên S3


# ---------------- Truy vấn DuckDB ----------------
def kho_da_xuat(monkeypatch) -> KhoGia:
    async def doc_csdl(db_url, den):
        return du_lieu()
    monkeypatch.setattr(lt, "doc_csdl", doc_csdl)
    kho = KhoGia()
    asyncio.run(lt.xuat("postgres://x", kho, DEN))
    return kho


def test_truy_van_duckdb_tren_parquet(monkeypatch):
    kho = kho_da_xuat(monkeypatch)
    hang = asyncio.run(lt.truy_van(kho, "SELECT thang, count(*) AS n, median(phan_hoi_giay) AS ph FROM su_co GROUP BY 1 ORDER BY 1"))
    assert hang == [("thang", "n", "ph"), ("2026-09", 2, 240.0), ("2026-10", 1, 240.0)]
    hang = asyncio.run(lt.truy_van(kho, "SELECT max(gia_tri), sum(so_tien) FROM so_do, khoan_tien"))
    assert hang[1] == (Decimal("304.50"), Decimal("250000000"))


def test_truy_van_bang_rong_van_chay(monkeypatch):
    async def doc_csdl(db_url, den):
        return {"su_co": du_lieu()["su_co"]}
    monkeypatch.setattr(lt, "doc_csdl", doc_csdl)
    kho = KhoGia()
    asyncio.run(lt.xuat("postgres://x", kho, DEN))
    assert asyncio.run(lt.truy_van(kho, "SELECT count(*) FROM khoan_tien"))[1] == (0,)


def test_tep_bi_sua_so_voi_manifest_thi_tu_choi(monkeypatch):
    kho = kho_da_xuat(monkeypatch)
    k = "su_co/thang=2026-09/du-lieu.parquet"
    kho.obj[k] = kho.obj[k][:-1] + b"\x00"
    with pytest.raises(SystemExit, match="SHA-256"):
        asyncio.run(lt.truy_van(kho, "SELECT 1"))


def test_chua_xuat_thi_bao_ro():
    with pytest.raises(SystemExit, match="Chưa có dữ liệu"):
        asyncio.run(lt.truy_van(KhoGia(), "SELECT 1"))
