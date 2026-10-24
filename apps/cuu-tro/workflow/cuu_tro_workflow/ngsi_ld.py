# SPDX-License-Identifier: Apache-2.0
"""Logic thuần (không I/O) của bản sao số trạm đo trên Scorpio NGSI-LD (#85).

Một trạm (bảng cuu_tro.sensors) = một thực thể NGSI-LD, id lấy từ sensors.ngsi_ld_id (trống thì
urn:ngsi-ld:<Type>:<mã trạm>). Mô hình và @context: apps/cuu-tro/ngsi-ld/ (README.md, context.jsonld).

  muc_nuoc  → WaterLevelStation, thuộc tính đo waterLevel   (cm,  unitCode CMT)
  luong_mua → RainGauge,         thuộc tính đo precipitation (mm,  unitCode MMT)
  gio       → WindStation,       thuộc tính đo windSpeed     (m/s, unitCode MTS)

Mỗi lần ghi gửi CẢ thực thể (upsert thay thế): name, stationCode, location, thuộc tính đo (có
observedAt), alertLevel, ngưỡng hiện tại. Bản tin cũ hơn lần đo đang có trên Scorpio thì không ghi
(can_ghi), nên giao lại / gửi bù không làm thực thể lùi về giá trị cũ.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from . import cam_bien

LOAI: dict[str, tuple[str, str, str]] = {
    # kind → (type NGSI-LD, thuộc tính đo, unitCode UN/CEFACT)
    "muc_nuoc": ("WaterLevelStation", "waterLevel", "CMT"),
    "luong_mua": ("RainGauge", "precipitation", "MMT"),
    "gio": ("WindStation", "windSpeed", "MTS"),
}


class LoiScorpio(Exception):
    """Scorpio trả lỗi. tam_thoi=True: thử lại sau (mạng, 5xx, 429); False: request sai, bỏ bản tin."""

    def __init__(self, thong_diep: str, tam_thoi: bool):
        super().__init__(thong_diep)
        self.tam_thoi = tam_thoi


@dataclass(frozen=True)
class Tram:
    """Thông tin trạm đọc từ cuu_tro.sensors (role cuu_tro_app, migration 0009)."""

    ma: str
    ten: str
    kind: str
    unit: str
    kinh_do: float
    vi_do: float
    nguong_canh_bao: Decimal | None
    nguong_nguy_hiem: Decimal | None
    active: bool
    ngsi_ld_id: str | None


def doc_context(duong_dan: str) -> dict:
    """Đọc context.jsonld → object @context (gửi kèm từng thực thể, Scorpio không phải tải về)."""
    with open(duong_dan, encoding="utf-8") as f:
        ctx = json.load(f)["@context"]
    if not isinstance(ctx, dict):
        raise ValueError("@context trong context.jsonld phải là object")
    return ctx


def iri(ctx: dict, term: str) -> str:
    """Term → IRI đầy đủ theo context (để đọc thực thể Scorpio trả ở dạng mở rộng, không có context)."""
    v = ctx[term]
    tien_to, _, duoi = v.partition(":")
    if duoi and not duoi.startswith("//") and tien_to in ctx and isinstance(ctx[tien_to], str):
        return ctx[tien_to] + duoi
    return v


def id_thuc_the(tram: Tram) -> str:
    return tram.ngsi_ld_id or f"urn:ngsi-ld:{LOAI[tram.kind][0]}:{tram.ma}"


def _thoi_diem(t: datetime) -> str:
    # NGSI-LD dùng DateTime UTC dạng ISO 8601; quy về UTC để so sánh chuỗi cùng một kiểu
    return t.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def thuc_the(tram: Tram, bt: cam_bien.BanTin, ctx: dict) -> dict:
    """Thực thể NGSI-LD (dạng chuẩn hóa, có @context nội tuyến) của trạm sau bản tin `bt`."""
    if bt.ma_tram != tram.ma:
        raise ValueError(f"bản tin của {bt.ma_tram}, không phải trạm {tram.ma}")
    kieu, thuoc_tinh, unit_code = LOAI[tram.kind]
    luc = _thoi_diem(bt.thoi_diem)
    e: dict = {
        "id": id_thuc_the(tram),
        "type": kieu,
        "name": {"type": "Property", "value": tram.ten},
        "stationCode": {"type": "Property", "value": tram.ma},
        "location": {"type": "GeoProperty", "value": {"type": "Point", "coordinates": [tram.kinh_do, tram.vi_do]}},
        thuoc_tinh: {"type": "Property", "value": float(bt.gia_tri), "unitCode": unit_code, "observedAt": luc},
        "alertLevel": {
            "type": "Property",
            "value": cam_bien.muc_canh_bao(bt.gia_tri, tram.nguong_canh_bao, tram.nguong_nguy_hiem),
            "observedAt": luc,
        },
    }
    if tram.nguong_canh_bao is not None:
        e["warningThreshold"] = {"type": "Property", "value": float(tram.nguong_canh_bao), "unitCode": unit_code}
    if tram.nguong_nguy_hiem is not None:
        e["dangerThreshold"] = {"type": "Property", "value": float(tram.nguong_nguy_hiem), "unitCode": unit_code}
    e["@context"] = [ctx]
    return e


def thoi_diem_hien_tai(thuc_the_scorpio: dict | None, kind: str, ctx: dict) -> datetime | None:
    """observedAt của thuộc tính đo trên thực thể Scorpio đang có (GET không kèm context → khóa là IRI)."""
    if not thuc_the_scorpio:
        return None
    thuoc_tinh = LOAI[kind][1]
    tt = thuc_the_scorpio.get(thuoc_tinh) or thuc_the_scorpio.get(iri(ctx, thuoc_tinh))
    if isinstance(tt, list):  # nhiều instance (datasetId): lấy cái mới nhất
        tt = max(tt, key=lambda x: x.get("observedAt", ""), default=None)
    if not isinstance(tt, dict) or not isinstance(tt.get("observedAt"), str):
        return None
    try:
        return datetime.fromisoformat(tt["observedAt"].replace("Z", "+00:00"))
    except ValueError:
        return None


def can_ghi(bt: cam_bien.BanTin, hien_tai: datetime | None) -> bool:
    """Ghi khi Scorpio chưa có lần đo nào hoặc bản tin không cũ hơn (bằng = ghi lại, kết quả như cũ)."""
    return hien_tai is None or bt.thoi_diem >= hien_tai


# Lỗi do chính dữ liệu gửi đi (gửi lại vẫn sai): bỏ bản tin. Mọi lỗi khác thử lại, vì Scorpio báo cả lỗi
# phía nó bằng 400 (vd hết kết nối PostgreSQL: 400 InvalidRequest "too many connections"); thực thể do
# ngsi_ld.thuc_the dựng nên request sai thật hiếm, và giao lại tối đa max_deliver lần rồi JetStream bỏ.
LOI_DU_LIEU = "https://uri.etsi.org/ngsi-ld/errors/BadRequestData"
MA_LOI_DU_LIEU = (413, 415, 422)


def _vinh_vien(ma_http: object, kieu: object) -> bool:
    return ma_http in MA_LOI_DU_LIEU or (ma_http == 400 and kieu == LOI_DU_LIEU)


def phan_loai_loi(ma_http: int, than: str = "") -> LoiScorpio:
    """Mã HTTP lỗi của Scorpio (+ body ProblemDetails) → LoiScorpio tạm thời (thử lại) hoặc không (bỏ bản tin)."""
    try:
        kieu = json.loads(than).get("type") if than else None
    except (ValueError, AttributeError):
        kieu = None
    return LoiScorpio(f"Scorpio trả HTTP {ma_http}: {than[:300]}", not _vinh_vien(ma_http, kieu))


def kiem_ket_qua_upsert(ma_http: int, than: str) -> None:
    """201 (tạo) / 204 (cập nhật) là xong. 207: batch có lỗi theo thực thể ({"errors": [{"entityId",
    "error": ProblemDetails}]}); lỗi dữ liệu (BadRequestData) → bỏ, lỗi khác → thử lại."""
    if ma_http in (200, 201, 204):
        return
    if ma_http == 207:
        try:
            loi = json.loads(than).get("errors") or []
        except (ValueError, AttributeError):
            loi = []
        if not loi:
            return
        chi_tiet = [(e.get("error") or e.get("ProblemDetails") or {}) for e in loi if isinstance(e, dict)]
        vinh_vien = bool(chi_tiet) and all(_vinh_vien(c.get("status"), c.get("type")) for c in chi_tiet)
        raise LoiScorpio(f"Scorpio upsert lỗi một phần: {than[:300]}", not vinh_vien)
    raise phan_loai_loi(ma_http, than)


def tre_thu_lai(lan_giao: int) -> float:
    """Giây chờ trước khi JetStream giao lại: 2, 4, 8 … tối đa 60 (Scorpio khởi động lại, mạng chập chờn)."""
    return float(min(60, 2 ** max(1, lan_giao)))
