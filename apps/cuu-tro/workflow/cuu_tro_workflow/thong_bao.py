# SPDX-License-Identifier: Apache-2.0
"""Thông báo realtime cho web điều phối (#68): logic thuần, không I/O (có pytest).

Luồng: sự kiện JetStream → cầu nối (thong_bao_cau_noi.py) → Centrifugo OSS của lõi (HTTP API, mạng
nội bộ) → kênh "dieu-phoi" → web điều phối (WebSocket qua APISIX /realtime/websocket).

Sự kiện nguồn (đều KHÔNG có SĐT hay tên người báo; cầu nối chỉ chép các trường trong danh sách trắng):
  cuu-tro.dieu-phoi.can-xu-ly.<incident_id>   workflow cần điều phối xử lý (#67, activity bao_dieu_phoi)
  cuu-tro.dieu-phoi.tin-moi.<incident_id>     tin kêu cứu mới vào hàng đợi phân công (khoi_chay.py)
  cuu-tro.dieu-phoi.canh-bao.<ma_tram>        thông báo cảnh báo trạm đo đã gửi (#87, workflow CanhBaoVuotNguong:
                                              đúng 1 lần mỗi bước canh_bao / nguy_hiem / ve_duoi_nguong của một đợt)
  cuu-tro.canh-bao.cam-bien.<ma_tram>         sự kiện thô của trạm đo (#30). Từ #87 cầu nối không còn consumer trên
                                              stream này (realtime-canh-bao); web nhận bản đã khử trùng lặp ở trên

Kết nối Centrifugo dùng token RIÊNG do cuu-tro-api ký (HS256, khóa trong OpenBao), không dùng thẳng
JWT Keycloak: API kiểm JWT Keycloak + vai trò rồi cấp token ngắn hạn chỉ mang `sub` và danh sách kênh
server-side (claim `channels`). Client không tự đăng ký được kênh nào (Centrifugo mặc định cấm).
"""

import json
import re
import time
from dataclasses import dataclass
from typing import Any

import jwt

APP = "cuu-tro"
KENH_DIEU_PHOI = "dieu-phoi"
# Vai trò được nhận thông báo điều phối. "quan-tri" để dành, realm hiện chưa có vai trò này
VAI_TRO_NHAN = ("dieu-phoi", "quan-tri")
# Khớp CENTRIFUGO_CLIENT_TOKEN_ISSUER/AUDIENCE trong docker-compose.yml (issuer = <DXOS_APP>-api)
TOKEN_ISSUER = f"{APP}-api"
TOKEN_AUDIENCE = "centrifugo"

TIEN_TO_CAN_XU_LY = f"{APP}.dieu-phoi.can-xu-ly."
TIEN_TO_TIN_MOI = f"{APP}.dieu-phoi.tin-moi."
TIEN_TO_CANH_BAO = f"{APP}.canh-bao.cam-bien."
TIEN_TO_CANH_BAO_DA_GUI = f"{APP}.dieu-phoi.canh-bao."

LOAI_CAN_XU_LY, LOAI_TIN_MOI, LOAI_CANH_BAO = "can_xu_ly", "tin_moi", "canh_bao"

# Danh sách trắng trường được đưa ra web theo loại sự kiện
_TRUONG = {
    LOAI_CAN_XU_LY: ("incident_id", "ly_do", "urgency", "so_lan_giao", "mo_ta", "luc"),
    LOAI_TIN_MOI: ("incident_id", "urgency", "luc"),
    LOAI_CANH_BAO: ("ma_tram", "ten_tram", "dai_luong", "buoc", "muc", "muc_truoc", "gia_tri", "nguong", "don_vi",
                    "thoi_diem", "dot"),
}
_MAX_CHUOI = 300
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_MA_TRAM = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
# Dãy số dạng SĐT/CCCD (giống luật của sổ cái, #28): chuỗi tự do có thứ này thì không đưa ra web
_SO_DINH_DANH = re.compile(r"(^|[^0-9])0[0-9]{8,}")


class SuKienKhongHopLe(ValueError):
    """Bản tin sai định dạng: cầu nối bỏ hẳn (term), giao lại cũng không khác."""


@dataclass(frozen=True)
class ThongBao:
    kenh: str
    du_lieu: dict[str, Any]
    # idempotency_key của Centrifugo: giao lại cùng bản tin không tạo thông báo trùng
    khoa: str


def tin_moi(incident_id: str, urgency: str, luc: str) -> tuple[str, bytes, str]:
    """(subject, payload, Nats-Msg-Id) của sự kiện tin mới mà bộ khởi chạy phát (khoi_chay.py)."""
    du_lieu = {"incident_id": incident_id, "urgency": urgency, "luc": luc}
    return f"{TIEN_TO_TIN_MOI}{incident_id}", json.dumps(du_lieu).encode(), f"tin-moi:{incident_id}"


def _loai(subject: str) -> tuple[str, str]:
    for tien_to, loai in ((TIEN_TO_CAN_XU_LY, LOAI_CAN_XU_LY), (TIEN_TO_TIN_MOI, LOAI_TIN_MOI),
                          (TIEN_TO_CANH_BAO_DA_GUI, LOAI_CANH_BAO), (TIEN_TO_CANH_BAO, LOAI_CANH_BAO)):
        if subject.startswith(tien_to):
            return loai, subject[len(tien_to):]
    raise SuKienKhongHopLe(f"subject không thuộc thông báo điều phối: {subject}")


def _gia_tri_sach(v: Any) -> Any:
    if v is None or isinstance(v, (bool, int, float)):
        return v
    if isinstance(v, str):
        if _SO_DINH_DANH.search(v):
            return None
        return v[:_MAX_CHUOI]
    return None  # không đưa object/mảng lồng nhau ra web


def chuyen_su_kien(subject: str, du_lieu: bytes, msg_id: str | None, stream: str, seq: int) -> ThongBao:
    """Bản tin JetStream → thông báo cho kênh dieu-phoi. Lỗi định dạng → SuKienKhongHopLe."""
    loai, duoi = _loai(subject)
    if loai == LOAI_CANH_BAO:
        if not _MA_TRAM.match(duoi):
            raise SuKienKhongHopLe(f"mã trạm sai: {duoi!r}")
    elif not _UUID.match(duoi):
        raise SuKienKhongHopLe(f"incident_id trên subject sai: {duoi!r}")
    try:
        goc = json.loads(du_lieu)
    except (ValueError, UnicodeDecodeError) as e:
        raise SuKienKhongHopLe(f"payload không phải JSON: {e}") from e
    if not isinstance(goc, dict):
        raise SuKienKhongHopLe("payload phải là object JSON")
    if loai != LOAI_CANH_BAO and goc.get("incident_id") not in (None, duoi):
        raise SuKienKhongHopLe("incident_id trong payload khác subject")
    sach = {k: _gia_tri_sach(goc[k]) for k in _TRUONG[loai] if k in goc}
    if loai == LOAI_CANH_BAO:
        sach["ma_tram"] = duoi
    else:
        sach["incident_id"] = duoi
    khoa = f"{stream}:{msg_id}" if msg_id else f"{stream}:{seq}"
    return ThongBao(kenh=KENH_DIEU_PHOI, du_lieu={"loai": loai, "id": khoa, **sach}, khoa=khoa)


def lenh_publish(tb: ThongBao) -> dict[str, Any]:
    """Body POST /api/publish của Centrifugo."""
    return {"channel": tb.kenh, "data": tb.du_lieu, "idempotency_key": tb.khoa}


def kenh_cua(vai_tro: frozenset[str] | set[str]) -> list[str]:
    """Kênh server-side người dùng được nhận theo vai trò (rỗng = không được kết nối)."""
    return [KENH_DIEU_PHOI] if any(v in vai_tro for v in VAI_TRO_NHAN) else []


def ky_token(sub: str, kenh: list[str], khoa: str, han_giay: int, bay_gio: float | None = None) -> str:
    """Token kết nối Centrifugo (HS256): sub, kênh server-side, iss/aud riêng, hết hạn ngắn."""
    if not khoa:
        raise ValueError("thiếu khóa ký token realtime (REALTIME_TOKEN_SECRET)")
    if not kenh:
        raise ValueError("không có kênh nào để cấp token")
    iat = int(bay_gio if bay_gio is not None else time.time())
    return jwt.encode(
        {"sub": sub, "iat": iat, "exp": iat + han_giay, "iss": TOKEN_ISSUER, "aud": TOKEN_AUDIENCE,
         "channels": list(kenh)},
        khoa,
        algorithm="HS256",
    )
