# SPDX-License-Identifier: Apache-2.0
"""Consumer luồng cảm biến của apps/cuu-tro (#30). Chạy: python -m cuu_tro_workflow.cam_bien_consumer

Khi khởi động: tạo/cập nhật stream + consumer JetStream theo apps/cuu-tro/nats/streams.json.
Sau đó kéo bản tin từ consumer bền "ghi-csdl" (stream CUU_TRO_CAM_BIEN), với mỗi bản tin:
  1. phân tích + kiểm (cam_bien.phan_tich); sai định dạng/không khớp trạm → bỏ hẳn (term);
  2. trong MỘT transaction (role DB cuu_tro_app): thêm dòng sensor_readings (trùng trạm + thời điểm
     thì bỏ qua), cập nhật sensors.last_* nếu là lần đo mới nhất; nếu mức tăng lên canh_bao/nguy_hiem
     thì phát sự kiện lên cuu-tro.canh-bao.cam-bien.<ma_tram> (JetStream, Nats-Msg-Id chống trùng);
     mức về binh_thuong sau một đợt thì phát sự kiện ve_duoi_nguong (#87); mỗi sự kiện có mã đợt "dot"
     TRƯỚC khi commit; lỗi bất kỳ → rollback, nak để JetStream giao lại;
  3. ack.
Xử lý lại cùng một bản tin cho cùng kết quả (mức trước lấy từ lần đo liền trước trong chuỗi đo).

Lệnh phụ cho smoke test / gỡ lỗi (cần NATS_URL):
  python -m cuu_tro_workflow.cam_bien_consumer canh-bao-cuoi <ma_tram>   in sự kiện cảnh báo cuối
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone

import asyncpg
import nats
from nats.errors import TimeoutError as NatsTimeout
from nats.js.api import ConsumerConfig, DeliverPolicy, StreamConfig, StorageType
from nats.js.errors import NotFoundError

from . import cam_bien, config

HEALTH_FILE = os.environ.get("HEALTH_FILE", "/tmp/cam-bien-alive")
LO_KEO = 50
CONSUMER_GHI = "ghi-csdl"
# Đầu đợt (#87): lần đo trên ngưỡng sớm nhất sau lần đo bình thường gần nhất trước $2 (cùng transaction,
# dòng vừa ghi đã thấy). Dùng cho cả sự kiện vượt ngưỡng (dòng hiện tại trên ngưỡng) lẫn về dưới ngưỡng.
SQL_DAU_DOT = """
SELECT min(observed_at) FROM cuu_tro.sensor_readings
 WHERE sensor_id = $1 AND observed_at <= $2 AND level <> 'binh_thuong'
   AND observed_at > coalesce((SELECT max(observed_at) FROM cuu_tro.sensor_readings
                                WHERE sensor_id = $1 AND observed_at < $2 AND level = 'binh_thuong'),
                              '-infinity'::timestamptz)
"""
log = logging.getLogger("cuu-tro-cam-bien")


def doc_khai_bao(duong_dan: str) -> tuple[list[StreamConfig], list[tuple[str, ConsumerConfig]]]:
    """Đọc streams.json → cấu hình nats-py (thời gian giây, dung lượng byte, như file khai báo)."""
    with open(duong_dan, encoding="utf-8") as f:
        kb = json.load(f)
    streams = [
        StreamConfig(
            name=s["name"],
            description=s.get("description"),
            subjects=s["subjects"],
            storage=StorageType(s.get("storage", "file")),
            max_age=s.get("max_age"),
            max_bytes=s.get("max_bytes"),
            max_msg_size=s.get("max_msg_size", -1),
            duplicate_window=s.get("duplicate_window", 120),
            num_replicas=1,
        )
        for s in kb["streams"]
    ]
    consumers = [
        (
            c["stream"],
            ConsumerConfig(
                durable_name=c["durable_name"],
                description=c.get("description"),
                filter_subject=c.get("filter_subject"),
                ack_wait=c.get("ack_wait", 30),
                max_deliver=c.get("max_deliver", 5),
                max_ack_pending=c.get("max_ack_pending", 200),
                # "new": consumer tạo lần đầu chỉ nhận bản tin từ lúc đó (cầu nối realtime, #68)
                deliver_policy=DeliverPolicy(c.get("deliver_policy", "all")),
            ),
        )
        for c in kb["consumers"]
    ]
    return streams, consumers


async def khai_bao_jetstream(js, streams, consumers) -> None:
    """Tạo stream/consumer còn thiếu, cập nhật cái đã có cho khớp file khai báo (chạy lại không lỗi)."""
    for sc in streams:
        try:
            await js.stream_info(sc.name)
            await js.update_stream(sc)
            log.info("stream %s: đã cập nhật", sc.name)
        except NotFoundError:
            await js.add_stream(sc)
            log.info("stream %s: đã tạo", sc.name)
    for stream, cc in consumers:
        # add_consumer với durable đã có = cập nhật các trường được phép đổi
        await js.add_consumer(stream, cc)
        log.info("consumer %s/%s: OK", stream, cc.durable_name)


class XuLy:
    def __init__(self, pool: asyncpg.Pool, js) -> None:
        self.pool = pool
        self.js = js

    async def mot_ban_tin(self, msg) -> str:
        """Xử lý một bản tin; trả "ghi" | "trung" | "bo" (để log/kiểm thử)."""
        try:
            bt = cam_bien.phan_tich(msg.subject, msg.data, datetime.now(timezone.utc))
        except cam_bien.BanTinKhongHopLe as e:
            log.warning("bỏ bản tin %s: %s", msg.subject, e)
            await msg.term()
            return "bo"
        try:
            async with self.pool.acquire() as con, con.transaction():
                ket_qua = await self._ghi(con, bt)
        except cam_bien.BanTinKhongHopLe as e:
            log.warning("bỏ bản tin %s: %s", msg.subject, e)
            await msg.term()
            return "bo"
        except Exception:
            log.exception("lỗi xử lý %s, giao lại sau", msg.subject)
            await msg.nak(delay=5)
            return "loi"
        await msg.ack()
        return ket_qua

    async def _ghi(self, con: asyncpg.Connection, bt: cam_bien.BanTin) -> str:
        tram = await con.fetchrow(
            """SELECT id, name, kind, unit, warning_threshold, danger_threshold,
                      last_value, last_observed_at, active
                 FROM cuu_tro.sensors WHERE code = $1 FOR UPDATE""",
            bt.ma_tram,
        )
        if tram is None:
            raise cam_bien.BanTinKhongHopLe(f"trạm {bt.ma_tram} không có trong CSDL")
        cam_bien.kiem_tra_khop_tram(bt, tram["kind"], tram["unit"], tram["active"])
        nguong_cb, nguong_nh = tram["warning_threshold"], tram["danger_threshold"]
        muc = cam_bien.muc_canh_bao(bt.gia_tri, nguong_cb, nguong_nh)
        moi = await con.fetchval(
            """INSERT INTO cuu_tro.sensor_readings (sensor_id, observed_at, value, level)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (sensor_id, observed_at) DO NOTHING RETURNING id""",
            tram["id"], bt.thoi_diem, bt.gia_tri, muc,
        )
        # Mức của lần đo liền trước; chưa có chuỗi đo thì lấy lần đo cuối trên sensors (vd từ seed)
        muc_truoc = await con.fetchval(
            """SELECT level FROM cuu_tro.sensor_readings
                WHERE sensor_id = $1 AND observed_at < $2
                ORDER BY observed_at DESC LIMIT 1""",
            tram["id"], bt.thoi_diem,
        )
        if muc_truoc is None and tram["last_value"] is not None and tram["last_observed_at"] < bt.thoi_diem:
            muc_truoc = cam_bien.muc_canh_bao(tram["last_value"], nguong_cb, nguong_nh)
        la_moi_nhat = tram["last_observed_at"] is None or tram["last_observed_at"] <= bt.thoi_diem
        if la_moi_nhat:
            await con.execute(
                "UPDATE cuu_tro.sensors SET last_value = $2, last_observed_at = $3 WHERE id = $1",
                tram["id"], bt.gia_tri, bt.thoi_diem,
            )
        su_kien = None
        if cam_bien.can_phat_canh_bao(muc_truoc, muc, la_moi_nhat):
            dot = await con.fetchval(SQL_DAU_DOT, tram["id"], bt.thoi_diem)
            su_kien = cam_bien.su_kien_canh_bao(bt, tram["name"], muc_truoc, muc, nguong_cb, nguong_nh, dot)
        elif cam_bien.can_phat_ve_duoi_nguong(muc_truoc, muc, la_moi_nhat):
            # Đợt chỉ có trong chuỗi đo; mức trước lấy từ sensors.last_* (vd seed) thì không có đợt để đóng
            dot = await con.fetchval(SQL_DAU_DOT, tram["id"], bt.thoi_diem)
            if dot is not None:
                su_kien = cam_bien.su_kien_ve_duoi_nguong(bt, tram["name"], muc_truoc, nguong_cb, dot)
        if su_kien is not None:
            await self.js.publish(
                cam_bien.subject_canh_bao(bt.ma_tram),
                json.dumps(su_kien, ensure_ascii=False).encode(),
                headers={"Nats-Msg-Id": cam_bien.ma_su_kien(bt, muc)},
            )
            log.info("cảnh báo %s: %s → %s (%s %s), đợt %s", bt.ma_tram, muc_truoc, muc, bt.gia_tri, bt.don_vi,
                     su_kien["dot"])
        return "ghi" if moi is not None else "trung"


async def _nhip_tim() -> None:
    while True:
        with open(HEALTH_FILE, "w") as f:
            f.write(str(int(time.time())))
        await asyncio.sleep(10)


async def _ket_noi_nats(url: str):
    return await nats.connect(url, name="cuu-tro-cam-bien", max_reconnect_attempts=-1, reconnect_time_wait=2)


async def main() -> None:
    cfg = config.load()
    if not cfg.db_url or not cfg.nats_url:
        raise SystemExit("Thiếu APP_DB_URL hoặc NATS_URL (bao agent chưa render bí mật?)")
    streams, consumers = doc_khai_bao(cfg.nats_streams_file)
    # Consumer realtime-* do cầu nối thông báo (#68, thong_bao_cau_noi.py) khai báo và dùng
    consumers = [(s, c) for s, c in consumers if c.durable_name == CONSUMER_GHI]
    if not consumers:
        raise SystemExit(f"streams.json không có consumer {CONSUMER_GHI}")
    nc = await _ket_noi_nats(cfg.nats_url)
    js = nc.jetstream()
    await khai_bao_jetstream(js, streams, consumers)
    pool = await asyncpg.create_pool(cfg.db_url, min_size=1, max_size=2)
    stream, cc = consumers[0]
    psub = await js.pull_subscribe_bind(cc.durable_name, stream=stream)
    xu_ly = XuLy(pool, js)

    dung = asyncio.Event()
    loop = asyncio.get_running_loop()
    for s in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(s, dung.set)
    nhip = asyncio.create_task(_nhip_tim())
    log.info("consumer chạy: %s/%s", stream, cc.durable_name)
    while not dung.is_set():
        try:
            msgs = await psub.fetch(LO_KEO, timeout=5)
        except (NatsTimeout, asyncio.TimeoutError):
            # Không có bản tin trong 5 giây (nats-py có lúc báo asyncio.TimeoutError thường)
            continue
        for m in msgs:
            await xu_ly.mot_ban_tin(m)
    nhip.cancel()
    await nc.drain()
    await pool.close()


async def canh_bao_cuoi(ma_tram: str) -> int:
    cfg = config.load()
    nc = await _ket_noi_nats(cfg.nats_url)
    try:
        m = await nc.jetstream().get_last_msg("CUU_TRO_CANH_BAO", cam_bien.subject_canh_bao(ma_tram))
        print(m.data.decode())
        return 0
    except NotFoundError:
        print("{}")
        return 1
    finally:
        await nc.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if len(sys.argv) == 3 and sys.argv[1] == "canh-bao-cuoi":
        sys.exit(asyncio.run(canh_bao_cuoi(sys.argv[2])))
    asyncio.run(main())
