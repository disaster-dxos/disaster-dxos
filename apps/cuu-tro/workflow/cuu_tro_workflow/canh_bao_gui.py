# SPDX-License-Identifier: Apache-2.0
"""Activity gửi thông báo cảnh báo vượt ngưỡng (#87), chạy trong worker.

Mỗi lần gọi là MỘT bước của MỘT đợt (canh_bao | nguy_hiem | ve_duoi_nguong):
  1. đọc tên + tọa độ trạm (role cuu_tro_app), dựng nội dung tiếng Việt (canh_bao.noi_dung);
  2. ghi hộp thư nội bộ cuu_tro.sensor_alert_notifications (migration 0010), UNIQUE (trạm, đợt, bước):
     activity chạy lại không tạo dòng thứ hai, dòng đã "da_gui" thì không gửi lại;
  3. kênh ngoài theo CANH_BAO_KENH: "gia-lap" (mặc định) không gửi đi đâu, hộp thư là nơi nhận;
     "telegram" gọi sendMessage của Bot API (token + chat id từ OpenBao secret/app/cuu-tro/telegram);
  4. đẩy sự kiện cuu-tro.dieu-phoi.canh-bao.<ma_tram> lên JetStream (Nats-Msg-Id theo trạm + đợt + bước),
     cầu nối thong_bao_cau_noi.py đưa lên web điều phối qua Centrifugo; rồi đánh dấu da_gui.
Lỗi tạm thời (mạng, 5xx, 429 của Telegram, CSDL) → raise để Temporal thử lại theo retry policy của
workflow; 429 đặt next_retry_delay theo retry_after. Lỗi cấu hình/không thử lại được (thiếu token,
400/401/403/404 từ Telegram) → ghi status "loi" + detail, raise non_retryable.
Gửi Telegram là "ít nhất một lần": worker chết sau khi Telegram nhận mà trước khi ghi da_gui thì lần thử
lại gửi thêm một tin (hiếm; hộp thư vẫn chỉ một dòng).
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

import asyncpg
import httpx
from temporalio import activity
from temporalio.exceptions import ApplicationError

from . import canh_bao
from .canh_bao import YeuCauGui

SQL_TRAM = """SELECT ST_X(location::geometry) AS kinh_do, ST_Y(location::geometry) AS vi_do
                FROM cuu_tro.sensors WHERE code = $1"""
SQL_GHI = """
INSERT INTO cuu_tro.sensor_alert_notifications (sensor_code, episode_at, step, previous_level, value, threshold,
                                                unit, observed_at, message, channel)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
ON CONFLICT (sensor_code, episode_at, step) DO UPDATE SET attempts = sensor_alert_notifications.attempts + 1
RETURNING id, status
"""
SQL_DANH_DAU = """UPDATE cuu_tro.sensor_alert_notifications SET status = $2, detail = $3,
                         sent_at = CASE WHEN $2 = 'da_gui' THEN now() END WHERE id = $1"""


def _luc(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


@dataclass(frozen=True)
class CauHinhGui:
    kenh: str = canh_bao.KENH_GIA_LAP
    telegram_api_url: str = "https://api.telegram.org"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    # Liên kết "Web điều phối" trong tin (URL công khai của gateway)
    web_url: str = "http://localhost:9080"


class GuiCanhBao:
    def __init__(self, pool: asyncpg.Pool, js, ch: CauHinhGui, http: httpx.AsyncClient | None = None) -> None:
        if ch.kenh not in canh_bao.KENH:
            raise ValueError(f"CANH_BAO_KENH phải là một trong {canh_bao.KENH}, nhận {ch.kenh!r}")
        self._pool, self._js, self._ch = pool, js, ch
        self._http = http

    async def _danh_dau(self, id_: int, trang_thai: str, chi_tiet: str | None = None) -> None:
        await self._pool.execute(SQL_DANH_DAU, id_, trang_thai, chi_tiet)

    async def _telegram(self, id_: int, text: str) -> str:
        ch = self._ch
        if not ch.telegram_bot_token or not ch.telegram_chat_id:
            await self._danh_dau(id_, "loi", "thiếu TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID (OpenBao secret/app/cuu-tro/telegram)")
            raise ApplicationError("CANH_BAO_KENH=telegram nhưng chưa cấu hình bot (OpenBao secret/app/cuu-tro/telegram)",
                                   non_retryable=True)
        http = self._http or httpx.AsyncClient(timeout=15)
        try:
            # Token nằm trong đường dẫn URL theo thiết kế của Bot API: không ghi URL hay lỗi httpx (có URL) ra log
            r = await http.post(f"{ch.telegram_api_url.rstrip('/')}/bot{ch.telegram_bot_token}/sendMessage",
                                json={"chat_id": ch.telegram_chat_id, "text": text,
                                      "disable_web_page_preview": True})
        except httpx.HTTPError as e:
            raise ApplicationError(f"không gọi được Telegram Bot API ({type(e).__name__})") from None
        finally:
            if self._http is None:
                await http.aclose()
        try:
            than = r.json()
        except ValueError:
            than = None
        if r.status_code == 200 and isinstance(than, dict) and than.get("ok"):
            return str((than.get("result") or {}).get("message_id", ""))
        thu_lai, cho = canh_bao.loi_telegram(r.status_code, than if isinstance(than, dict) else None)
        mo_ta = f"Telegram trả HTTP {r.status_code}: {(than or {}).get('description', '') if isinstance(than, dict) else ''}"[:300]
        if not thu_lai:
            await self._danh_dau(id_, "loi", mo_ta)
            raise ApplicationError(mo_ta, non_retryable=True)
        raise ApplicationError(mo_ta, next_retry_delay=timedelta(seconds=cho) if cho else None)

    @activity.defn(name="gui_canh_bao")
    async def gui_canh_bao(self, yc: YeuCauGui) -> str:
        """Trả "da_gui" | "da_gui_truoc" (activity chạy lại, bước này đã gửi xong)."""
        sk = yc.su_kien
        tram = await self._pool.fetchrow(SQL_TRAM, sk.ma_tram)
        text = canh_bao.noi_dung(yc, tram["kinh_do"] if tram else None, tram["vi_do"] if tram else None,
                                 self._ch.web_url)
        dong = await self._pool.fetchrow(
            SQL_GHI, sk.ma_tram, _luc(sk.dot), yc.buoc, sk.muc_truoc, Decimal(str(sk.gia_tri)),
            None if sk.nguong is None else Decimal(str(sk.nguong)), sk.don_vi, _luc(sk.thoi_diem), text, self._ch.kenh)
        if dong["status"] == "da_gui":
            return "da_gui_truoc"
        chi_tiet = None
        if self._ch.kenh == canh_bao.KENH_TELEGRAM:
            chi_tiet = f"telegram message_id {await self._telegram(dong['id'], text)}"
        if self._js is None:
            raise ApplicationError("worker chạy không có NATS (NATS_URL trống)", non_retryable=True)
        await self._js.publish(
            f"{canh_bao.TIEN_TO_WEB}{sk.ma_tram}",
            json.dumps(canh_bao.su_kien_web(sk, yc.buoc), ensure_ascii=False).encode(),
            headers={"Nats-Msg-Id": canh_bao.ma_tin_web(sk, yc.buoc)},
        )
        await self._danh_dau(dong["id"], "da_gui", chi_tiet)
        activity.logger.info("Đã báo %s %s (đợt %s) qua %s", sk.ma_tram, yc.buoc, sk.dot, self._ch.kenh)
        return "da_gui"
