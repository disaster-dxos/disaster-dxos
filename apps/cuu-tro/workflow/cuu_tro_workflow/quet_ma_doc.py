# SPDX-License-Identifier: Apache-2.0
"""Quét mã độc ảnh hiện trường bằng clamd (ClamAV, dịch vụ riêng của lõi, profile `sec`, #111).

Giao thức clamd qua TCP (không cần thư viện ngoài):
  - "zVERSION\\0"   → "ClamAV 1.5.4/28165/Mon Oct 26 …\\0" (phiên bản động cơ / bộ chữ ký / ngày bộ chữ ký);
  - "zINSTREAM\\0"  → gửi nội dung thành các khúc [độ dài 4 byte big-endian][dữ liệu], kết thúc bằng khúc dài 0;
                     clamd trả "stream: OK\\0" | "stream: <tên chữ ký> FOUND\\0" | "… ERROR\\0".
Nội dung ảnh nằm trong bộ nhớ (API đã giới hạn ANH_MAX_BYTES, mặc định 10 MiB; clamd StreamMaxLength 25 MiB),
gửi thẳng trong mạng nội bộ, không ghi tệp tạm.

Kết quả là một trong ba: SACH, NHIEM (kèm tên chữ ký), hoặc LoiQuet (không kết nối được, hết giờ, clamd báo
lỗi). API quyết định khi lỗi: mặc định vẫn nhận ảnh với scan_status "chua_quet" (ảnh cứu nạn không được mất vì
máy quét tắt), ANH_QUET_BAT_BUOC=1 thì từ chối.
"""

import asyncio
from dataclasses import dataclass

KHUC = 64 * 1024


class LoiQuet(Exception):
    """Không quét được: máy quét không có, hết giờ, hoặc clamd trả lỗi."""


@dataclass(frozen=True)
class KetQuaQuet:
    sach: bool
    chu_ky: str | None
    dong_co: str | None


class MayQuet:
    """Client clamd. host rỗng = tắt quét (luôn LoiQuet "tắt")."""

    def __init__(self, host: str, port: int = 3310, timeout: float = 30.0) -> None:
        self.host = host.strip()
        self.port = port
        self.timeout = timeout

    @property
    def bat(self) -> bool:
        return bool(self.host)

    async def _hoi(self, lenh: bytes, du_lieu: bytes | None = None) -> str:
        if not self.bat:
            raise LoiQuet("quét mã độc đang tắt (CLAMAV_HOST trống)")
        try:
            async with asyncio.timeout(self.timeout):
                reader, writer = await asyncio.open_connection(self.host, self.port)
                try:
                    writer.write(lenh)
                    if du_lieu is not None:
                        for i in range(0, len(du_lieu), KHUC):
                            khuc = du_lieu[i:i + KHUC]
                            writer.write(len(khuc).to_bytes(4, "big") + khuc)
                            await writer.drain()
                        writer.write(b"\x00\x00\x00\x00")
                    await writer.drain()
                    tra_loi = await reader.readuntil(b"\x00")
                finally:
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except OSError:
                        pass
        except TimeoutError as e:
            raise LoiQuet(f"clamd không trả lời trong {self.timeout:g} giây") from e
        except (OSError, asyncio.IncompleteReadError, asyncio.LimitOverrunError) as e:
            raise LoiQuet(f"không kết nối được clamd {self.host}:{self.port} ({type(e).__name__})") from e
        return tra_loi.rstrip(b"\x00").decode("utf-8", "replace").strip()

    async def phien_ban(self) -> str:
        return await self._hoi(b"zVERSION\x00")

    async def quet(self, du_lieu: bytes) -> KetQuaQuet:
        tra_loi = await self._hoi(b"zINSTREAM\x00", du_lieu)
        kq = doc_ket_qua(tra_loi)
        try:
            dong_co = await self.phien_ban()
        except LoiQuet:
            dong_co = None
        return KetQuaQuet(kq.sach, kq.chu_ky, rut_gon_phien_ban(dong_co))


def doc_ket_qua(tra_loi: str) -> KetQuaQuet:
    """"stream: OK" → sạch; "stream: <chữ ký> FOUND" → nhiễm; còn lại ("… ERROR", lạ) → LoiQuet."""
    noi_dung = tra_loi.split(":", 1)[1].strip() if ":" in tra_loi else tra_loi.strip()
    if noi_dung == "OK":
        return KetQuaQuet(True, None, None)
    if noi_dung.endswith(" FOUND"):
        return KetQuaQuet(False, noi_dung[: -len(" FOUND")].strip()[:200], None)
    raise LoiQuet(f"clamd báo lỗi: {noi_dung[:200]}")


def rut_gon_phien_ban(v: str | None) -> str | None:
    """"ClamAV 1.5.4/28165/Mon Oct 26 08:38:01 2026" → "ClamAV 1.5.4/28165" (động cơ / số bộ chữ ký daily)."""
    if not v:
        return None
    phan = v.split("/")
    return "/".join(phan[:2])[:100]
