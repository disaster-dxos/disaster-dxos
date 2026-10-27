# SPDX-License-Identifier: Apache-2.0
"""Luật ảnh hiện trường (#27), logic thuần để kiểm thử không cần S3/CSDL/Hasura.

- Loại tệp xác định bằng magic bytes (chữ ký đầu tệp), KHÔNG tin Content-Type hay đuôi tên tệp của client.
- Quyền theo vai trò, khớp metadata Hasura (apps/cuu-tro/hasura/metadata, #26):
    dieu-phoi   tải lên và xem ảnh của mọi tin kêu cứu
    cuu-ho      tải lên và xem ảnh của tin phân công cho đội mình
    tinh-nguyen chỉ tải lên cho tin mình vừa tạo, khi tin còn ở trạng thái tiep_nhan (lúc kêu cứu);
                không liệt kê ảnh của tin; chỉ xem lại được ảnh chính mình tải lên
  "Tin của đội mình" / "tin mình tạo" không viết lại ở đây: API hỏi Hasura bằng JWT + vai trò của
  người dùng, Hasura trả null nghĩa là không thấy (apps/cuu-tro/workflow/cuu_tro_workflow/api.py).
- Quét mã độc (#111, quet_ma_doc.py): clamd của lõi (profile sec) quét nội dung trước khi lưu; scan_status
  sach | chua_quet (máy quét không có hoặc lỗi). Tệp nhiễm không bao giờ được lưu.
"""

from dataclasses import dataclass

from .auth import VAI_TRO_CUU_HO, VAI_TRO_DIEU_PHOI, VAI_TRO_TINH_NGUYEN, NguoiDung

# Loại cho phép → đuôi object
DUOI = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
# Số byte đầu tệp cần để nhận dạng
SO_BYTE_DAU = 16

# Thứ tự ưu tiên khi người dùng có nhiều vai trò: vai trò rộng nhất
UU_TIEN = (VAI_TRO_DIEU_PHOI, VAI_TRO_CUU_HO, VAI_TRO_TINH_NGUYEN)
# Trạng thái tin cho phép tinh-nguyen gửi ảnh (tin kêu cứu mới, chưa phân công)
TRANG_THAI_TIN_MOI = "tiep_nhan"
# Tin đã đóng không nhận thêm ảnh
TRANG_THAI_DONG = "dong"


def nhan_dang(dau: bytes) -> str | None:
    """Trả content-type thật từ các byte đầu tệp, None nếu không phải JPEG/PNG/WebP."""
    # JPEG: SOI FF D8 rồi một marker FF xx
    if len(dau) >= 4 and dau[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    # PNG: chữ ký 8 byte, chunk đầu luôn là IHDR
    if dau[:8] == b"\x89PNG\r\n\x1a\n" and dau[12:16] == b"IHDR":
        return "image/png"
    # WebP: RIFF <cỡ 4 byte> WEBP rồi chunk VP8 / VP8L / VP8X
    if dau[:4] == b"RIFF" and dau[8:12] == b"WEBP" and dau[12:16] in (b"VP8 ", b"VP8L", b"VP8X"):
        return "image/webp"
    return None


def vai_tro_chinh(nd: NguoiDung) -> str | None:
    for v in UU_TIEN:
        if nd.co(v):
            return v
    return None


@dataclass(frozen=True)
class TuChoi:
    ma: int
    ly_do: str


def quyen_tai_len(vai_tro: str | None, tin: dict | None) -> TuChoi | None:
    """`tin` là kết quả incidents_by_pk mà Hasura trả cho đúng vai trò này (None = không thấy)."""
    if vai_tro not in UU_TIEN:
        return TuChoi(403, f"Cần vai trò: {', '.join(UU_TIEN)}")
    if tin is None:
        if vai_tro == VAI_TRO_DIEU_PHOI:
            return TuChoi(404, "Không có tin kêu cứu này")
        if vai_tro == VAI_TRO_CUU_HO:
            return TuChoi(403, "Tin kêu cứu không được phân công cho đội của bạn")
        return TuChoi(403, "Chỉ gửi ảnh cho tin kêu cứu do chính bạn tạo")
    if vai_tro == VAI_TRO_TINH_NGUYEN and tin.get("status") != TRANG_THAI_TIN_MOI:
        return TuChoi(403, "Tình nguyện viên chỉ gửi ảnh khi tạo tin kêu cứu mới (trạng thái tiep_nhan)")
    if tin.get("status") == TRANG_THAI_DONG:
        return TuChoi(409, "Tin kêu cứu đã đóng, không nhận thêm ảnh")
    return None


def quyen_liet_ke(vai_tro: str | None, tin: dict | None) -> TuChoi | None:
    """Liệt kê ảnh của một tin: dieu-phoi, cuu-ho (tin của đội mình). tinh-nguyen không được."""
    if vai_tro not in (VAI_TRO_DIEU_PHOI, VAI_TRO_CUU_HO):
        return TuChoi(403, f"Cần vai trò: {VAI_TRO_DIEU_PHOI}, {VAI_TRO_CUU_HO}")
    if tin is None:
        if vai_tro == VAI_TRO_DIEU_PHOI:
            return TuChoi(404, "Không có tin kêu cứu này")
        return TuChoi(403, "Tin kêu cứu không được phân công cho đội của bạn")
    return None


def quyen_xem(vai_tro: str | None, anh: dict | None) -> TuChoi | None:
    """`anh` là incident_media_by_pk mà Hasura trả cho vai trò này (đã lọc theo đội / người tải)."""
    if vai_tro not in UU_TIEN:
        return TuChoi(403, f"Cần vai trò: {', '.join(UU_TIEN)}")
    if anh is None:
        if vai_tro == VAI_TRO_DIEU_PHOI:
            return TuChoi(404, "Không có ảnh này")
        return TuChoi(403, "Bạn không có quyền xem ảnh này")
    return None


def object_key(incident_id: str, media_id: str, content_type: str) -> str:
    return f"su-co/{incident_id}/{media_id}.{DUOI[content_type]}"
