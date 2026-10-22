# SPDX-License-Identifier: Apache-2.0
"""Activity của worker: đọc/ghi CSDL bằng role dịch vụ cuu_tro_app (quyền tối thiểu, db/migrations/0003,
0007); báo điều phối qua NATS JetStream.

Activity là nơi duy nhất có I/O; workflow chỉ điều phối và phải tất định (deterministic).
Mọi activity chạy lại được (Temporal thử lại khi lỗi mạng/CSDL): ghi trạng thái có kiểm điều kiện.
"""

import json

import asyncpg
from temporalio import activity
from temporalio.exceptions import ApplicationError

from .logic import (
    DOI_DANG_LAM_NHIEM_VU,
    DOI_SAN_SANG,
    GAN_BI_GIANH,
    GAN_DA_GAN,
    GAN_NHUONG,
    GAN_TIN_DA_DOI,
    GIAO_DA_NHAN,
    BaoDieuPhoi,
    ChuyenTrangThaiKhongHopLe,
    DoiUngVien,
    KetQuaGiao,
    TinKeuCuu,
    YeuCauGan,
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

# Đánh dấu tin đang được workflow tìm đội (luật nhường đội, migration 0007). Tin khởi chạy tay chưa
# có dòng hàng đợi thì thêm (started_at = now: bộ khởi chạy không chạy lại). Tin đã bị xóa / không
# còn tiep_nhan thì không ghi gì (không lỗi khóa ngoại).
SQL_DANG_TIM = """
INSERT INTO cuu_tro.assignment_queue (incident_id, started_at, seeking_at)
SELECT id, now(), now() FROM cuu_tro.incidents WHERE id = $1 AND status = 'tiep_nhan'
ON CONFLICT (incident_id) DO UPDATE SET seeking_at = EXCLUDED.seeking_at
"""

# Sự kiện cho điều phối viên (stream CUU_TRO_DIEU_PHOI, apps/cuu-tro/nats/streams.json)
SUBJECT_DIEU_PHOI = "cuu-tro.dieu-phoi.can-xu-ly"


@activity.defn(name="chao")
async def chao(ten: str) -> str:
    """Activity của workflow Hello: kiểm thử đường đi API → Temporal → worker."""
    return f"Xin chào {ten}, worker cuu-tro đã nhận việc"


class HoatDong:
    def __init__(self, pool: asyncpg.Pool, js=None) -> None:
        self._pool = pool
        # JetStream (nats-py) để báo điều phối; None khi chạy không có NATS (kiểm thử)
        self._js = js

    @activity.defn(name="doc_tin")
    async def doc_tin(self, incident_id: str) -> TinKeuCuu | None:
        row = await self._pool.fetchrow(
            "SELECT id::text, status, assigned_team_id::text, urgency FROM cuu_tro.incidents WHERE id = $1",
            incident_id,
        )
        if row is None:
            return None
        return TinKeuCuu(id=row["id"], trang_thai=row["status"], doi_id=row["assigned_team_id"],
                         urgency=row["urgency"])

    @activity.defn(name="tim_doi_ung_vien")
    async def tim_doi_ung_vien(self, incident_id: str, ban_kinh_m: int) -> list[DoiUngVien]:
        async with self._pool.acquire() as conn:
            await conn.execute(SQL_DANG_TIM, incident_id)
            rows = await conn.fetch(SQL_UNG_VIEN, incident_id, float(ban_kinh_m))
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
    async def gan_doi(self, yc: YeuCauGan) -> str:
        """Gán đội cho tin (tiep_nhan → phan_cong), đội → dang_lam_nhiem_vu, ghi lịch sử giao.

        Trả GAN_DA_GAN; GAN_BI_GIANH khi đội vừa bị gán cho tin khác; GAN_NHUONG khi đội đang được giữ
        cho tin khẩn hơn đang chờ (hàm SQL team_reserved_for_more_urgent); GAN_TIN_DA_DOI khi tin
        không còn tiep_nhan. Chạy lại sau khi đã ghi thành công vẫn trả GAN_DA_GAN.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            tin = await conn.fetchrow(
                "SELECT status, assigned_team_id::text AS doi FROM cuu_tro.incidents WHERE id = $1 FOR UPDATE",
                yc.incident_id,
            )
            if tin is None:
                return GAN_TIN_DA_DOI  # tin đã bị xóa
            if tin["status"] == "phan_cong" and tin["doi"] == yc.doi_id:
                await self._ghi_lich_su(conn, yc)
                return GAN_DA_GAN  # lần thử lại sau khi đã ghi thành công
            if tin["status"] != "tiep_nhan":
                return GAN_TIN_DA_DOI
            if await conn.fetchval(
                "SELECT cuu_tro.team_reserved_for_more_urgent($1, $2, $3, $4)",
                yc.incident_id, yc.doi_id, float(yc.ban_kinh_m), yc.cua_so_tim_giay,
            ):
                return GAN_NHUONG
            doi = await conn.execute(
                "UPDATE cuu_tro.rescue_teams SET status = $2 WHERE id = $1 AND status = $3",
                yc.doi_id,
                DOI_DANG_LAM_NHIEM_VU,
                DOI_SAN_SANG,
            )
            if doi != "UPDATE 1":
                return GAN_BI_GIANH
            await conn.execute(
                "UPDATE cuu_tro.incidents SET status = 'phan_cong', assigned_team_id = $2 WHERE id = $1",
                yc.incident_id,
                yc.doi_id,
            )
            await self._ghi_lich_su(conn, yc)
            await conn.execute(
                "UPDATE cuu_tro.assignment_queue SET seeking_at = NULL WHERE incident_id = $1", yc.incident_id
            )
        activity.logger.info("Đã gán đội %s cho tin %s (lần %s)", yc.doi_id, yc.incident_id, yc.lan)
        return GAN_DA_GAN

    @staticmethod
    async def _ghi_lich_su(conn: asyncpg.Connection, yc: YeuCauGan) -> None:
        await conn.execute(
            """INSERT INTO cuu_tro.incident_assignments
                 (incident_id, team_id, workflow_run_id, attempt_no, urgency, distance_m, deadline_at)
               VALUES ($1, $2, $3, $4, $5, $6, now() + make_interval(secs => $7))
               ON CONFLICT (workflow_run_id, attempt_no) DO NOTHING""",
            yc.incident_id, yc.doi_id, yc.workflow_run_id, yc.lan, yc.urgency, yc.khoang_cach_m,
            float(yc.han_nhan_giay),
        )

    @staticmethod
    async def _ket_qua_giao(conn: asyncpg.Connection, kq: KetQuaGiao) -> None:
        # Chỉ dòng còn cho_nhan: lần thử lại không ghi đè kết quả đã có
        await conn.execute(
            """UPDATE cuu_tro.incident_assignments
                  SET result = $3, responded_at = now(), responded_by = $4, note = NULLIF($5, '')
                WHERE workflow_run_id = $1 AND attempt_no = $2 AND result = 'cho_nhan'""",
            kq.workflow_run_id, kq.lan, kq.ket_qua, kq.nguoi, kq.ghi_chu,
        )

    @activity.defn(name="nhan_nhiem_vu")
    async def nhan_nhiem_vu(self, kq: KetQuaGiao) -> str:
        """Đội nhận nhiệm vụ: tin phan_cong → dang_cuu, lịch sử da_nhan. Trả trạng thái tin."""
        async with self._pool.acquire() as conn, conn.transaction():
            tin = await conn.fetchrow(
                "SELECT status, assigned_team_id::text AS doi FROM cuu_tro.incidents WHERE id = $1 FOR UPDATE",
                kq.incident_id,
            )
            if tin is None:
                raise ApplicationError(f"không có tin kêu cứu {kq.incident_id}", non_retryable=True)
            if tin["doi"] != kq.doi_id:
                raise ApplicationError(f"tin {kq.incident_id} không còn giao cho đội {kq.doi_id}", non_retryable=True)
            trang_thai = tin["status"]
            if trang_thai == "phan_cong":
                _chuyen(trang_thai, "dang_cuu")
                await conn.execute("UPDATE cuu_tro.incidents SET status = 'dang_cuu' WHERE id = $1", kq.incident_id)
                trang_thai = "dang_cuu"
            await self._ket_qua_giao(conn, KetQuaGiao(**{**kq.__dict__, "ket_qua": GIAO_DA_NHAN}))
        return trang_thai

    @activity.defn(name="go_doi")
    async def go_doi(self, kq: KetQuaGiao) -> str:
        """Đội từ chối / quá hạn nhận / điều phối hủy: gỡ đội khỏi tin (phan_cong → tiep_nhan),
        đội trở lại san_sang, ghi kết quả vào lịch sử. Tin đã đổi khác (xử lý tay) thì chỉ ghi lịch sử."""
        async with self._pool.acquire() as conn, conn.transaction():
            tin = await conn.fetchrow(
                "SELECT status, assigned_team_id::text AS doi FROM cuu_tro.incidents WHERE id = $1 FOR UPDATE",
                kq.incident_id,
            )
            trang_thai = tin["status"] if tin else "khong_co"
            if tin is not None and tin["status"] == "phan_cong" and tin["doi"] == kq.doi_id:
                _chuyen("phan_cong", "tiep_nhan")
                await conn.execute(
                    "UPDATE cuu_tro.incidents SET status = 'tiep_nhan', assigned_team_id = NULL WHERE id = $1",
                    kq.incident_id,
                )
                await conn.execute(
                    "UPDATE cuu_tro.rescue_teams SET status = $2 WHERE id = $1 AND status = $3",
                    kq.doi_id, DOI_SAN_SANG, DOI_DANG_LAM_NHIEM_VU,
                )
                trang_thai = "tiep_nhan"
            await self._ket_qua_giao(conn, kq)
        activity.logger.info("Gỡ đội %s khỏi tin %s: %s", kq.doi_id, kq.incident_id, kq.ket_qua)
        return trang_thai

    @activity.defn(name="dung_tim")
    async def dung_tim(self, incident_id: str) -> None:
        """Workflow thôi tìm đội cho tin (không có đội, hủy, tin đã đổi): bỏ giữ chỗ ưu tiên."""
        await self._pool.execute(
            "UPDATE cuu_tro.assignment_queue SET seeking_at = NULL WHERE incident_id = $1", incident_id
        )

    @activity.defn(name="bao_dieu_phoi")
    async def bao_dieu_phoi(self, bd: BaoDieuPhoi) -> None:
        """Phát sự kiện cần điều phối xử lý lên JetStream; web/bot đọc stream CUU_TRO_DIEU_PHOI.

        Nats-Msg-Id = workflow + lý do: activity chạy lại không tạo sự kiện trùng (duplicate_window).
        Sự kiện chỉ có id tin, mức khẩn cấp, lý do: không có SĐT/tên người báo.
        """
        if self._js is None:
            raise ApplicationError("worker chạy không có NATS (NATS_URL trống)", non_retryable=True)
        info = activity.info()
        await self._js.publish(
            f"{SUBJECT_DIEU_PHOI}.{bd.incident_id}",
            json.dumps({**bd.__dict__, "luc": info.current_attempt_scheduled_time.isoformat()},
                       ensure_ascii=False).encode(),
            headers={"Nats-Msg-Id": f"{info.workflow_run_id}:{bd.ly_do}"},
        )
        activity.logger.info("Báo điều phối tin %s: %s", bd.incident_id, bd.ly_do)

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
