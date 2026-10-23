# SPDX-License-Identifier: Apache-2.0
"""Tiếp nhận tin kêu cứu qua API (#66): Poka-yoke ở tầng API, logic thuần (không I/O).

Bổ sung cho ràng buộc ở tầng dữ liệu (#25, migration 0001): CSDL vẫn là chốt chặn cuối (tọa độ NOT NULL,
domain phone_vn, trigger incidents_no_duplicate có khóa advisory theo SĐT). API kiểm trước để trả lỗi
tiếng Việt chỉ rõ trường sai (422) và ánh xạ lỗi trùng của trigger thành 409 kèm mã tin đang mở.

Không ghi SĐT ra log, không đưa giá trị SĐT vào thông báo lỗi.
"""

import math
import re
from dataclasses import dataclass
from typing import Any

URGENCY = ("khan_cap", "cao", "trung_binh", "thap")
NGUON = ("app", "web", "dien_thoai", "telegram", "mang_xa_hoi", "khac")
MO_TA_TOI_DA = 500
DIA_CHI_TOI_DA = 300
TEN_TOI_DA = 100
SO_NGUOI_TOI_DA = 10000
# Body JSON của một tin kêu cứu: vài trăm byte; gateway còn giới hạn chung 1 MiB
BODY_TOI_DA = 16 * 1024

TRUONG = ("lat", "lon", "reporter_phone", "description", "urgency", "people_count",
          "address_text", "reporter_name", "source")

# Di động Việt Nam 10 số: 03x, 05x, 07x, 08x, 09x (khớp domain phone_vn của CSDL: 0 + 9 số)
_SDT = re.compile(r"^0[35789][0-9]{8}$")
_KY_TU_PHAN_CACH = re.compile(r"[\s.\-()]")
_KY_TU_DIEU_KHIEN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_DETAIL_TRUNG = re.compile(r"incident_id=(?P<id>[0-9a-f-]{36}) distance_m=(?P<m>[0-9.]+) "
                           r"radius_m=(?P<r>[0-9.]+) window_minutes=(?P<w>[0-9]+)")


@dataclass(frozen=True)
class VungPhucVu:
    """Hình chữ nhật kinh độ/vĩ độ (WGS 84) mà hệ thống nhận tin kêu cứu."""

    kinh_do_min: float
    vi_do_min: float
    kinh_do_max: float
    vi_do_max: float

    def chua(self, lon: float, lat: float) -> bool:
        return self.kinh_do_min <= lon <= self.kinh_do_max and self.vi_do_min <= lat <= self.vi_do_max


# Mặc định: lãnh thổ Việt Nam kể cả Hoàng Sa, Trường Sa (đổi bằng KEU_CUU_VUNG_PHUC_VU)
VUNG_VIET_NAM = "102.1,6.0,117.9,23.4"


def vung_tu_chuoi(s: str) -> VungPhucVu:
    """"kinh_do_min,vi_do_min,kinh_do_max,vi_do_max" → VungPhucVu; sai dạng → ValueError."""
    so = [float(x) for x in s.split(",")]
    if len(so) != 4 or not all(math.isfinite(x) for x in so):
        raise ValueError("KEU_CUU_VUNG_PHUC_VU cần 4 số: kinh_do_min,vi_do_min,kinh_do_max,vi_do_max")
    v = VungPhucVu(*so)
    if not (-180 <= v.kinh_do_min < v.kinh_do_max <= 180 and -90 <= v.vi_do_min < v.vi_do_max <= 90):
        raise ValueError("KEU_CUU_VUNG_PHUC_VU: khoảng kinh độ/vĩ độ không hợp lệ")
    return v


@dataclass(frozen=True)
class LoiTruong:
    truong: str
    thong_bao: str


@dataclass(frozen=True)
class TinKeuCuu:
    lat: float
    lon: float
    reporter_phone: str
    description: str
    urgency: str
    people_count: int
    address_text: str | None
    reporter_name: str | None
    source: str


def chuan_hoa_sdt(s: str) -> str | None:
    """Bỏ dấu cách, chấm, gạch, ngoặc; +84/84 → 0. Trả None nếu không phải di động Việt Nam 10 số."""
    s = _KY_TU_PHAN_CACH.sub("", s)
    if s.startswith("+84"):
        s = "0" + s[3:]
    elif s.startswith("84") and len(s) == 11:
        s = "0" + s[2:]
    return s if _SDT.match(s) else None


def _so_thuc(v: Any) -> float | None:
    # bool là con của int trong Python: true/false không phải tọa độ
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    v = float(v)
    return v if math.isfinite(v) else None


def _chuoi(d: dict[str, Any], truong: str, toi_da: int, loi: list[LoiTruong], ten: str,
           bat_buoc: bool = False) -> str | None:
    v = d.get(truong)
    if v is None or (isinstance(v, str) and not v.strip()):
        if bat_buoc:
            loi.append(LoiTruong(truong, f"Thiếu {ten}."))
        return None
    if not isinstance(v, str):
        loi.append(LoiTruong(truong, f"{ten.capitalize()} phải là chuỗi ký tự."))
        return None
    v = v.strip()
    if _KY_TU_DIEU_KHIEN.search(v):
        loi.append(LoiTruong(truong, f"{ten.capitalize()} chứa ký tự điều khiển không hợp lệ."))
        return None
    if len(v) > toi_da:
        loi.append(LoiTruong(truong, f"{ten.capitalize()} dài tối đa {toi_da} ký tự (đang có {len(v)})."))
        return None
    return v


def kiem_tra(d: Any, vung: VungPhucVu) -> TinKeuCuu | list[LoiTruong]:
    """Kiểm body JSON của tin kêu cứu. Trả tin đã chuẩn hóa, hoặc danh sách lỗi theo trường (đủ mọi lỗi)."""
    if not isinstance(d, dict):
        return [LoiTruong("body", "Nội dung gửi lên phải là một đối tượng JSON.")]
    loi: list[LoiTruong] = []
    for k in d:
        if k not in TRUONG:
            loi.append(LoiTruong(str(k)[:50], "Trường không được hỗ trợ (kiểm tra lại tên trường)."))

    # Tọa độ: bắt buộc, là số, trong khoảng hợp lệ, trong vùng phục vụ
    lat, lon = d.get("lat"), d.get("lon")
    if lat is None or lon is None:
        for truong, v, ten in (("lat", lat, "vĩ độ"), ("lon", lon, "kinh độ")):
            if v is None:
                loi.append(LoiTruong(truong, f"Thiếu {ten}: tin kêu cứu bắt buộc có vị trí."))
    lat_f, lon_f = _so_thuc(lat), _so_thuc(lon)
    if lat is not None and lat_f is None:
        loi.append(LoiTruong("lat", "Vĩ độ phải là số."))
    elif lat_f is not None and not -90 <= lat_f <= 90:
        loi.append(LoiTruong("lat", "Vĩ độ phải trong khoảng -90 đến 90."))
        lat_f = None
    if lon is not None and lon_f is None:
        loi.append(LoiTruong("lon", "Kinh độ phải là số."))
    elif lon_f is not None and not -180 <= lon_f <= 180:
        loi.append(LoiTruong("lon", "Kinh độ phải trong khoảng -180 đến 180."))
        lon_f = None
    if lat_f is not None and lon_f is not None and not vung.chua(lon_f, lat_f):
        loi.append(LoiTruong("lat", "Vị trí nằm ngoài vùng phục vụ (kiểm tra có nhầm vĩ độ với kinh độ không)."))

    sdt = d.get("reporter_phone")
    sdt_chuan = None
    if sdt is None or (isinstance(sdt, str) and not sdt.strip()):
        loi.append(LoiTruong("reporter_phone", "Thiếu số điện thoại người báo."))
    elif not isinstance(sdt, str):
        loi.append(LoiTruong("reporter_phone", "Số điện thoại phải là chuỗi ký tự."))
    else:
        sdt_chuan = chuan_hoa_sdt(sdt)
        if sdt_chuan is None:
            loi.append(LoiTruong("reporter_phone",
                                 "Số điện thoại không đúng dạng di động Việt Nam (10 số, bắt đầu 03, 05, 07, 08, 09; "
                                 "chấp nhận +84)."))

    mo_ta = _chuoi(d, "description", MO_TA_TOI_DA, loi, "mô tả", bat_buoc=True)

    urgency = d.get("urgency", "trung_binh")
    if urgency not in URGENCY:
        loi.append(LoiTruong("urgency", f"Mức khẩn cấp phải là một trong: {', '.join(URGENCY)}."))

    so_nguoi = d.get("people_count", 1)
    if isinstance(so_nguoi, bool) or not isinstance(so_nguoi, int):
        loi.append(LoiTruong("people_count", "Số người phải là số nguyên."))
    elif not 1 <= so_nguoi <= SO_NGUOI_TOI_DA:
        loi.append(LoiTruong("people_count", f"Số người phải từ 1 đến {SO_NGUOI_TOI_DA}."))

    dia_chi = _chuoi(d, "address_text", DIA_CHI_TOI_DA, loi, "địa chỉ")
    ten = _chuoi(d, "reporter_name", TEN_TOI_DA, loi, "tên người báo")

    nguon = d.get("source", "app")
    if nguon not in NGUON:
        loi.append(LoiTruong("source", f"Nguồn tin phải là một trong: {', '.join(NGUON)}."))

    if loi:
        return loi
    assert lat_f is not None and lon_f is not None and sdt_chuan is not None and mo_ta is not None
    return TinKeuCuu(lat=lat_f, lon=lon_f, reporter_phone=sdt_chuan, description=mo_ta, urgency=urgency,
                     people_count=so_nguoi, address_text=dia_chi, reporter_name=ten, source=nguon)


def loi_422(loi: list[LoiTruong]) -> dict[str, Any]:
    return {"ma": "du_lieu_khong_hop_le",
            "thong_bao": "Chưa gửi được tin kêu cứu: kiểm tra lại các trường bên dưới.",
            "loi": [{"truong": x.truong, "thong_bao": x.thong_bao} for x in loi]}


def tin_trung_tu_detail(detail: str | None) -> dict[str, Any] | None:
    """DETAIL của trigger incidents_no_duplicate (0001) → thông tin tin đang mở; None nếu không đọc được."""
    m = _DETAIL_TRUNG.search(detail or "")
    if not m:
        return None
    return {"incident_id": m["id"], "khoang_cach_m": round(float(m["m"])),
            "ban_kinh_m": round(float(m["r"])), "trong_vong_phut": int(m["w"])}


def loi_409(trung: dict[str, Any]) -> dict[str, Any]:
    return {"ma": "tin_trung",
            "thong_bao": (f"Số điện thoại này đã báo một tin kêu cứu còn mở cách vị trí này khoảng "
                          f"{trung['khoang_cach_m']} m. Không tạo tin mới; hãy cập nhật tin đang mở "
                          f"(số người, mô tả) nếu tình hình thay đổi."),
            **trung}
