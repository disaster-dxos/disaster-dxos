# SPDX-License-Identifier: Apache-2.0
"""Activity của worker: đọc/ghi CSDL bằng role dịch vụ cuu_tro_app (quyền tối thiểu, db/migrations/0003).

Activity là nơi duy nhất có I/O; workflow chỉ điều phối và phải tất định (deterministic).
Mọi activity chạy lại được (Temporal thử lại khi lỗi mạng/CSDL): ghi trạng thái có kiểm điều kiện.
"""

import asyncpg
from temporalio import activity
from temporalio.exceptions import ApplicationError

from .logic import (
    DOI_DANG_LAM_NHIEM_VU,
    DOI_SAN_SANG,
    ChuyenTrangThaiKhongHopLe,
    DoiUngVien,
    TinKeuCuu,
    kiem_tra_chuyen_trang_thai,
)

# Ứng viên lấy theo KNN của chỉ mục GiST (toán tử <-> trên geography), lọc trước theo trạng thái và
# bán kính; chọn đội cuối cùng là việc của logic.chon_doi_gan_nhat.
SQL_UNG_VIEN = """
SELECT t.id::text AS id, t.name, t.status, t.member_count,
       ST_Distance(t.location, i.location) AS khoang_cach_m
  FROM cuu_tro.incidents i
  JOIN cuu_tro.rescue_teams t
    ON t.status = 'san_sang' AND t.location IS NOT NULL AND ST_DWithin(t.location, i.location, $2)
 WHERE i.id = $1
 ORDER BY t.location <-> i.location
 LIMIT 10
"""


@activity.defn(name="chao")
async def chao(ten: str) -> str:
    """Activity của workflow Hello: kiểm thử đường đi API → Temporal → worker."""
    return f"Xin chào {ten}, worker cuu-tro đã nhận việc"


class HoatDong:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @activity.defn(name="doc_tin")
    async def doc_tin(self, incident_id: str) -> TinKeuCuu | None:
        row = await self._pool.fetchrow(
            "SELECT id::text, status, assigned_team_id::text FROM cuu_tro.incidents WHERE id = $1",
            incident_id,
        )
        if row is None:
            return None
        return TinKeuCuu(id=row["id"], trang_thai=row["status"], doi_id=row["assigned_team_id"])

    @activity.defn(name="tim_doi_ung_vien")
    async def tim_doi_ung_vien(self, incident_id: str, ban_kinh_m: int) -> list[DoiUngVien]:
        rows = await self._pool.fetch(SQL_UNG_VIEN, incident_id, float(ban_kinh_m))
        return [
            DoiUngVien(
                id=r["id"],
                ten=r["name"],
                trang_thai=r["status"],
                khoang_cach_m=round(r["khoang_cach_m"], 1),
                so_thanh_vien=r["member_count"],
            )
            for r in rows
        ]

    @activity.defn(name="gan_doi")
    async def gan_doi(self, incident_id: str, doi_id: str) -> bool:
        """Gán đội cho tin (tiep_nhan → phan_cong) và chuyển đội sang dang_lam_nhiem_vu.

        Trả False khi đội vừa bị gán cho tin khác (không còn san_sang): workflow chọn đội khác.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            tin = await conn.fetchrow(
                "SELECT status, assigned_team_id::text AS doi FROM cuu_tro.incidents WHERE id = $1 FOR UPDATE",
                incident_id,
            )
            if tin is None:
                raise ApplicationError(f"không có tin kêu cứu {incident_id}", non_retryable=True)
            if tin["status"] == "phan_cong" and tin["doi"] == doi_id:
                return True  # lần thử lại sau khi đã ghi thành công
            _chuyen(tin["status"], "phan_cong")
            doi = await conn.execute(
                "UPDATE cuu_tro.rescue_teams SET status = $2 WHERE id = $1 AND status = $3",
                doi_id,
                DOI_DANG_LAM_NHIEM_VU,
                DOI_SAN_SANG,
            )
            if doi != "UPDATE 1":
                return False
            await conn.execute(
                "UPDATE cuu_tro.incidents SET status = 'phan_cong', assigned_team_id = $2 WHERE id = $1",
                incident_id,
                doi_id,
            )
        activity.logger.info("Đã gán đội %s cho tin %s", doi_id, incident_id)
        return True

    @activity.defn(name="ket_thuc")
    async def ket_thuc(self, incident_id: str, doi_id: str) -> str:
        """Sau xác nhận "đã cứu": tin → da_cuu → dong, đội trở lại san_sang. Trả trạng thái cuối."""
        async with self._pool.acquire() as conn, conn.transaction():
            tin = await conn.fetchrow(
                "SELECT status FROM cuu_tro.incidents WHERE id = $1 FOR UPDATE", incident_id
            )
            if tin is None:
                raise ApplicationError(f"không có tin kêu cứu {incident_id}", non_retryable=True)
            trang_thai = tin["status"]
            # Đã đóng (lần thử lại sau khi đã ghi) thì chỉ còn trả đội
            buoc = [] if trang_thai == "dong" else ["dong"] if trang_thai == "da_cuu" else ["da_cuu", "dong"]
            for moi in buoc:
                _chuyen(trang_thai, moi)
                await conn.execute(
                    "UPDATE cuu_tro.incidents SET status = $2 WHERE id = $1", incident_id, moi
                )
                trang_thai = moi
            await conn.execute(
                "UPDATE cuu_tro.rescue_teams SET status = $2 WHERE id = $1 AND status = $3",
                doi_id,
                DOI_SAN_SANG,
                DOI_DANG_LAM_NHIEM_VU,
            )
        return trang_thai


def _chuyen(hien_tai: str, moi: str) -> None:
    try:
        kiem_tra_chuyen_trang_thai(hien_tai, moi)
    except ChuyenTrangThaiKhongHopLe as e:
        # Lỗi nghiệp vụ: thử lại không giúp được gì
        raise ApplicationError(str(e), type="ChuyenTrangThaiKhongHopLe", non_retryable=True) from e
