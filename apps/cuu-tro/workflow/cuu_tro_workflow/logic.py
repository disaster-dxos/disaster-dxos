# SPDX-License-Identifier: Apache-2.0
"""Logic thuần (không I/O) của luồng phân công cứu hộ: chọn đội, chuyển trạng thái tin kêu cứu.

Dùng được trong sandbox workflow của Temporal và kiểm thử bằng pytest không cần CSDL.
Giá trị trạng thái khớp CHECK của bảng cuu_tro.incidents / rescue_teams (db/migrations/0001).
"""

from dataclasses import dataclass, field

# Luồng trạng thái tin kêu cứu: tiep_nhan → phan_cong → dang_cuu → da_cuu → dong.
# Đội cứu hộ có thể xác nhận "đã cứu" khi chưa kịp chuyển dang_cuu (phan_cong → da_cuu).
# Điều phối được đóng thẳng tin không cần cứu (trùng, báo nhầm): tiep_nhan → dong.
CHUYEN_TRANG_THAI: dict[str, frozenset[str]] = {
    "tiep_nhan": frozenset({"phan_cong", "dong"}),
    "phan_cong": frozenset({"dang_cuu", "da_cuu"}),
    "dang_cuu": frozenset({"da_cuu"}),
    "da_cuu": frozenset({"dong"}),
    "dong": frozenset(),
}

DOI_SAN_SANG = "san_sang"
DOI_DANG_LAM_NHIEM_VU = "dang_lam_nhiem_vu"


class ChuyenTrangThaiKhongHopLe(ValueError):
    """Chuyển trạng thái không có trong CHUYEN_TRANG_THAI."""


def kiem_tra_chuyen_trang_thai(hien_tai: str, moi: str) -> None:
    """Báo lỗi nếu không được chuyển tin kêu cứu từ `hien_tai` sang `moi`."""
    if hien_tai not in CHUYEN_TRANG_THAI:
        raise ChuyenTrangThaiKhongHopLe(f"trạng thái không tồn tại: {hien_tai}")
    if moi not in CHUYEN_TRANG_THAI.get(hien_tai, frozenset()):
        raise ChuyenTrangThaiKhongHopLe(f"không được chuyển {hien_tai} → {moi}")


@dataclass
class DoiUngVien:
    """Một đội cứu hộ ứng viên, khoảng cách (mét) tới tin kêu cứu do PostGIS tính."""

    id: str
    ten: str
    trang_thai: str
    khoang_cach_m: float | None
    so_thanh_vien: int = 1


def chon_doi_gan_nhat(
    ung_vien: list[DoiUngVien], ban_kinh_m: float, bo_qua: frozenset[str] = frozenset()
) -> DoiUngVien | None:
    """Chọn đội sẵn sàng gần nhất trong bán kính; hòa khoảng cách thì đội đông người hơn, rồi theo id.

    Bỏ qua đội không sẵn sàng, chưa có vị trí (khoang_cach_m None) và đội trong `bo_qua`
    (vd đội vừa bị đội khác giành mất khi gán, xem activity gan_doi).
    """
    hop_le = [
        d
        for d in ung_vien
        if d.trang_thai == DOI_SAN_SANG
        and d.khoang_cach_m is not None
        and d.khoang_cach_m <= ban_kinh_m
        and d.id not in bo_qua
    ]
    if not hop_le:
        return None
    return min(hop_le, key=lambda d: (d.khoang_cach_m, -d.so_thanh_vien, d.id))


# ---------- Dữ liệu vào/ra của workflow và activity (Temporal tuần tự hóa dataclass thành JSON) ----------


@dataclass
class ThamSoPhanCong:
    incident_id: str
    # sub Keycloak của người điều phối khởi chạy (ghi vào lịch sử workflow)
    nguoi_khoi_chay: str = ""
    ban_kinh_m: int = 20000
    han_xac_nhan_giay: int = 6 * 3600
    so_lan_tim_doi: int = 10
    cho_tim_lai_giay: int = 60


@dataclass
class TinKeuCuu:
    id: str
    trang_thai: str
    doi_id: str | None = None


@dataclass
class XacNhan:
    nguoi: str
    vai_tro: str
    ghi_chu: str = ""


@dataclass
class TrangThaiPhanCong:
    """Trạng thái workflow trả về qua query `trang_thai` và GET /workflow/{id}."""

    incident_id: str
    buoc: str = "khoi_tao"
    doi_id: str | None = None
    doi_ten: str | None = None
    khoang_cach_m: float | None = None
    so_lan_tim: int = 0
    xac_nhan: XacNhan | None = None
    ket_qua: str | None = None
    lich_su: list[str] = field(default_factory=list)


# Kết quả cuối của workflow PhanCongCuuHo
KQ_DA_DONG = "da_dong"
KQ_KHONG_CO_DOI = "khong_co_doi"
KQ_QUA_HAN = "qua_han_xac_nhan"
KQ_BO_QUA = "bo_qua"
