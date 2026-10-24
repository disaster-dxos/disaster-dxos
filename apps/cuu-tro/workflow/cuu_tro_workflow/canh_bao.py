# SPDX-License-Identifier: Apache-2.0
"""Thông báo cảnh báo vượt ngưỡng (#87): logic thuần, không I/O (có pytest).

Luồng: consumer ghi-csdl (#30) phát sự kiện lên cuu-tro.canh-bao.cam-bien.<ma_tram> khi mức TĂNG
(vuot_nguong) và khi về binh_thuong sau một đợt (ve_duoi_nguong), mỗi sự kiện mang mã đợt "dot" (lần
đo đầu tiên trên ngưỡng). Bộ khởi chạy trong worker (canh_bao_khoi_chay.py) signal-with-start workflow
CanhBaoVuotNguong id canh-bao-<ma_tram>-<dot>: một đợt = một workflow. Workflow báo đúng 1 lần cho mỗi
bước: canh_bao, nguy_hiem (lên cấp), ve_duoi_nguong (kết thúc đợt). Đo lại vẫn trên ngưỡng, xuống từ
nguy_hiem về canh_bao rồi lên lại, sự kiện giao lại: không báo thêm (quyet_dinh).
Activity gui_canh_bao (canh_bao_gui.py) ghi hộp thư nội bộ (bảng sensor_alert_notifications), đẩy lên web điều
phối (NATS → Centrifugo) và, nếu CANH_BAO_KENH=telegram, gửi Telegram Bot API.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from . import cam_bien

LOAI_VUOT, LOAI_VE = "vuot_nguong", "ve_duoi_nguong"
BUOC_CANH_BAO, BUOC_NGUY_HIEM, BUOC_VE = cam_bien.CANH_BAO, cam_bien.NGUY_HIEM, LOAI_VE
BUOC = (BUOC_CANH_BAO, BUOC_NGUY_HIEM, BUOC_VE)
KENH_GIA_LAP, KENH_TELEGRAM = "gia-lap", "telegram"
KENH = (KENH_GIA_LAP, KENH_TELEGRAM)
SIGNAL_SU_KIEN = "su_kien"
# TrangThaiCanhBao.ket_thuc: ve_duoi_nguong | het_han (không có sự kiện về dưới ngưỡng) | khong_bao
KET_THUC_HET_HAN, KET_THUC_KHONG_BAO = "het_han", "khong_bao"
TIEN_TO_WORKFLOW = "canh-bao-"
# Sự kiện đẩy lên web điều phối (stream CUU_TRO_DIEU_PHOI, cầu nối thong_bao_cau_noi.py → Centrifugo)
TIEN_TO_WEB = f"{cam_bien.APP}.dieu-phoi.canh-bao."
GIO_VN = timezone(timedelta(hours=7))
TEN_MUC = {cam_bien.CANH_BAO: "Cảnh báo", cam_bien.NGUY_HIEM: "Nguy hiểm", cam_bien.BINH_THUONG: "Bình thường"}
TEN_DAI_LUONG = {"muc_nuoc": "Mực nước", "luong_mua": "Lượng mưa", "gio": "Tốc độ gió"}


class SuKienKhongHopLe(ValueError):
    """Sự kiện cảnh báo sai định dạng: bỏ (term), giao lại cũng không khác."""


@dataclass
class SuKien:
    """Sự kiện cảnh báo đã kiểm (payload JSON của cam_bien.su_kien_canh_bao / su_kien_ve_duoi_nguong)."""

    loai: str
    ma_tram: str
    ten_tram: str
    dai_luong: str
    muc: str
    muc_truoc: str
    gia_tri: float
    nguong: float | None
    don_vi: str
    thoi_diem: str
    dot: str


@dataclass
class ThamSoCanhBao:
    ma_tram: str
    dot: str
    # Đợt không có sự kiện về dưới ngưỡng (trạm mất tín hiệu): workflow tự kết thúc sau hạn này
    han_giay: int = 7 * 24 * 3600


@dataclass
class YeuCauGui:
    """Đầu vào activity gui_canh_bao: một bước thông báo của một đợt."""

    buoc: str
    su_kien: SuKien
    # Bước đã báo trước đó trong đợt (vd canh_bao khi lên nguy_hiem), để ghi "trước: …"
    da_bao: list[str] = field(default_factory=list)


@dataclass
class TrangThaiCanhBao:
    ma_tram: str
    dot: str
    da_bao: list[str]
    ket_thuc: str | None = None


def _so(v: object, ten: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise SuKienKhongHopLe(f"{ten} phải là số")
    return float(v)


def doc_su_kien(subject: str, d: object) -> SuKien:
    """Kiểm payload sự kiện trên subject cuu-tro.canh-bao.cam-bien.<ma_tram>."""
    tien_to = cam_bien.TIEN_TO_CANH_BAO + "."
    if not subject.startswith(tien_to):
        raise SuKienKhongHopLe(f"subject không phải cảnh báo cảm biến: {subject}")
    ma = subject[len(tien_to):]
    if not cam_bien.MA_TRAM_RE.match(ma):
        raise SuKienKhongHopLe(f"mã trạm sai: {ma!r}")
    if not isinstance(d, dict):
        raise SuKienKhongHopLe("payload phải là object JSON")
    loai, muc = d.get("loai"), d.get("muc")
    if loai == LOAI_VUOT and muc in (cam_bien.CANH_BAO, cam_bien.NGUY_HIEM):
        pass
    elif loai == LOAI_VE and muc == cam_bien.BINH_THUONG:
        pass
    else:
        raise SuKienKhongHopLe(f"loai/muc không hợp lệ: {loai!r}/{muc!r}")
    if d.get("ma_tram") != ma:
        raise SuKienKhongHopLe("ma_tram trong payload khác subject")
    for k in ("thoi_diem", "dot"):
        try:
            t = datetime.fromisoformat(str(d.get(k, "")).replace("Z", "+00:00"))
        except ValueError as e:
            raise SuKienKhongHopLe(f"{k} không phải ISO 8601") from e
        if t.tzinfo is None:
            raise SuKienKhongHopLe(f"{k} phải có múi giờ")
    nguong = d.get("nguong")
    return SuKien(
        loai=loai, ma_tram=ma, ten_tram=str(d.get("ten_tram") or ma)[:200],
        dai_luong=str(d.get("dai_luong") or "muc_nuoc"), muc=muc,
        muc_truoc=str(d.get("muc_truoc") or cam_bien.BINH_THUONG),
        gia_tri=_so(d.get("gia_tri"), "gia_tri"), nguong=None if nguong is None else _so(nguong, "nguong"),
        don_vi=str(d.get("don_vi") or ""), thoi_diem=str(d["thoi_diem"]),
        dot=cam_bien.chuoi_dot(datetime.fromisoformat(str(d["dot"]).replace("Z", "+00:00"))),
    )


def workflow_id(ma_tram: str, dot: str) -> str:
    """Một đợt vượt ngưỡng của một trạm = một workflow (Temporal từ chối chạy lại id đã xong)."""
    return f"{TIEN_TO_WORKFLOW}{ma_tram}-{dot}"


def quyet_dinh(sk: SuKien, da_bao: list[str]) -> str | None:
    """Bước cần báo cho sự kiện `sk`, hoặc None (đã báo cấp này/cao hơn, hay về dưới ngưỡng khi chưa báo)."""
    if sk.loai == LOAI_VE:
        return BUOC_VE if da_bao and BUOC_VE not in da_bao else None
    if BUOC_VE in da_bao:
        return None  # đợt đã kết thúc
    cap_da_bao = max((cam_bien.THU_TU_MUC[b] for b in da_bao if b in cam_bien.THU_TU_MUC), default=0)
    return sk.muc if cam_bien.THU_TU_MUC[sk.muc] > cap_da_bao else None


def _so_vn(v: float | None) -> str:
    if v is None:
        return "?"
    try:
        d = Decimal(str(v)).normalize()
    except InvalidOperation:
        return str(v)
    s = format(d, "f")
    return s.replace(".", ",")


def _gio_vn(iso: str) -> str:
    t = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(GIO_VN)
    return t.strftime("%H:%M %d/%m/%Y") + " (giờ Việt Nam)"


def lien_ket_ban_do(kinh_do: float | None, vi_do: float | None) -> str | None:
    """Liên kết bản đồ công khai (OpenStreetMap) tới vị trí trạm, mở được ngoài web điều phối."""
    if kinh_do is None or vi_do is None:
        return None
    q = urlencode({"mlat": f"{vi_do:.5f}", "mlon": f"{kinh_do:.5f}"})
    return f"https://www.openstreetmap.org/?{q}#map=14/{vi_do:.5f}/{kinh_do:.5f}"


def noi_dung(yc: YeuCauGui, kinh_do: float | None, vi_do: float | None, web_url: str) -> str:
    """Nội dung tin tiếng Việt (văn bản thuần, gửi được cả Telegram lẫn hộp thư nội bộ)."""
    sk = yc.su_kien
    dl = TEN_DAI_LUONG.get(sk.dai_luong, sk.dai_luong)
    if yc.buoc == BUOC_VE:
        dau = f"🟢 ĐÃ VỀ DƯỚI NGƯỠNG: {sk.ten_tram} ({sk.ma_tram})"
        do = f"{dl}: {_so_vn(sk.gia_tri)} {sk.don_vi} (dưới ngưỡng cảnh báo {_so_vn(sk.nguong)} {sk.don_vi})"
        cap = f"Cấp báo động: {TEN_MUC[cam_bien.BINH_THUONG]} (cao nhất trong đợt: {TEN_MUC.get(_cao_nhat(yc.da_bao), '?')})"
    else:
        bieu_tuong = "🔴" if yc.buoc == BUOC_NGUY_HIEM else "🟠"
        dau = f"{bieu_tuong} {TEN_MUC[yc.buoc].upper()}: {sk.ten_tram} ({sk.ma_tram})"
        do = f"{dl}: {_so_vn(sk.gia_tri)} {sk.don_vi} (ngưỡng {TEN_MUC[yc.buoc].lower()} {_so_vn(sk.nguong)} {sk.don_vi})"
        truoc = _cao_nhat(yc.da_bao)
        cap = f"Cấp báo động: {TEN_MUC[yc.buoc]}" + (f" (trước: {TEN_MUC[truoc]})" if truoc else "")
    dong = [dau, do, cap, f"Thời điểm đo: {_gio_vn(sk.thoi_diem)}"]
    ban_do = lien_ket_ban_do(kinh_do, vi_do)
    if ban_do:
        dong.append(f"Bản đồ: {ban_do}")
    if web_url:
        dong.append(f"Web điều phối: {web_url.rstrip('/')}/")
    return "\n".join(dong)


def _cao_nhat(da_bao: list[str]) -> str | None:
    cap = [b for b in da_bao if b in cam_bien.THU_TU_MUC]
    return max(cap, key=lambda b: cam_bien.THU_TU_MUC[b]) if cap else None


def ma_tin_web(sk: SuKien, buoc: str) -> str:
    """Nats-Msg-Id của sự kiện đẩy lên web: activity chạy lại không tạo thông báo trùng."""
    return f"canh-bao:{sk.ma_tram}:{sk.dot}:{buoc}"


def su_kien_web(sk: SuKien, buoc: str) -> dict:
    """Payload sự kiện cho web điều phối (không có dữ liệu cá nhân; cầu nối lọc theo danh sách trắng)."""
    return {
        "ma_tram": sk.ma_tram, "ten_tram": sk.ten_tram, "dai_luong": sk.dai_luong, "buoc": buoc,
        "muc": sk.muc, "muc_truoc": sk.muc_truoc, "gia_tri": sk.gia_tri, "nguong": sk.nguong,
        "don_vi": sk.don_vi, "thoi_diem": sk.thoi_diem, "dot": sk.dot,
    }


def loi_telegram(ma_http: int, than: dict | None) -> tuple[bool, float | None]:
    """(thử lại?, giây chờ) cho phản hồi lỗi của Telegram Bot API. 429 có retry_after; 5xx thử lại;
    400/401/403/404 (token sai, chat không có, bot bị chặn) gửi lại cũng vậy: không thử lại."""
    if ma_http == 429:
        cho = ((than or {}).get("parameters") or {}).get("retry_after")
        return True, float(cho) if isinstance(cho, (int, float)) else None
    if ma_http >= 500:
        return True, None
    return False, None
