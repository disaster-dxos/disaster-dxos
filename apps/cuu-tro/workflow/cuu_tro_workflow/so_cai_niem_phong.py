# SPDX-License-Identifier: Apache-2.0
"""Bộ niêm phong bù sổ cái minh bạch (#89), chạy trong tiến trình worker.

Outbox là chính các dòng supply_movements / relief_fund_entries có ledger_index NULL: phiếu/bút toán và
"việc phải niêm phong" nằm trong CÙNG transaction, không mất việc khi API chết giữa chừng hay sổ cái
tạm dừng. API niêm phong ngay sau khi lập; bộ này quét mỗi SO_CAI_QUET_GIAY giây các dòng chưa niêm
phong cũ hơn SO_CAI_CHO_GIAY giây (để API làm trước, không tranh nhau), khóa FOR UPDATE SKIP LOCKED
(nhiều worker không lấy trùng), ghi lá rồi điền ledger_*. Sổ cái lỗi → dừng lượt, lượt sau thử lại.
Gửi lại cùng lá là an toàn: core/ledger chống trùng, trả index cũ (#28).
"""

import asyncio
import logging
from typing import Any

import asyncpg

from . import so_cai, so_cai_csdl

LO = 20
log = logging.getLogger("cuu-tro-niem-phong")

SQL_CHO = {
    so_cai_csdl.PHIEU_KHO: """
SELECT id, supply_id, direction, quantity, note, shelter_id, created_at, ledger_index, ledger_leaf_hash, ledger_logged_at
  FROM cuu_tro.supply_movements
 WHERE ledger_index IS NULL AND created_at < now() - make_interval(secs => $1)
 ORDER BY created_at LIMIT $2 FOR UPDATE SKIP LOCKED""",
    so_cai_csdl.KHOAN_TIEN: """
SELECT id, direction, amount, currency, category, purpose, shelter_id, supply_movement_id, created_at,
       ledger_index, ledger_leaf_hash, ledger_logged_at
  FROM cuu_tro.relief_fund_entries
 WHERE ledger_index IS NULL AND created_at < now() - make_interval(secs => $1)
 ORDER BY created_at LIMIT $2 FOR UPDATE SKIP LOCKED""",
}


class BoNiemPhong:
    def __init__(self, pool: asyncpg.Pool, client: so_cai.SoCai, cho_giay: float = 5, quet_giay: float = 10) -> None:
        self._pool, self._client = pool, client
        self._cho, self._quet = cho_giay, quet_giay

    async def mot_luot(self) -> dict[str, Any]:
        """Một lượt quét cả hai loại. Trả số dòng đã niêm phong theo loại và lỗi sổ cái (nếu có)."""
        kq: dict[str, Any] = {"loi": None}
        for ten, sql in SQL_CHO.items():
            loai = so_cai_csdl.LOAI[ten]
            kq[ten] = 0
            async with self._pool.acquire() as con, con.transaction():
                for dong in await con.fetch(sql, float(self._cho), LO):
                    r = await so_cai_csdl.niem_phong(self._client, con, loai, dict(dong))
                    if r["trang_thai"] != "da_ghi":
                        kq["loi"] = r.get("loi")
                        break
                    kq[ten] += 1
                    log.info("đã niêm phong bù %s %s → lá %s", ten, dong["id"], r["index"])
            if kq["loi"]:
                break
        return kq

    async def chay(self, dung: asyncio.Event) -> None:
        log.info("bộ niêm phong sổ cái chạy: quét mỗi %ss, dòng cũ hơn %ss", self._quet, self._cho)
        while not dung.is_set():
            try:
                kq = await self.mot_luot()
                if kq["loi"]:
                    log.warning("sổ cái chưa nhận, thử lại lượt sau: %s", kq["loi"])
            except Exception:
                log.exception("lượt niêm phong lỗi")
            try:
                await asyncio.wait_for(dung.wait(), timeout=self._quet)
            except asyncio.TimeoutError:
                pass
