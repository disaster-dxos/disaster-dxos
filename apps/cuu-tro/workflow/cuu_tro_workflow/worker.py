# SPDX-License-Identifier: Apache-2.0
"""Temporal worker của apps/cuu-tro. Chạy: python -m cuu_tro_workflow.worker

Kết nối Temporal (gRPC, mạng nội bộ) và PostgreSQL bằng role dịch vụ cuu_tro_app; APP_DB_URL do
bao agent render từ OpenBao. NATS (NATS_URL, user cuu-tro-app) để báo điều phối: khai báo stream theo
apps/cuu-tro/nats/streams.json khi khởi động. Cùng tiến trình chạy bộ khởi chạy tự động (#67,
khoi_chay.py) trừ khi PHAN_CONG_TU_DONG=0; bộ khởi chạy phát thông báo tin mới lên NATS (#68).
Cảnh báo vượt ngưỡng (#87): consumer canh-bao-temporal (canh_bao_khoi_chay.py) signal-with-start workflow
CanhBaoVuotNguong; activity gui_canh_bao gửi theo CANH_BAO_KENH (gia-lap | telegram).
Healthcheck: file HEALTH_FILE được ghi lại mỗi 10 giây khi worker chạy.
"""

import asyncio
import logging
import os
import signal
import time

import asyncpg
import nats
from temporalio.client import Client
from temporalio.worker import Worker

from . import config
from .activities import HoatDong, chao
from .cam_bien_consumer import doc_khai_bao, khai_bao_jetstream
from .canh_bao_gui import CauHinhGui, GuiCanhBao
from .canh_bao_khoi_chay import CONSUMER as CONSUMER_CANH_BAO
from .canh_bao_khoi_chay import BoKhoiChayCanhBao
from .khoi_chay import BoKhoiChay
from .workflows import CanhBaoVuotNguong, Hello, PhanCongCuuHo

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
    nc = js = None
    if cfg.nats_url:
        nc = await nats.connect(cfg.nats_url, name="cuu-tro-worker", max_reconnect_attempts=-1, reconnect_time_wait=2)
        js = nc.jetstream()
        # Stream + consumer của worker (canh-bao-temporal, #87); consumer cảm biến do cuu-tro-cam-bien,
        # consumer realtime-* do cầu nối thông báo khai báo
        streams, consumers = doc_khai_bao(cfg.nats_streams_file)
        await khai_bao_jetstream(js, streams, [(s, c) for s, c in consumers if c.durable_name == CONSUMER_CANH_BAO])
    else:
        log.warning("NATS_URL trống: activity bao_dieu_phoi sẽ báo lỗi")
    hd = HoatDong(pool, js)
    gui = GuiCanhBao(pool, js, CauHinhGui(kenh=cfg.canh_bao_kenh, telegram_api_url=cfg.telegram_api_url,
                                          telegram_bot_token=cfg.telegram_bot_token,
                                          telegram_chat_id=cfg.telegram_chat_id, web_url=cfg.gateway_public_url))
    if cfg.canh_bao_kenh == "telegram" and not (cfg.telegram_bot_token and cfg.telegram_chat_id):
        log.error("CANH_BAO_KENH=telegram nhưng OpenBao secret/app/cuu-tro/telegram chưa có bot_token/chat_id")
    worker = Worker(
        client,
        task_queue=cfg.task_queue,
        workflows=[Hello, PhanCongCuuHo, CanhBaoVuotNguong],
        activities=[chao, hd.doc_tin, hd.tim_doi_ung_vien, hd.gan_doi, hd.nhan_nhiem_vu, hd.go_doi,
                    hd.dung_tim, hd.bao_dieu_phoi, hd.ket_thuc, gui.gui_canh_bao],
    )
    dung = asyncio.Event()
    loop = asyncio.get_running_loop()
    for s in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(s, dung.set)
    log.info("worker chạy: task queue %s, Temporal %s", cfg.task_queue, cfg.temporal_address)
    async with worker:
        nhip = asyncio.create_task(_nhip_tim())
        tu_dong = asyncio.create_task(BoKhoiChay(pool, client, cfg, js).chay(dung)) if cfg.tu_dong else None
        canh = asyncio.create_task(BoKhoiChayCanhBao(client, cfg).chay(js, dung)) if js is not None else None
        log.info("cảnh báo vượt ngưỡng gửi qua kênh %s", cfg.canh_bao_kenh)
        await dung.wait()
        nhip.cancel()
        for t in (tu_dong, canh):
            if t is not None:
                await t
    if nc is not None:
        await nc.drain()
    await pool.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(main())
