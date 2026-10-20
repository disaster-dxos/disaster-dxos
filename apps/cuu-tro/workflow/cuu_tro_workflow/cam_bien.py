# SPDX-License-Identifier: Apache-2.0
"""Logic thuần (không I/O) của luồng cảm biến (#30): topic/subject, phân tích bản tin, mức ngưỡng.

Quy ước topic MQTT:  cuu-tro/cam-bien/<ma_tram>/<dai_luong>   (vd cuu-tro/cam-bien/AL-MN-01/muc-nuoc)
NATS đổi "/" thành ".":  cuu-tro.cam-bien.<ma_tram>.<dai_luong>
Payload JSON:  {"ma_tram": "AL-MN-01", "gia_tri": 382.5, "don_vi": "cm",
                "thoi_diem": "2026-10-20T08:00:00+07:00"}
Sự kiện cảnh báo:  cuu-tro.canh-bao.cam-bien.<ma_tram>  (xem su_kien_canh_bao)
Giá trị kind/unit/level khớp CHECK của bảng cuu_tro.sensors / sensor_readings (db/migrations).
"""

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

APP = "cuu-tro"
TIEN_TO_CAM_BIEN = f"{APP}.cam-bien"
TIEN_TO_CANH_BAO = f"{APP}.canh-bao.cam-bien"

# Đại lượng trên topic → (kind, unit) của bảng sensors
DAI_LUONG: dict[str, tuple[str, str]] = {
    "muc-nuoc": ("muc_nuoc", "cm"),
    "luong-mua": ("luong_mua", "mm"),
    "gio": ("gio", "m/s"),
}
KIND_SANG_DAI_LUONG = {kind: dl for dl, (kind, _) in DAI_LUONG.items()}

# Cùng biểu thức với CHECK sensors.code; không có "." hay "/" nên không vỡ subject/topic
MA_TRAM_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{1,31}$")
KICH_THUOC_TOI_DA = 4096
# numeric(10, 2) chứa được tới 99 999 999.99; khoảng hợp lý cho cả mực nước (cm), mưa (mm), gió (m/s)
GIA_TRI_MIN = Decimal("-1000")
GIA_TRI_MAX = Decimal("100000")
LECH_TUONG_LAI = timedelta(minutes=5)  # đồng hồ thiết bị nhanh hơn lõi tối đa
QUA_CU = timedelta(days=7)  # thiết bị mất mạng gửi bù tối đa 7 ngày (bằng max_age của stream)

BINH_THUONG, CANH_BAO, NGUY_HIEM = "binh_thuong", "canh_bao", "nguy_hiem"
THU_TU_MUC = {BINH_THUONG: 0, CANH_BAO: 1, NGUY_HIEM: 2}


class BanTinKhongHopLe(ValueError):
    """Bản tin sai định dạng hoặc không khớp trạm: bỏ, không giao lại."""


@dataclass(frozen=True)
class BanTin:
    ma_tram: str
    kind: str
    gia_tri: Decimal
    don_vi: str
    thoi_diem: datetime


def topic_mqtt(ma_tram: str, kind: str) -> str:
    return f"{APP}/cam-bien/{ma_tram}/{KIND_SANG_DAI_LUONG[kind]}"


def subject_canh_bao(ma_tram: str) -> str:
    return f"{TIEN_TO_CANH_BAO}.{ma_tram}"


def tach_subject(subject: str) -> tuple[str, str]:
    """cuu-tro.cam-bien.<ma_tram>.<dai_luong> → (ma_tram, kind)."""
    tien_to = TIEN_TO_CAM_BIEN + "."
    if not subject.startswith(tien_to):
        raise BanTinKhongHopLe(f"subject không thuộc luồng cảm biến: {subject}")
    phan = subject[len(tien_to):].split(".")
    if len(phan) != 2:
        raise BanTinKhongHopLe(f"subject phải có dạng {tien_to}<ma_tram>.<dai_luong>: {subject}")
    ma_tram, dai_luong = phan
    if not MA_TRAM_RE.match(ma_tram):
        raise BanTinKhongHopLe(f"mã trạm không hợp lệ: {ma_tram}")
    if dai_luong not in DAI_LUONG:
        raise BanTinKhongHopLe(f"đại lượng không hỗ trợ: {dai_luong}")
    return ma_tram, DAI_LUONG[dai_luong][0]


def _gia_tri(v: object) -> Decimal:
    # bool là con của int trong Python: true/false không phải số đo
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise BanTinKhongHopLe("gia_tri phải là số")
    if isinstance(v, float) and not math.isfinite(v):
        raise BanTinKhongHopLe("gia_tri phải là số hữu hạn")
    d = Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if not GIA_TRI_MIN <= d <= GIA_TRI_MAX:
        raise BanTinKhongHopLe(f"gia_tri ngoài khoảng [{GIA_TRI_MIN}, {GIA_TRI_MAX}]: {d}")
    return d


def _thoi_diem(v: object, bay_gio: datetime) -> datetime:
    if not isinstance(v, str):
        raise BanTinKhongHopLe("thoi_diem phải là chuỗi ISO 8601")
    try:
        t = datetime.fromisoformat(v)
    except ValueError as e:
        raise BanTinKhongHopLe(f"thoi_diem không phải ISO 8601: {v}") from e
    if t.tzinfo is None:
        raise BanTinKhongHopLe("thoi_diem phải có múi giờ (vd +07:00 hoặc Z)")
    if t > bay_gio + LECH_TUONG_LAI:
        raise BanTinKhongHopLe(f"thoi_diem ở tương lai: {v}")
    if t < bay_gio - QUA_CU:
        raise BanTinKhongHopLe(f"thoi_diem quá cũ: {v}")
    return t


def phan_tich(subject: str, du_lieu: bytes, bay_gio: datetime) -> BanTin:
    """Kiểm subject + payload JSON; trả BanTin hoặc báo BanTinKhongHopLe. `bay_gio` có múi giờ."""
    ma_tram, kind = tach_subject(subject)
    if len(du_lieu) > KICH_THUOC_TOI_DA:
        raise BanTinKhongHopLe(f"bản tin lớn hơn {KICH_THUOC_TOI_DA} byte")
    try:
        p = json.loads(du_lieu)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise BanTinKhongHopLe("payload không phải JSON") from e
    if not isinstance(p, dict):
        raise BanTinKhongHopLe("payload phải là object JSON")
    if p.get("ma_tram") != ma_tram:
        raise BanTinKhongHopLe(f"ma_tram trong payload ({p.get('ma_tram')!r}) khác topic ({ma_tram})")
    don_vi = DAI_LUONG[KIND_SANG_DAI_LUONG[kind]][1]
    if p.get("don_vi") != don_vi:
        raise BanTinKhongHopLe(f"don_vi phải là {don_vi!r}, nhận {p.get('don_vi')!r}")
    return BanTin(
        ma_tram=ma_tram,
        kind=kind,
        gia_tri=_gia_tri(p.get("gia_tri")),
        don_vi=don_vi,
        thoi_diem=_thoi_diem(p.get("thoi_diem"), bay_gio),
    )


def kiem_tra_khop_tram(bt: BanTin, kind: str, unit: str, active: bool) -> None:
    """Bản tin phải khớp loại/đơn vị của trạm trong CSDL; trạm đã tắt thì bỏ bản tin."""
    if not active:
        raise BanTinKhongHopLe(f"trạm {bt.ma_tram} đang tắt")
    if (bt.kind, bt.don_vi) != (kind, unit):
        raise BanTinKhongHopLe(f"trạm {bt.ma_tram} đo {kind} ({unit}), bản tin là {bt.kind} ({bt.don_vi})")


def muc_canh_bao(gia_tri: Decimal, nguong_canh_bao: Decimal | None, nguong_nguy_hiem: Decimal | None) -> str:
    """So với ngưỡng của trạm (>= là vượt). Ngưỡng NULL = không cảnh báo ở mức đó."""
    if nguong_nguy_hiem is not None and gia_tri >= nguong_nguy_hiem:
        return NGUY_HIEM
    if nguong_canh_bao is not None and gia_tri >= nguong_canh_bao:
        return CANH_BAO
    return BINH_THUONG


def can_phat_canh_bao(muc_truoc: str | None, muc_moi: str, la_moi_nhat: bool) -> bool:
    """Chỉ phát khi mức TĂNG lên canh_bao/nguy_hiem ở lần đo mới nhất.

    Không phát lại khi nước vẫn ở trên ngưỡng (tránh dội cảnh báo mỗi chu kỳ đo), không phát cho
    bản tin gửi bù cũ hơn lần đo cuối. Chưa có lần đo trước (muc_truoc None) coi như bình thường.
    """
    if not la_moi_nhat or muc_moi == BINH_THUONG:
        return False
    return THU_TU_MUC[muc_moi] > THU_TU_MUC[muc_truoc or BINH_THUONG]


def su_kien_canh_bao(
    bt: BanTin,
    ten_tram: str,
    muc_truoc: str | None,
    muc_moi: str,
    nguong_canh_bao: Decimal | None,
    nguong_nguy_hiem: Decimal | None,
) -> dict:
    """Payload JSON của sự kiện cảnh báo (khung cho agent cảnh báo tuần 4–5)."""
    nguong = nguong_nguy_hiem if muc_moi == NGUY_HIEM else nguong_canh_bao
    return {
        "loai": "vuot_nguong",
        "ma_tram": bt.ma_tram,
        "ten_tram": ten_tram,
        "dai_luong": bt.kind,
        "muc": muc_moi,
        "muc_truoc": muc_truoc or BINH_THUONG,
        "gia_tri": float(bt.gia_tri),
        "nguong": None if nguong is None else float(nguong),
        "don_vi": bt.don_vi,
        "thoi_diem": bt.thoi_diem.isoformat(),
    }


def ma_su_kien(bt: BanTin, muc: str) -> str:
    """Nats-Msg-Id: JetStream bỏ bản trùng trong cửa sổ chống trùng khi consumer xử lý lại bản tin."""
    # Quy về UTC: cùng một thời điểm viết với múi giờ khác nhau vẫn cùng mã
    return f"{bt.ma_tram}:{bt.thoi_diem.astimezone(timezone.utc).isoformat()}:{muc}"
