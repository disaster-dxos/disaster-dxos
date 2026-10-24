# SPDX-License-Identifier: Apache-2.0
"""Bản sao số trạm đo: NATS JetStream → Scorpio NGSI-LD (#85). Chạy: python -m cuu_tro_workflow.ban_sao_so

Consumer bền thứ hai trên stream CUU_TRO_CAM_BIEN ("ban-sao-so", độc lập với "ghi-csdl" của #30:
mỗi consumer nhận đủ mọi bản tin). Khi khởi động: khai báo stream + consumer theo
apps/cuu-tro/nats/streams.json. Với mỗi bản tin:
  1. phân tích + kiểm (cam_bien.phan_tich, như ghi-csdl); sai định dạng → bỏ hẳn (term);
  2. đọc trạm trong cuu_tro.sensors (tên, tọa độ, ngưỡng, ngsi_ld_id; role cuu_tro_app, migration
     0009); trạm không có hoặc đang tắt → bỏ;
  3. GET thực thể đang có trên Scorpio; bản tin cũ hơn lần đo trên đó → ack, không ghi (gửi bù,
     giao lại không làm bản sao số lùi về giá trị cũ);
  4. POST /ngsi-ld/v1/entityOperations/upsert (thay cả thực thể, @context nội tuyến từ
     apps/cuu-tro/ngsi-ld/context.jsonld) → ack.
Scorpio không trả lời / 5xx / 429 → nak có hẹn giờ tăng dần (ngsi_ld.tre_thu_lai), JetStream giao lại
tối đa max_deliver lần (Scorpio báo cả lỗi phía nó, vd hết kết nối CSDL, bằng 400, nên chỉ lỗi dữ liệu
BadRequestData / 413 / 415 / 422 mới bỏ ngay, term + log). Ghi lại cùng bản tin cho cùng thực thể.
Scorpio không có xác thực riêng: chỉ nằm trong mạng nội bộ, consumer gọi thẳng scorpio:9090; người
dùng đọc qua APISIX /ngsi-ld/v1/* (JWT, chỉ GET).
"""

import asyncio
import json
import logging
import os
import signal
import time
from datetime import datetime, timezone
from urllib.parse import quote

import asyncpg
import httpx
import nats
from nats.errors import TimeoutError as NatsTimeout

from . import cam_bien, config, ngsi_ld
from .cam_bien_consumer import doc_khai_bao, khai_bao_jetstream

HEALTH_FILE = os.environ.get("HEALTH_FILE", "/tmp/ban-sao-so-alive")
CONSUMER = "ban-sao-so"
LO_KEO = 50
log = logging.getLogger("cuu-tro-ban-sao-so")

SQL_TRAM = """SELECT code, name, kind, unit, ST_X(location::geometry) AS kinh_do, ST_Y(location::geometry) AS vi_do,
                     warning_threshold, danger_threshold, active, ngsi_ld_id
                FROM cuu_tro.sensors WHERE code = $1"""


class BanSaoSo:
    def __init__(self, doc_tram, http: httpx.AsyncClient, ctx: dict) -> None:
        # doc_tram(ma) -> ngsi_ld.Tram | None (async): tách khỏi asyncpg để kiểm thử không cần CSDL
        self._doc_tram = doc_tram
        self._http = http
        self._ctx = ctx

    async def _get(self, id_tt: str) -> dict | None:
        try:
            r = await self._http.get(f"/ngsi-ld/v1/entities/{quote(id_tt, safe=':')}",
                                     headers={"Accept": "application/json"})
        except httpx.HTTPError as e:
            raise ngsi_ld.LoiScorpio(f"không gọi được Scorpio: {e}", tam_thoi=True) from e
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            raise ngsi_ld.phan_loai_loi(r.status_code, r.text)
        return r.json()

    async def _upsert(self, tt: dict) -> None:
        try:
            r = await self._http.post("/ngsi-ld/v1/entityOperations/upsert", content=json.dumps([tt]),
                                      headers={"Content-Type": "application/ld+json"})
        except httpx.HTTPError as e:
            raise ngsi_ld.LoiScorpio(f"không gọi được Scorpio: {e}", tam_thoi=True) from e
        ngsi_ld.kiem_ket_qua_upsert(r.status_code, r.text)

    async def mot_ban_tin(self, msg) -> str:
        """Xử lý một bản tin; trả "ghi" | "cu" | "bo" | "loi" (để log/kiểm thử)."""
        try:
            bt = cam_bien.phan_tich(msg.subject, msg.data, datetime.now(timezone.utc))
            tram = await self._doc_tram(bt.ma_tram)
            if tram is None:
                raise cam_bien.BanTinKhongHopLe(f"trạm {bt.ma_tram} không có trong CSDL")
            cam_bien.kiem_tra_khop_tram(bt, tram.kind, tram.unit, tram.active)
        except cam_bien.BanTinKhongHopLe as e:
            log.warning("bỏ bản tin %s: %s", msg.subject, e)
            await msg.term()
            return "bo"
        except Exception:
            log.exception("lỗi đọc trạm cho %s, giao lại sau", msg.subject)
            await msg.nak(delay=5)
            return "loi"
        id_tt = ngsi_ld.id_thuc_the(tram)
        try:
            hien_tai = ngsi_ld.thoi_diem_hien_tai(await self._get(id_tt), tram.kind, self._ctx)
            if not ngsi_ld.can_ghi(bt, hien_tai):
                await msg.ack()
                log.info("bỏ qua %s: bản tin %s cũ hơn lần đo trên Scorpio %s", id_tt, bt.thoi_diem, hien_tai)
                return "cu"
            await self._upsert(ngsi_ld.thuc_the(tram, bt, self._ctx))
        except ngsi_ld.LoiScorpio as e:
            if not e.tam_thoi:
                log.error("bỏ bản tin %s: %s", msg.subject, e)
                await msg.term()
                return "bo"
            lan = getattr(getattr(msg, "metadata", None), "num_delivered", 1) or 1
            log.warning("chưa ghi được %s lên Scorpio (lần %s): %s, giao lại sau", id_tt, lan, e)
            await msg.nak(delay=ngsi_ld.tre_thu_lai(lan))
            return "loi"
        await msg.ack()
        log.info("đã cập nhật %s: %s %s lúc %s", id_tt, bt.gia_tri, bt.don_vi, bt.thoi_diem.isoformat())
        return "ghi"


def doc_tram_tu_pool(pool: asyncpg.Pool):
    async def doc(ma: str) -> ngsi_ld.Tram | None:
        r = await pool.fetchrow(SQL_TRAM, ma)
        if r is None:
            return None
        return ngsi_ld.Tram(
            ma=r["code"], ten=r["name"], kind=r["kind"], unit=r["unit"], kinh_do=r["kinh_do"], vi_do=r["vi_do"],
            nguong_canh_bao=r["warning_threshold"], nguong_nguy_hiem=r["danger_threshold"],
            active=r["active"], ngsi_ld_id=r["ngsi_ld_id"],
        )
    return doc


async def _nhip_tim() -> None:
    while True:
        with open(HEALTH_FILE, "w") as f:
            f.write(str(int(time.time())))
        await asyncio.sleep(10)


async def main() -> None:
    cfg = config.load()
    if not cfg.db_url or not cfg.nats_url:
        raise SystemExit("Thiếu APP_DB_URL hoặc NATS_URL (bao agent chưa render bí mật?)")
    ctx = ngsi_ld.doc_context(cfg.ngsi_ld_context_file)
    streams, consumers = doc_khai_bao(cfg.nats_streams_file)
    cua_minh = [(s, c) for s, c in consumers if c.durable_name == CONSUMER]
    if not cua_minh:
        raise SystemExit(f"streams.json không có consumer {CONSUMER}")
    nc = await nats.connect(cfg.nats_url, name="cuu-tro-ban-sao-so", max_reconnect_attempts=-1, reconnect_time_wait=2)
    js = nc.jetstream()
    await khai_bao_jetstream(js, streams, cua_minh)
    pool = await asyncpg.create_pool(cfg.db_url, min_size=1, max_size=2)
    stream, cc = cua_minh[0]
    psub = await js.pull_subscribe_bind(cc.durable_name, stream=stream)

    dung = asyncio.Event()
    loop = asyncio.get_running_loop()
    for s in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(s, dung.set)
    async with httpx.AsyncClient(base_url=cfg.ngsi_ld_url, timeout=10) as http:
        xu_ly = BanSaoSo(doc_tram_tu_pool(pool), http, ctx)
        nhip = asyncio.create_task(_nhip_tim())
        log.info("bản sao số chạy: %s/%s → %s", stream, cc.durable_name, cfg.ngsi_ld_url)
        while not dung.is_set():
            try:
                msgs = await psub.fetch(LO_KEO, timeout=5)
            except (NatsTimeout, asyncio.TimeoutError):
                continue
            except Exception:  # NATS đang kết nối lại...: thử lại, không để vòng kéo chết lặng lẽ
                log.exception("kéo bản tin lỗi")
                await asyncio.sleep(2)
                continue
            for m in msgs:
                await xu_ly.mot_ban_tin(m)
        nhip.cancel()
    await nc.drain()
    await pool.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(main())
