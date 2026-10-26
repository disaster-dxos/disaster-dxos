# SPDX-License-Identifier: Apache-2.0
"""Header `Idempotency-Key` cho đường ghi mà app hiện trường gửi lại từ hàng đợi offline (#106, D-011).

Client đặt cho mỗi bản ghi trong hàng đợi một khóa ngẫu nhiên (UUID) và giữ nguyên khóa khi gửi lại. API:
  1. Không có header → chạy như cũ (web điều phối, curl).
  2. Có header: kiểm dạng khóa (8–128 ký tự A-Z a-z 0-9 _ -), băm endpoint + nội dung yêu cầu.
  3. `tim`: khóa đã xong trong 72 giờ → trả lại đúng phản hồi cũ (header `Idempotent-Replayed: true`), không làm
     lại; cùng khóa mà nội dung/đường dẫn khác → 422 `khoa_idempotency_dung_lai`.
  4. `chay`: trong MỘT transaction: INSERT khóa trước (yêu cầu đồng thời cùng khóa chờ ở PRIMARY KEY tới khi
     yêu cầu đầu COMMIT rồi phát lại kết quả của nó), làm việc nghiệp vụ bằng cùng kết nối, ghi phản hồi, COMMIT.
     Nghiệp vụ lỗi (422, 409 tin trùng…) → rollback, khóa không được giữ: gửi lại sẽ làm lại và nhận cùng lỗi.

Phản hồi lưu lại không chứa dữ liệu cá nhân: đường nào trả SĐT/tên/văn bản thì tự chọn phần được lưu.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import asyncpg

HEADER = "Idempotency-Key"
HEADER_PHAT_LAI = "Idempotent-Replayed"
HAN_GIO = 72
_KHOA = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


class KhoaSai(Exception):
    """Header có nhưng sai dạng → 422."""


class KhoaDungLai(Exception):
    """Cùng khóa đã dùng cho yêu cầu khác (đường dẫn hoặc nội dung khác) → 422."""


@dataclass(frozen=True)
class KetQua:
    status: int
    body: dict[str, Any]
    phat_lai: bool


def doc_khoa(gia_tri: str | None) -> str | None:
    """Giá trị header → khóa; None nếu không gửi header. Sai dạng → KhoaSai."""
    if gia_tri is None:
        return None
    k = gia_tri.strip()
    if not _KHOA.match(k):
        raise KhoaSai(gia_tri[:20])
    return k


def bam(endpoint: str, noi_dung: bytes) -> bytes:
    """SHA-256 của "<endpoint>\\n<nội dung>": cùng khóa phải đi với đúng một yêu cầu."""
    return hashlib.sha256(endpoint.encode() + b"\n" + noi_dung).digest()


def loi_422(ly_do: str) -> dict[str, Any]:
    return {"ma": "khoa_idempotency_dung_lai" if ly_do == "dung_lai" else "khoa_idempotency_sai",
            "thong_bao": ("Idempotency-Key này đã dùng cho một yêu cầu khác (khác đường dẫn hoặc nội dung): mỗi bản "
                          "ghi phải có khóa riêng." if ly_do == "dung_lai" else
                          "Idempotency-Key phải gồm 8–128 ký tự chữ, số, '-' hoặc '_' (nên dùng UUID)."),
            "loi": [{"truong": HEADER, "thong_bao": "Khóa không hợp lệ cho yêu cầu này."}]}


# Nghiệp vụ chạy trong transaction: nhận kết nối, trả (mã HTTP 2xx, body trả client, body được lưu để phát lại)
XuLy = Callable[[asyncpg.Connection | None], Awaitable[tuple[int, dict[str, Any], dict[str, Any]]]]


class SoIdempotency:
    """Bảng cuu_tro.idempotency_keys (migration 0015) bằng role dịch vụ cuu_tro_app."""

    def __init__(self, pool: asyncpg.Pool, han_gio: int = HAN_GIO) -> None:
        self._pool = pool
        self._han = han_gio

    @staticmethod
    def _tu_dong(dong: Any, endpoint: str, sha: bytes) -> KetQua:
        if dong["endpoint"] != endpoint or bytes(dong["request_sha256"]) != sha:
            raise KhoaDungLai()
        body = dong["response"]
        return KetQua(dong["status_code"], json.loads(body) if isinstance(body, str) else body, True)

    async def tim(self, sub: str, khoa: str, endpoint: str, sha: bytes) -> KetQua | None:
        """Phản hồi đã lưu của khóa (còn hạn), không khóa dòng; None nếu chưa có."""
        dong = await self._pool.fetchrow(
            """SELECT endpoint, request_sha256, status_code, response FROM cuu_tro.idempotency_keys
                WHERE owner_sub = $1 AND key = $2 AND status_code IS NOT NULL
                  AND created_at > now() - make_interval(hours => $3)""", sub, khoa, self._han)
        return self._tu_dong(dong, endpoint, sha) if dong else None

    async def chay(self, sub: str, khoa: str, endpoint: str, sha: bytes, xu_ly: XuLy) -> KetQua:
        async with self._pool.acquire() as conn, conn.transaction():
            # Khóa hết hạn của chính người này: xóa để dùng lại được (client nên sinh khóa mới, nhưng không chặn)
            await conn.execute(
                """DELETE FROM cuu_tro.idempotency_keys
                    WHERE owner_sub = $1 AND key = $2 AND created_at <= now() - make_interval(hours => $3)""",
                sub, khoa, self._han)
            giu = await conn.fetchval(
                """INSERT INTO cuu_tro.idempotency_keys (owner_sub, key, endpoint, request_sha256)
                   VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING RETURNING true""", sub, khoa, endpoint, sha)
            if not giu:
                # Yêu cầu khác cùng khóa đã COMMIT trong lúc ta chờ: phát lại kết quả của nó
                dong = await conn.fetchrow(
                    """SELECT endpoint, request_sha256, status_code, response FROM cuu_tro.idempotency_keys
                        WHERE owner_sub = $1 AND key = $2""", sub, khoa)
                return self._tu_dong(dong, endpoint, sha)
            status, body, luu = await xu_ly(conn)
            await conn.execute(
                """UPDATE cuu_tro.idempotency_keys SET status_code = $3, response = $4::jsonb
                    WHERE owner_sub = $1 AND key = $2""", sub, khoa, status, json.dumps(luu, ensure_ascii=False))
            return KetQua(status, body, False)

    async def don(self) -> int:
        """Xóa khóa hết hạn (gọi khi API khởi động); trả số dòng đã xóa."""
        kq = await self._pool.execute(
            "DELETE FROM cuu_tro.idempotency_keys WHERE created_at <= now() - make_interval(hours => $1)", self._han)
        return int(kq.split()[-1])
