# SPDX-License-Identifier: Apache-2.0
"""Temporal worker của apps/cuu-tro. Chạy: python -m cuu_tro_workflow.worker

Kết nối Temporal (gRPC, mạng nội bộ) và PostgreSQL bằng role dịch vụ cuu_tro_app; APP_DB_URL do
bao agent render từ OpenBao. Healthcheck: file HEALTH_FILE được ghi lại mỗi 10 giây khi worker chạy.
"""

import asyncio
import logging
import os
import signal
import time

import asyncpg
from temporalio.client import Client
from temporalio.worker import Worker

from . import config
from .activities import HoatDong, chao
from .workflows import Hello, PhanCongCuuHo

HEALTH_FILE = os.environ.get("HEALTH_FILE", "/tmp/worker-alive")
log = logging.getLogger("cuu-tro-worker")


async def _nhip_tim() -> None:
    # Chạy trong "async with worker" và bị hủy khi worker dừng
    while True:
        with open(HEALTH_FILE, "w") as f:
            f.write(str(int(time.time())))
        await asyncio.sleep(10)


async def main() -> None:
    cfg = config.load()
    if not cfg.db_url:
        raise SystemExit("Thiếu APP_DB_URL (bao agent chưa render bí mật?)")
    client = await Client.connect(cfg.temporal_address, namespace=cfg.temporal_namespace)
    pool = await asyncpg.create_pool(cfg.db_url, min_size=1, max_size=4)
    hd = HoatDong(pool)
    worker = Worker(
        client,
        task_queue=cfg.task_queue,
        workflows=[Hello, PhanCongCuuHo],
        activities=[chao, hd.doc_tin, hd.tim_doi_ung_vien, hd.gan_doi, hd.ket_thuc],
    )
    dung = asyncio.Event()
    loop = asyncio.get_running_loop()
    for s in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(s, dung.set)
    log.info("worker chạy: task queue %s, Temporal %s", cfg.task_queue, cfg.temporal_address)
    async with worker:
        nhip = asyncio.create_task(_nhip_tim())
        await dung.wait()
        nhip.cancel()
    await pool.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(main())
