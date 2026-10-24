# SPDX-License-Identifier: Apache-2.0
"""Bộ giả lập trận lũ mẫu (#84): tệp dữ liệu, khớp seed, dạng đường lũ, tất định theo seed, phát lại."""

import json
import random
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from cuu_tro_workflow import cam_bien as cb
from cuu_tro_workflow import gia_lap

BAY_GIO = datetime(2026, 10, 20, 1, 0, tzinfo=timezone.utc)
SEED_SQL = Path(__file__).resolve().parents[2] / "db" / "seed" / "0001_xa_mau.sql"
TRAM_MUC_NUOC = [t for t in gia_lap.TRAM_MAU if t.kind == "muc_nuoc"]


def tram_trong_seed() -> dict[str, dict]:
    """Đọc các dòng INSERT INTO sensors của seed: mã → kind, unit, tọa độ, ngưỡng."""
    sql = SEED_SQL.read_text(encoding="utf-8")
    khoi = sql[sql.index("INSERT INTO sensors"):]
    khoi = khoi[:khoi.index("ON CONFLICT")]
    mau = re.compile(
        r"\('[0-9a-f-]+', '(?P<ma>[A-Z0-9_-]+)', '[^']+', '(?P<kind>\w+)', '(?P<unit>[^']+)',\s*"
        r"ST_MakePoint\((?P<x>[\d.]+), (?P<y>[\d.]+)\)::geography, (?P<cb>[\d.]+), (?P<nh>[\d.]+),")
    return {m["ma"]: m.groupdict() for m in mau.finditer(khoi)}


def test_tep_tran_lu_co_ghi_la_gia_lap():
    d = json.loads(gia_lap.TEP_TRAN_LU.read_text(encoding="utf-8"))
    assert "GIẢ LẬP" in d["_mo_ta"] and d["buoc_gio"] == 1
    assert len({t["ma"] for t in d["tram"]}) == len(d["tram"]) >= 9
    # Trạm miền Trung có tọa độ trong Quảng Nam / Đà Nẵng
    for t in gia_lap.TRAM_MAU:
        assert 107.2 <= t.kinh_do <= 108.8 and 14.9 <= t.vi_do <= 16.3, t.ma


def test_moi_tram_gia_lap_co_trong_seed_va_khop_nguong():
    seed = tram_trong_seed()
    for t in gia_lap.TRAM_MAU:
        assert t.ma in seed, f"{t.ma} không có trong seed sensors"
        s = seed[t.ma]
        assert s["kind"] == t.kind and s["unit"] == cb.DAI_LUONG[cb.KIND_SANG_DAI_LUONG[t.kind]][1]
        assert (float(s["cb"]), float(s["nh"])) == (t.nguong_canh_bao, t.nguong_nguy_hiem), t.ma
        assert (float(s["x"]), float(s["y"])) == pytest.approx((t.kinh_do, t.vi_do), abs=1e-4), t.ma


@pytest.mark.parametrize("tram", gia_lap.TRAM_MAU, ids=lambda t: t.ma)
def test_duong_lu_dang_dinh_rut(tram):
    c = tram.chuoi
    assert len(c) == 49  # 48 giờ, mỗi bước một giờ
    dinh = c.index(max(c))
    assert 0 < dinh < len(c) - 1
    assert list(c[:dinh + 1]) == sorted(c[:dinh + 1])  # dâng (không giảm) tới đỉnh
    assert list(c[dinh:]) == sorted(c[dinh:], reverse=True)  # rút (không tăng) sau đỉnh
    assert c[0] == tram.muc_nen and c[-1] < max(c)
    assert all(v >= 0 for v in c)


def test_dinh_vuot_nguong_va_thuong_nguon_len_truoc_ha_luu():
    theo_ma = {t.ma: t for t in gia_lap.TRAM_MAU}
    vuot = [t.ma for t in TRAM_MUC_NUOC if max(t.chuoi) >= t.nguong_nguy_hiem]
    chi_canh_bao = [t.ma for t in TRAM_MUC_NUOC if t.nguong_canh_bao <= max(t.chuoi) < t.nguong_nguy_hiem]
    assert len(vuot) >= 4 and chi_canh_bao  # có cả trạm lên mức nguy hiểm lẫn trạm chỉ tới mức cảnh báo
    gio_dinh = {m: t.chuoi.index(max(t.chuoi)) for m, t in theo_ma.items()}
    # Mưa đạt đỉnh trước; Ái Nghĩa (thượng nguồn Vu Gia) trước Câu Lâu, Câu Lâu trước Hội An (hạ lưu)
    assert gio_dinh["QN-LM-01"] < gio_dinh["QN-AN-01"] < gio_dinh["QN-CL-01"] < gio_dinh["QN-HA-01"]


@pytest.mark.parametrize("tram", gia_lap.TRAM_MAU, ids=lambda t: t.ma)
def test_kich_ban_tran_lu_theo_tep_roi_giu_gia_tri_cuoi(tram):
    rng = random.Random()
    day = [gia_lap.gia_tri_kich_ban(tram, "tran-lu", b, 6, rng) for b in range(len(tram.chuoi) + 3)]
    assert day[:len(tram.chuoi)] == [round(v, 1) for v in tram.chuoi]
    assert day[-3:] == [round(tram.chuoi[-1], 1)] * 3


def test_cung_seed_cung_chuoi_khac_seed_khac():
    def chay(seed):
        rng = random.Random(seed)
        return [gia_lap.gia_tri_kich_ban(t, "binh-thuong", b, 6, rng) for b in range(20) for t in gia_lap.TRAM_MAU]
    assert chay(42) == chay(42)
    assert chay(42) != chay(43)


def test_ban_tin_tran_lu_qua_kiem_tra_va_doi_muc_dung_nguong():
    rng = random.Random(1)
    t = next(x for x in gia_lap.TRAM_MAU if x.ma == "QN-AN-01")
    muc = []
    for b, td in enumerate(gia_lap.thoi_diem_phat_lai(BAY_GIO, len(t.chuoi), 1)):
        topic, p = gia_lap.ban_tin(t, gia_lap.gia_tri_kich_ban(t, "tran-lu", b, 6, rng), td)
        bt = cb.phan_tich(topic.replace("/", "."), p, BAY_GIO)
        muc.append(cb.muc_canh_bao(bt.gia_tri, Decimal(t.nguong_canh_bao), Decimal(t.nguong_nguy_hiem)))
    # bình thường → cảnh báo → nguy hiểm → cảnh báo → bình thường (không nhảy cóc khi rút)
    gon = [m for i, m in enumerate(muc) if i == 0 or m != muc[i - 1]]
    assert gon == ["binh_thuong", "canh_bao", "nguy_hiem", "canh_bao", "binh_thuong"]


def test_thoi_diem_phat_lai():
    moc = gia_lap.thoi_diem_phat_lai(BAY_GIO, 49, 1)
    assert moc[-1] == BAY_GIO and moc[0] == BAY_GIO - timedelta(hours=48)
    assert all(b - a == timedelta(hours=1) for a, b in zip(moc, moc[1:]))
    # cả chuỗi nằm trong khoảng consumer nhận (không quá cũ)
    assert BAY_GIO - moc[0] < cb.QUA_CU


def test_tran_lu_thieu_chuoi():
    t = gia_lap.TramGiaLap("X-1", "muc_nuoc", 1, 2, 3)
    with pytest.raises(ValueError):
        gia_lap.gia_tri_kich_ban(t, "tran-lu", 0, 6, random.Random())


def test_phat_lai_chi_dung_voi_tran_lu():
    with pytest.raises(SystemExit):
        gia_lap.main(["--phat-lai", "--kich-ban", "binh-thuong"])
