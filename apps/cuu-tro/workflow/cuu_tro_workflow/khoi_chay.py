# SPDX-License-Identifier: Apache-2.0
"""Bộ khởi chạy tự động workflow PhanCongCuuHo (#67), chạy trong tiến trình worker.

Nguồn sự kiện: outbox cuu_tro.assignment_queue (migration 0007). Trigger trên incidents ghi một dòng
cùng transaction với tin mới rồi pg_notify("cuu_tro_tin_moi"). Bộ khởi chạy LISTEN kênh đó để dậy
ngay, và quét lại mỗi PHAN_CONG_QUET_GIAY giây phòng lỡ NOTIFY (mất kết nối, worker khởi động lại).
Mỗi lượt quét: lấy các dòng chưa khởi chạy, tin khẩn trước (urgency_rank, rồi thời điểm tạo), khóa
FOR UPDATE SKIP LOCKED (nhiều worker không lấy trùng), khởi chạy workflow rồi đánh dấu started_at.

Không chạy trùng: workflow id tất định phan-cong-<incident_id>. Đang chạy → dùng lại (USE_EXISTING);
đã chạy xong → Temporal từ chối (REJECT_DUPLICATE), coi như đã khởi chạy. Nên đánh dấu lỗi sau khi
đã khởi chạy (worker chết giữa chừng) chỉ dẫn tới một lần gọi lại vô hại.
"""

import asyncio
import logging

import asyncpg
from temporalio.client import Client
from temporalio.common import Priority, WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from . import config
from .logic import uu_tien
from .workflows import PhanCongCuuHo

KENH_TIN_MOI = "cuu_tro_tin_moi"
TIEN_TO_PHAN_CONG = "phan-cong-"
NGUOI_KHOI_CHAY = "tu-dong"
LO = 20

SQL_LAY = """
SELECT q.incident_id::text AS id, i.urgency
  FROM cuu_tro.assignment_queue q
  JOIN cuu_tro.incidents i ON i.id = q.incident_id
 WHERE q.started_at IS NULL AND i.status = 'tiep_nhan'
 ORDER BY cuu_tro.urgency_rank(i.urgency), q.created_at
 LIMIT $1
   FOR UPDATE OF q SKIP LOCKED
"""

log = logging.getLogger("cuu-tro-khoi-chay")


def workflow_id(incident_id: str) -> str:
    return f"{TIEN_TO_PHAN_CONG}{incident_id}"


async def khoi_chay_mot(client: Client, cfg: config.Config, incident_id: str, urgency: str) -> str:
    """Khởi chạy workflow phân công của một tin, hoặc nhận ra đã có.

    Trả "dang_chay" (vừa tạo hoặc đã đang chạy: USE_EXISTING) | "da_xong" (đã chạy xong trước đó).
    """
    try:
        await client.start_workflow(
            PhanCongCuuHo.run,
            config.tham_so_phan_cong(cfg, incident_id, NGUOI_KHOI_CHAY),
            id=workflow_id(incident_id),
            task_queue=cfg.task_queue,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
            # Máy chủ Temporal xếp việc của tin khẩn lên trước khi worker bận (activity thừa hưởng)
            priority=Priority(priority_key=uu_tien(urgency)),
        )
    except WorkflowAlreadyStartedError:
        return "da_xong"  # vd điều phối đã khởi chạy tay và luồng đã kết thúc
    return "dang_chay"


class BoKhoiChay:
    def __init__(self, pool: asyncpg.Pool, client: Client, cfg: config.Config) -> None:
        self._pool = pool
        self._client = client
        self._cfg = cfg

    async def quet(self) -> int:
        """Một lượt: khởi chạy tối đa LO tin đang chờ. Trả số dòng đã lấy."""
        async with self._pool.acquire() as conn, conn.transaction():
            rows = await conn.fetch(SQL_LAY, LO)
            for r in rows:
                try:
                    kq = await khoi_chay_mot(self._client, self._cfg, r["id"], r["urgency"])
                except Exception as e:  # Temporal không với tới: để lần quét sau
                    log.warning("chưa khởi chạy được phân công tin %s: %s", r["id"], e)
                    await conn.execute(
                        "UPDATE cuu_tro.assignment_queue SET attempts = attempts + 1, last_error = $2 WHERE incident_id = $1",
                        r["id"], str(e)[:500],
                    )
                    continue
                await conn.execute(
                    """UPDATE cuu_tro.assignment_queue
                          SET started_at = now(), attempts = attempts + 1, last_error = NULL
                        WHERE incident_id = $1""",
                    r["id"],
                )
                log.info("tự khởi chạy phân công tin %s (urgency %s): %s", r["id"], r["urgency"], kq)
        return len(rows)

    async def chay(self, dung: asyncio.Event) -> None:
        """Vòng chính: LISTEN + quét định kỳ cho tới khi `dung` được đặt."""
        co_tin = asyncio.Event()
        nghe: asyncpg.Connection | None = None
        try:
            while not dung.is_set():
                if nghe is None or nghe.is_closed():
                    nghe = await self._nghe(co_tin)
                co_tin.clear()
                try:
                    while await self.quet() == LO:
                        pass
                except Exception:
                    log.exception("lượt quét hàng đợi phân công lỗi")
                await _cho_mot(co_tin, dung, self._cfg.quet_giay)
        finally:
            if nghe is not None and not nghe.is_closed():
                await nghe.close()

    async def _nghe(self, co_tin: asyncio.Event) -> asyncpg.Connection | None:
        try:
            conn = await asyncpg.connect(self._cfg.db_url)
            await conn.add_listener(KENH_TIN_MOI, lambda *_: co_tin.set())
            log.info("LISTEN %s", KENH_TIN_MOI)
            return conn
        except Exception as e:  # quét định kỳ vẫn chạy, lượt sau thử nghe lại
            log.warning("không LISTEN được %s: %s", KENH_TIN_MOI, e)
            return None


async def _cho_mot(co_tin: asyncio.Event, dung: asyncio.Event, giay: int) -> None:
    viec = [asyncio.create_task(co_tin.wait()), asyncio.create_task(dung.wait())]
    try:
        await asyncio.wait(viec, timeout=giay, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for v in viec:
            v.cancel()
