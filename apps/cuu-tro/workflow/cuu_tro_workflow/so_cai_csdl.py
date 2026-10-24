# SPDX-License-Identifier: Apache-2.0
"""Phần CSDL của sổ cái minh bạch (#28, #89), role dịch vụ cuu_tro_app (migration 0006, 0011).

Hai bảng được niêm phong: supply_movements (phiếu nhập/xuất hàng) và relief_fund_entries (bút toán tiền
thu/chi). Mỗi bảng một LoaiSoCai: cột đọc, bản ghi chuẩn hóa, lá, câu UPDATE điền ledger_* một lần.
Dòng có ledger_index NULL là outbox: cùng transaction với phiếu/bút toán; API niêm phong ngay sau khi
lập, bộ niêm phong trong worker (so_cai_niem_phong.py) ghi bù dòng còn sót.
Không đọc created_by (người lập không lên trang công khai).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable

import asyncpg

from . import so_cai

PHIEU_KHO, KHOAN_TIEN = "phieu_kho", "khoan_tien"


@dataclass(frozen=True)
class LoaiSoCai:
    ten: str
    bang: str
    loai_la: str
    ban_ghi: Callable[[dict[str, Any]], dict[str, str | None]]
    la: Callable[[dict[str, str | None]], dict[str, Any]]


LOAI = {
    PHIEU_KHO: LoaiSoCai(PHIEU_KHO, "cuu_tro.supply_movements", so_cai.LOAI_LA,
                         so_cai.ban_ghi_chuan_hoa, so_cai.la_cho_phieu),
    KHOAN_TIEN: LoaiSoCai(KHOAN_TIEN, "cuu_tro.relief_fund_entries", so_cai.LOAI_LA_TIEN,
                          so_cai.ban_ghi_khoan_tien, so_cai.la_cho_khoan_tien),
}

_COT_TIEN = """k.id, k.direction, k.amount, k.currency, k.category, k.purpose, k.shelter_id, k.supply_movement_id,
               k.created_at, k.ledger_index, k.ledger_leaf_hash, k.ledger_logged_at"""


class SoKhoanTien:
    """Bút toán tiền cứu trợ (relief_fund_entries, migration 0011)."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def them(self, *, direction: str, amount: Decimal, category: str, purpose: str | None,
                   shelter_id: str | None, supply_movement_id: str | None, created_by: str) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            f"""INSERT INTO cuu_tro.relief_fund_entries AS k (direction, amount, category, purpose, shelter_id,
                                                             supply_movement_id, created_by)
                VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING {_COT_TIEN}""",
            direction, amount, category, purpose, uuid.UUID(shelter_id) if shelter_id else None,
            uuid.UUID(supply_movement_id) if supply_movement_id else None, created_by,
        )
        return dict(row)

    async def doc(self, ma: str) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            f"""SELECT {_COT_TIEN}, sh.name AS shelter_name
                  FROM cuu_tro.relief_fund_entries k LEFT JOIN cuu_tro.shelters sh ON sh.id = k.shelter_id
                 WHERE k.id = $1""",
            uuid.UUID(ma),
        )
        return dict(row) if row else None

    async def ghi_so(self, ma: str, index: int, leaf_hash: bytes) -> datetime | None:
        return await dien_ledger(self._pool, LOAI[KHOAN_TIEN], ma, index, leaf_hash)


async def dien_ledger(con: asyncpg.Connection | asyncpg.Pool, loai: LoaiSoCai, ma: str, index: int,
                      leaf_hash: bytes) -> datetime | None:
    """Điền ledger_* nếu chưa có; None nếu đã có (trigger bất biến chặn ghi đè)."""
    return await con.fetchval(
        f"""UPDATE {loai.bang} SET ledger_index = $2, ledger_leaf_hash = $3, ledger_logged_at = now()
             WHERE id = $1 AND ledger_index IS NULL RETURNING ledger_logged_at""",
        uuid.UUID(ma), index, leaf_hash,
    )


async def niem_phong(client: so_cai.SoCai, con: asyncpg.Connection | asyncpg.Pool, loai: LoaiSoCai,
                     dong: dict[str, Any]) -> dict[str, Any]:
    """Ghi lá của dòng lên sổ cái rồi điền ledger_*. Lá trùng (gọi lại) được sổ cái trả index cũ.
    Lỗi sổ cái → trang_thai chua_ghi_so, dòng vẫn ở outbox."""
    ban_ghi = loai.ban_ghi(dong)
    try:
        kq = await client.ghi(loai.la(ban_ghi))
    except so_cai.LoiSoCai as e:
        return {"trang_thai": so_cai.CHUA_GHI_SO, "loi": str(e)}
    lh = bytes.fromhex(kq["leaf_hash"])
    luc = await dien_ledger(con, loai, ban_ghi["id"], kq["index"], lh)
    return {"trang_thai": "da_ghi", "index": kq["index"], "leaf_hash": kq["leaf_hash"],
            "tree_size": kq.get("tree_size"), "trung": bool(kq.get("duplicate")),
            "logged_at": luc.isoformat() if luc else None}


# ---------------- Danh sách / tổng hợp công khai ----------------
SQL_DANH_SACH = """
SELECT * FROM (
  SELECT 'phieu_kho' AS loai, m.id, m.direction, m.quantity AS so_luong, s.unit AS don_vi, s.item_name AS noi_dung,
         sh.name AS diem_nhan, m.created_at, m.ledger_index
    FROM cuu_tro.supply_movements m JOIN cuu_tro.supplies s ON s.id = m.supply_id
    LEFT JOIN cuu_tro.shelters sh ON sh.id = m.shelter_id
   WHERE m.ledger_index IS NOT NULL
  UNION ALL
  SELECT 'khoan_tien', k.id, k.direction, k.amount, k.currency, k.category, sh.name, k.created_at, k.ledger_index
    FROM cuu_tro.relief_fund_entries k LEFT JOIN cuu_tro.shelters sh ON sh.id = k.shelter_id
   WHERE k.ledger_index IS NOT NULL
) x
WHERE ($1::bigint IS NULL OR x.ledger_index < $1) AND ($2::text IS NULL OR x.loai = $2)
ORDER BY x.ledger_index DESC
LIMIT $3
"""

SQL_TONG_HOP = """
SELECT coalesce(sum(amount) FILTER (WHERE direction = 'thu'), 0) AS tong_thu,
       coalesce(sum(amount) FILTER (WHERE direction = 'chi'), 0) AS tong_chi,
       count(*) FILTER (WHERE ledger_index IS NOT NULL) AS da_niem_phong,
       count(*) FILTER (WHERE ledger_index IS NULL) AS cho_niem_phong
  FROM cuu_tro.relief_fund_entries
"""
SQL_CHO_PHIEU = "SELECT count(*) FROM cuu_tro.supply_movements WHERE ledger_index IS NULL"


class SoCaiCongKhai:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def danh_sach(self, truoc: int | None, loai: str | None, gioi_han: int) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(SQL_DANH_SACH, truoc, loai, gioi_han)
        return [{
            "loai": r["loai"], "ma": str(r["id"]), "chieu": r["direction"],
            "so_luong": format(Decimal(r["so_luong"]), "f"), "don_vi": r["don_vi"],
            # phieu_kho: tên mặt hàng; khoan_tien: hạng mục
            "noi_dung": r["noi_dung"], "diem_nhan": r["diem_nhan"],
            "thoi_diem": r["created_at"].isoformat(), "ledger_index": r["ledger_index"],
        } for r in rows]

    async def tong_hop(self) -> dict[str, Any]:
        r = await self._pool.fetchrow(SQL_TONG_HOP)
        cho_phieu = await self._pool.fetchval(SQL_CHO_PHIEU)
        thu, chi = Decimal(r["tong_thu"]), Decimal(r["tong_chi"])
        return {"don_vi": "VND", "tong_thu": f"{thu:.0f}", "tong_chi": f"{chi:.0f}", "so_du": f"{thu - chi:.0f}",
                "khoan_tien_da_niem_phong": r["da_niem_phong"], "khoan_tien_cho_niem_phong": r["cho_niem_phong"],
                "phieu_kho_cho_niem_phong": cho_phieu}
