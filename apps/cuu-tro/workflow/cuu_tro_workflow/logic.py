# SPDX-License-Identifier: Apache-2.0
"""Logic thuần (không I/O) của luồng phân công cứu hộ: chọn đội, chuyển trạng thái tin kêu cứu.

Dùng được trong sandbox workflow của Temporal và kiểm thử bằng pytest không cần CSDL.
Giá trị trạng thái khớp CHECK của bảng cuu_tro.incidents / rescue_teams (db/migrations/0001).
"""

from dataclasses import dataclass, field

# Luồng trạng thái tin kêu cứu: tiep_nhan → phan_cong → dang_cuu → da_cuu → dong.
# Đội cứu hộ có thể xác nhận "đã cứu" khi chưa kịp chuyển dang_cuu (phan_cong → da_cuu).
# Điều phối được đóng thẳng tin không cần cứu (trùng, báo nhầm): tiep_nhan → dong.
# Đội từ chối / quá hạn nhận / điều phối hủy khi chưa nhận: phan_cong → tiep_nhan (gỡ đội, #67).
CHUYEN_TRANG_THAI: dict[str, frozenset[str]] = {
    "tiep_nhan": frozenset({"phan_cong", "dong"}),
    "phan_cong": frozenset({"dang_cuu", "da_cuu", "tiep_nhan"}),
    "dang_cuu": frozenset({"da_cuu"}),
    "da_cuu": frozenset({"dong"}),
    "dong": frozenset(),
}

DOI_SAN_SANG = "san_sang"
DOI_DANG_LAM_NHIEM_VU = "dang_lam_nhiem_vu"

# Mức khẩn cấp, khớp CHECK incidents.urgency (0001) và hàm SQL urgency_rank (0007): 1 = khẩn nhất.
# Dùng làm thứ tự khởi chạy và priority_key của Temporal (số nhỏ được ưu tiên).
URGENCY_RANK: dict[str, int] = {"khan_cap": 1, "cao": 2, "trung_binh": 3, "thap": 4}
URGENCY_MAC_DINH = "trung_binh"


def uu_tien(urgency: str | None) -> int:
    """priority_key Temporal của một mức urgency (lạ/thiếu → như trung_binh)."""
    return URGENCY_RANK.get(urgency or "", URGENCY_RANK[URGENCY_MAC_DINH])


def han_nhan(han_theo_muc: dict[str, int], urgency: str | None) -> int:
    """Hạn (giây) để đội nhận nhiệm vụ theo urgency; mức không có trong bảng → hạn của trung_binh."""
    return han_theo_muc.get(urgency or "") or han_theo_muc.get(URGENCY_MAC_DINH) or HAN_NHAN_MAC_DINH[URGENCY_MAC_DINH]


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


HAN_NHAN_MAC_DINH: dict[str, int] = {"khan_cap": 300, "cao": 600, "trung_binh": 900, "thap": 1800}


@dataclass
class ThamSoPhanCong:
    incident_id: str
    # Người khởi chạy (tên đăng nhập Keycloak), hoặc "tu-dong" khi bộ khởi chạy outbox chạy (#67)
    nguoi_khoi_chay: str = ""
    ban_kinh_m: int = 20000
    han_xac_nhan_giay: int = 6 * 3600
    so_lan_tim_doi: int = 10
    cho_tim_lai_giay: int = 60
    # Hạn nhận nhiệm vụ theo urgency (giây); quá hạn thì gỡ đội, giao đội kế tiếp (#67)
    han_nhan_giay: dict[str, int] = field(default_factory=lambda: dict(HAN_NHAN_MAC_DINH))
    # Số lần giao tối đa (mỗi lần một đội); hết lần thì báo điều phối
    so_lan_giao_toi_da: int = 3


@dataclass
class TinKeuCuu:
    id: str
    trang_thai: str
    doi_id: str | None = None
    urgency: str = URGENCY_MAC_DINH


@dataclass
class XacNhan:
    nguoi: str
    vai_tro: str
    ghi_chu: str = ""
    # Đội mà người gửi đang thay mặt (API điền từ trạng thái workflow). Khác đội đang được giao →
    # workflow bỏ qua (phản hồi muộn của đội cũ sau khi đã phân công lại). None = không kiểm.
    doi_id: str | None = None


# Phản hồi cho một lần giao (signal nhan_nhiem_vu / tu_choi, #67)
PH_NHAN = "nhan"
PH_TU_CHOI = "tu_choi"


@dataclass
class PhanHoi:
    loai: str
    nguoi: str
    vai_tro: str
    doi_id: str | None = None
    ghi_chu: str = ""


@dataclass
class YeuCauHuy:
    nguoi: str
    ly_do: str = ""


# Kết quả của một lần giao trong lịch sử (CHECK incident_assignments.result, 0007)
GIAO_CHO_NHAN = "cho_nhan"
GIAO_DA_NHAN = "da_nhan"
GIAO_TU_CHOI = "tu_choi"
GIAO_QUA_HAN = "qua_han"
GIAO_HUY = "huy"

# Kết quả activity gan_doi
GAN_DA_GAN = "da_gan"
GAN_BI_GIANH = "bi_gianh"  # đội vừa bị gán cho tin khác
GAN_NHUONG = "nhuong"  # đội đang được giữ cho tin khẩn hơn đang chờ (luật ưu tiên, 0007)
GAN_TIN_DA_DOI = "tin_da_doi"  # tin không còn tiep_nhan (điều phối đã xử lý tay)


@dataclass
class YeuCauGan:
    incident_id: str
    doi_id: str
    ban_kinh_m: int
    # Cửa sổ (giây) để coi một tin khác "đang tìm đội" khi xét nhường đội
    cua_so_tim_giay: int
    workflow_run_id: str
    lan: int
    urgency: str
    khoang_cach_m: float | None
    han_nhan_giay: int


@dataclass
class KetQuaGiao:
    incident_id: str
    doi_id: str
    workflow_run_id: str
    lan: int
    ket_qua: str
    nguoi: str | None = None
    ghi_chu: str = ""


@dataclass
class LanGiao:
    """Một lần giao trong trạng thái workflow (bản gọn của dòng incident_assignments)."""

    lan: int
    doi_id: str
    doi_ten: str
    khoang_cach_m: float | None
    han_nhan_giay: int
    ket_qua: str = GIAO_CHO_NHAN
    nguoi: str | None = None


@dataclass
class BaoDieuPhoi:
    """Sự kiện báo điều phối viên (NATS cuu-tro.dieu-phoi.can-xu-ly.<incident_id>)."""

    incident_id: str
    ly_do: str
    urgency: str
    so_lan_giao: int
    workflow_id: str
    mo_ta: str = ""


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
    urgency: str | None = None
    han_nhan_giay: int | None = None
    giao: list[LanGiao] = field(default_factory=list)
    da_bao_dieu_phoi: bool = False


# Kết quả cuối của workflow PhanCongCuuHo
KQ_DA_DONG = "da_dong"
KQ_KHONG_CO_DOI = "khong_co_doi"
KQ_QUA_HAN = "qua_han_xac_nhan"
KQ_BO_QUA = "bo_qua"
KQ_HET_LAN_GIAO = "het_lan_giao"
KQ_DA_HUY = "da_huy"

# Lý do báo điều phối
BAO_HET_LAN_GIAO = "het_lan_giao"
BAO_KHONG_CO_DOI = "khong_co_doi"
BAO_QUA_HAN_XAC_NHAN = "qua_han_xac_nhan"
