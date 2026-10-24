# SPDX-License-Identifier: Apache-2.0
"""Bộ khởi chạy workflow CanhBaoVuotNguong (#87), chạy trong tiến trình worker.

Kéo consumer bền "canh-bao-temporal" (stream CUU_TRO_CANH_BAO, deliver_policy new: lần đầu không khởi
chạy cho các đợt cũ). Mỗi sự kiện (vuot_nguong / ve_duoi_nguong, có mã đợt "dot"):
  1. kiểm (canh_bao.doc_su_kien); sai → bỏ hẳn (term);
  2. signal-with-start workflow id canh-bao-<ma_tram>-<dot>: đợt đang chạy → nhận thêm sự kiện, chưa có →
     tạo và nhận sự kiện đầu tiên. Đợt đã kết thúc (về dưới ngưỡng / hết hạn) → Temporal từ chối chạy lại
     id đó (REJECT_DUPLICATE): sự kiện giao lại/gửi bù muộn không tạo đợt thứ hai;
  3. ack. Temporal chưa sẵn sàng → nak, JetStream giao lại sau 5 giây.
Khử trùng lặp theo bước nằm trong workflow (canh_bao.quyet_dinh) và hộp thư (UNIQUE ma_tram, dot, buoc).
"""

import asyncio
import json
import logging

from nats.errors import TimeoutError as NatsTimeout
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from . import canh_bao, config
from .canh_bao import ThamSoCanhBao
from .workflows import CanhBaoVuotNguong

CONSUMER = "canh-bao-temporal"
LO_KEO = 20
log = logging.getLogger("cuu-tro-canh-bao")


async def khoi_chay_mot(client: Client, task_queue: str, sk: canh_bao.SuKien, han_giay: int) -> str:
    """Signal-with-start workflow của đợt. Trả "gui" (đã đưa sự kiện vào đợt) | "da_xong" (đợt đã kết thúc)."""
    try:
        await client.start_workflow(
            CanhBaoVuotNguong.run,
            ThamSoCanhBao(ma_tram=sk.ma_tram, dot=sk.dot, han_giay=han_giay),
            id=canh_bao.workflow_id(sk.ma_tram, sk.dot),
            task_queue=task_queue,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            start_signal=canh_bao.SIGNAL_SU_KIEN,
            start_signal_args=[sk],
        )
    except WorkflowAlreadyStartedError:
        return "da_xong"
    return "gui"


class BoKhoiChayCanhBao:
    def __init__(self, client: Client, cfg: config.Config) -> None:
        self._client, self._cfg = client, cfg

    async def mot_ban_tin(self, msg) -> str:
        """Xử lý một sự kiện; trả "gui" | "da_xong" | "bo" | "loi" (để log/kiểm thử)."""
        try:
            sk = canh_bao.doc_su_kien(msg.subject, json.loads(msg.data))
        except (ValueError, UnicodeDecodeError) as e:  # SuKienKhongHopLe là ValueError
            log.warning("bỏ sự kiện %s: %s", msg.subject, e)
            await msg.term()
            return "bo"
        try:
            kq = await khoi_chay_mot(self._client, self._cfg.task_queue, sk, self._cfg.canh_bao_han_dot_giay)
        except Exception:
            log.exception("chưa khởi chạy được cảnh báo %s đợt %s, giao lại sau", sk.ma_tram, sk.dot)
            await msg.nak(delay=5)
            return "loi"
        await msg.ack()
        if kq == "da_xong":
            log.info("bỏ qua %s %s: đợt %s đã kết thúc", sk.ma_tram, sk.loai, sk.dot)
        else:
            log.info("đưa %s %s (%s) vào đợt %s", sk.ma_tram, sk.loai, sk.muc, sk.dot)
        return kq

    async def chay(self, js, dung: asyncio.Event) -> None:
        psub = await js.pull_subscribe_bind(CONSUMER, stream="CUU_TRO_CANH_BAO")
        log.info("bộ khởi chạy cảnh báo chạy: CUU_TRO_CANH_BAO/%s", CONSUMER)
        while not dung.is_set():
            try:
                msgs = await psub.fetch(LO_KEO, timeout=5)
            except (NatsTimeout, asyncio.TimeoutError):
                continue
            except Exception:  # NATS đang kết nối lại...: thử lại, không để vòng kéo chết lặng lẽ
                log.exception("kéo sự kiện cảnh báo lỗi")
                await asyncio.sleep(2)
                continue
            for m in msgs:
                await self.mot_ban_tin(m)
