# SPDX-License-Identifier: Apache-2.0
"""Logic thuần: chọn đội gần nhất, chuyển trạng thái tin kêu cứu."""

import pytest

from cuu_tro_workflow.logic import (
    CHUYEN_TRANG_THAI,
    ChuyenTrangThaiKhongHopLe,
    DoiUngVien,
    chon_doi_gan_nhat,
    kiem_tra_chuyen_trang_thai,
)


def doi(id_, km, trang_thai="san_sang", so=5):
    return DoiUngVien(id=id_, ten=f"Đội {id_}", trang_thai=trang_thai,
                      khoang_cach_m=None if km is None else km * 1000, so_thanh_vien=so)


def test_chon_doi_gan_nhat():
    assert chon_doi_gan_nhat([doi("a", 2.0), doi("b", 0.4), doi("c", 1.1)], 20000).id == "b"


def test_bo_qua_doi_khong_san_sang_va_chua_co_vi_tri():
    ung_vien = [doi("ban", 0.1, "dang_lam_nhiem_vu"), doi("nghi", 0.2, "nghi"), doi("mat", None), doi("ok", 3)]
    assert chon_doi_gan_nhat(ung_vien, 20000).id == "ok"


def test_ngoai_ban_kinh_thi_khong_chon():
    assert chon_doi_gan_nhat([doi("xa", 25)], 20000) is None
    assert chon_doi_gan_nhat([doi("bien", 20)], 20000).id == "bien"


def test_khong_co_ung_vien():
    assert chon_doi_gan_nhat([], 20000) is None


def test_hoa_khoang_cach_uu_tien_doi_dong_nguoi_roi_theo_id():
    assert chon_doi_gan_nhat([doi("a", 1, so=4), doi("b", 1, so=8)], 20000).id == "b"
    assert chon_doi_gan_nhat([doi("b", 1), doi("a", 1)], 20000).id == "a"


def test_bo_qua_doi_vua_bi_gianh():
    ung_vien = [doi("gan", 0.3), doi("xa_hon", 0.9)]
    assert chon_doi_gan_nhat(ung_vien, 20000, frozenset({"gan"})).id == "xa_hon"
    assert chon_doi_gan_nhat(ung_vien, 20000, frozenset({"gan", "xa_hon"})) is None


@pytest.mark.parametrize("tu,den", [
    ("tiep_nhan", "phan_cong"), ("phan_cong", "dang_cuu"), ("phan_cong", "da_cuu"),
    ("dang_cuu", "da_cuu"), ("da_cuu", "dong"), ("tiep_nhan", "dong"),
])
def test_chuyen_hop_le(tu, den):
    kiem_tra_chuyen_trang_thai(tu, den)


@pytest.mark.parametrize("tu,den", [
    ("tiep_nhan", "da_cuu"), ("phan_cong", "tiep_nhan"), ("dang_cuu", "dong"),
    ("dong", "tiep_nhan"), ("da_cuu", "phan_cong"), ("khong_ro", "dong"), ("tiep_nhan", "khong_ro"),
])
def test_chuyen_khong_hop_le(tu, den):
    with pytest.raises(ChuyenTrangThaiKhongHopLe):
        kiem_tra_chuyen_trang_thai(tu, den)


def test_trang_thai_khop_check_cua_bang_incidents():
    # CHECK (status IN (...)) trong db/migrations/0001_bang_nghiep_vu.sql
    assert set(CHUYEN_TRANG_THAI) == {"tiep_nhan", "phan_cong", "dang_cuu", "da_cuu", "dong"}
    for dich in CHUYEN_TRANG_THAI.values():
        assert dich <= set(CHUYEN_TRANG_THAI)
