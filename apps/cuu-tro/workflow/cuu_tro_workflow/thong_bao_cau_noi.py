# SPDX-License-Identifier: Apache-2.0
"""Cầu nối NATS JetStream → Centrifugo (#68). Chạy: python -m cuu_tro_workflow.thong_bao_cau_noi

Khi khởi động: khai báo stream + consumer theo apps/cuu-tro/nats/streams.json (chỉ consumer có tên
bắt đầu "realtime-", deliver_policy "new": lần đầu không đẩy lại sự kiện cũ). Sau đó kéo từ từng
consumer bền, với mỗi bản tin:
  1. chuyển thành thông báo (thong_bao.chuyen_su_kien: danh sách trắng trường, không SĐT/tên);
     sai định dạng → bỏ hẳn (term);
  2. POST /api/publish của Centrifugo (mạng nội bộ, header X-API-Key) kèm idempotency_key = Nats-Msg-Id
     (hoặc stream:seq): giao lại cùng bản tin không tạo thông báo trùng;
  3. Centrifugo nhận → ack; lỗi mạng/5xx → nak có hẹn giờ, JetStream giao lại (max_deliver).
Không đọc CSDL. Bí mật: NATS_URL (user cuu-tro-app), CENTRIFUGO_API_KEY, do bao agent render.
Healthcheck: HEALTH_FILE ghi lại mỗi 10 giây.
"""

import asyncio
import logging
import os
import signal
import time

import httpx
import nats
from nats.errors import TimeoutError as NatsTimeout
from nats.js.errors import NotFoundError

from . import thong_bao
from .cam_bien_consumer import doc_khai_bao, khai_bao_jetstream

HEALTH_FILE = os.environ.get("HEALTH_FILE", "/tmp/thong-bao-alive")
TIEN_TO_CONSUMER = "realtime-"
LO_KEO = 50
# Consumer cũ đã thay bằng luồng thông báo qua Temporal (#87): xóa trên máy nâng cấp từ bản trước để
# không giữ bản tin chờ vô ích
CONSUMER_BO = (("CUU_TRO_CANH_BAO", "realtime-canh-bao"),)
log = logging.getLogger("cuu-tro-thong-bao")


class LoiCentrifugo(Exception):
    """Centrifugo không nhận lệnh publish (mạng, 5xx, lỗi trong body): giao lại sau."""


class CauNoi:
    def __init__(self, http: httpx.AsyncClient, api_key: str) -> None:
        self._http = http
        self._api_key = api_key

    async def publish(self, tb: thong_bao.ThongBao) -> None:
        try:
            r = await self._http.post("/api/publish", json=thong_bao.lenh_publish(tb),
                                      headers={"X-API-Key": self._api_key})
        except httpx.HTTPError as e:
            raise LoiCentrifugo(f"không gọi được Centrifugo: {e}") from e
        if r.status_code != 200:
            raise LoiCentrifugo(f"Centrifugo trả HTTP {r.status_code}")
        loi = r.json().get("error")
        if loi:
            raise LoiCentrifugo(f"Centrifugo báo lỗi {loi.get('code')}: {loi.get('message')}")

    async def mot_ban_tin(self, msg) -> str:
        """Xử lý một bản tin; trả "gui" | "bo" | "loi" (để log/kiểm thử)."""
        md = msg.metadata
        try:
            tb = thong_bao.chuyen_su_kien(msg.subject, msg.data, (msg.headers or {}).get("Nats-Msg-Id"),
                                          md.stream, md.sequence.stream)
        except thong_bao.SuKienKhongHopLe as e:
            log.warning("bỏ bản tin %s: %s", msg.subject, e)
            await msg.term()
            return "bo"
        try:
            await self.publish(tb)
        except LoiCentrifugo as e:
            log.warning("chưa đẩy được %s: %s, giao lại sau", tb.khoa, e)
            await msg.nak(delay=5)
            return "loi"
        await msg.ack()
        log.info("đã đẩy %s lên kênh %s", tb.du_lieu["loai"], tb.kenh)
        return "gui"


async def _nhip_tim() -> None:
    while True:
        with open(HEALTH_FILE, "w") as f:
            f.write(str(int(time.time())))
        await asyncio.sleep(10)


async def _keo(psub, cau_noi: CauNoi, dung: asyncio.Event) -> None:
    while not dung.is_set():
        try:
            msgs = await psub.fetch(LO_KEO, timeout=5)
        except (NatsTimeout, asyncio.TimeoutError):
            continue
        except Exception:  # NATS đang kết nối lại...: thử lại, không để luồng kéo chết lặng lẽ
            log.exception("kéo bản tin lỗi")
            await asyncio.sleep(2)
            continue
        for m in msgs:
            await cau_noi.mot_ban_tin(m)


async def main() -> None:
    nats_url = os.environ.get("NATS_URL", "")
    api_key = os.environ.get("CENTRIFUGO_API_KEY", "")
    if not nats_url or not api_key:
        raise SystemExit("Thiếu NATS_URL hoặc CENTRIFUGO_API_KEY (bao agent chưa render bí mật?)")
    streams, consumers = doc_khai_bao(os.environ.get("NATS_STREAMS_FILE", "/app/nats/streams.json"))
    cua_minh = [(s, c) for s, c in consumers if c.durable_name.startswith(TIEN_TO_CONSUMER)]
    if not cua_minh:
        raise SystemExit(f"streams.json không có consumer {TIEN_TO_CONSUMER}*")
    nc = await nats.connect(nats_url, name="cuu-tro-thong-bao", max_reconnect_attempts=-1, reconnect_time_wait=2)
    js = nc.jetstream()
    await khai_bao_jetstream(js, streams, cua_minh)
    for stream, ten in CONSUMER_BO:
        try:
            await js.delete_consumer(stream, ten)
            log.info("đã xóa consumer cũ %s/%s", stream, ten)
        except NotFoundError:
            pass

    dung = asyncio.Event()
    loop = asyncio.get_running_loop()
    for s in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(s, dung.set)
    async with httpx.AsyncClient(base_url=os.environ.get("CENTRIFUGO_API_URL", "http://centrifugo:8000"),
                                 timeout=5) as http:
        cau_noi = CauNoi(http, api_key)
        nhip = asyncio.create_task(_nhip_tim())
        viec = []
        for stream, cc in cua_minh:
            psub = await js.pull_subscribe_bind(cc.durable_name, stream=stream)
            viec.append(asyncio.create_task(_keo(psub, cau_noi, dung)))
            log.info("cầu nối chạy: %s/%s → Centrifugo", stream, cc.durable_name)
        await dung.wait()
        await asyncio.gather(*viec, return_exceptions=True)
        nhip.cancel()
    await nc.drain()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # Mỗi lần publish httpx ghi một dòng INFO: đã có dòng "đã đẩy ..." của cầu nối
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(main())
