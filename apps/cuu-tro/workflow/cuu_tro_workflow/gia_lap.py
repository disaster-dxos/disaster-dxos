# SPDX-License-Identifier: Apache-2.0
"""Bộ giả lập trạm cảm biến (#30): gửi bản tin MQTT vào cổng MQTT của NATS (lõi).

Chạy (trong container, mật khẩu thiết bị do bao agent render):
  docker compose --profile core --profile app run --rm --no-deps cuu-tro-gia-lap python -m cuu_tro_workflow.gia_lap --mot-lan
  docker compose --profile gia-lap up -d cuu-tro-gia-lap          # chạy liên tục
Chạy trên máy host (cổng MQTT công bố ở 127.0.0.1:${NATS_MQTT_PORT}):
  MQTT_HOST=127.0.0.1 MQTT_PASSWORD=... uv run python -m cuu_tro_workflow.gia_lap --lien-tuc

Kịch bản:
  binh-thuong   dao động quanh mực nền của trạm, dưới ngưỡng cảnh báo
  vuot-nguong   nước lên dần từ mực nền tới trên ngưỡng nguy hiểm trong --so-buoc chu kỳ rồi giữ
                (--mot-lan: gửi ngay một bản tin trên ngưỡng nguy hiểm)
Mỗi bản tin gửi QoS 1 (NATS xác nhận PUBACK sau khi nhận) và in ra một dòng JSON trên stdout.
Thông tin trạm dưới đây là dữ liệu giả, khớp seed apps/cuu-tro/db/seed/0001_xa_mau.sql; bộ giả lập
không đọc CSDL (như thiết bị thật, nó chỉ biết mã trạm của mình).
"""

import argparse
import json
import os
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from . import cam_bien


@dataclass(frozen=True)
class TramGiaLap:
    ma: str
    kind: str
    muc_nen: float
    nguong_canh_bao: float
    nguong_nguy_hiem: float


TRAM_MAU = [
    TramGiaLap("AL-MN-01", "muc_nuoc", 320, 350, 450),
    TramGiaLap("AL-MN-02", "muc_nuoc", 210, 300, 400),
    TramGiaLap("AL-LM-01", "luong_mua", 20, 100, 200),
]
KICH_BAN = ("binh-thuong", "vuot-nguong")


def gia_tri_kich_ban(tram: TramGiaLap, kich_ban: str, buoc: int, so_buoc: int, rng: random.Random) -> float:
    """Giá trị đo ở chu kỳ `buoc` (0, 1, ...). Kết quả làm tròn 1 chữ số thập phân, không âm."""
    nhieu = rng.uniform(-1, 1) * 0.02 * tram.muc_nen
    if kich_ban == "binh-thuong":
        v = min(tram.muc_nen + nhieu, tram.nguong_canh_bao * 0.95)
    elif kich_ban == "vuot-nguong":
        dinh = tram.nguong_nguy_hiem * 1.05
        ti_le = 1.0 if so_buoc <= 1 else min(buoc / (so_buoc - 1), 1.0)
        v = tram.muc_nen + (dinh - tram.muc_nen) * ti_le
    else:
        raise ValueError(f"kịch bản không có: {kich_ban}")
    return round(max(v, 0.0), 1)


def ban_tin(tram: TramGiaLap, gia_tri: float, thoi_diem: datetime) -> tuple[str, bytes]:
    """(topic MQTT, payload JSON) theo quy ước trong cam_bien."""
    payload = {
        "ma_tram": tram.ma,
        "gia_tri": gia_tri,
        "don_vi": cam_bien.DAI_LUONG[cam_bien.KIND_SANG_DAI_LUONG[tram.kind]][1],
        "thoi_diem": thoi_diem.isoformat(timespec="milliseconds"),
    }
    return cam_bien.topic_mqtt(tram.ma, tram.kind), json.dumps(payload).encode()


def ket_noi(host: str, port: int, user: str | None, password: str | None) -> mqtt.Client:
    c = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=f"gia-lap-{os.getpid()}", protocol=mqtt.MQTTv311)
    if user:
        c.username_pw_set(user, password)
    ket_qua: dict = {}
    c.on_connect = lambda _c, _u, _f, rc, _p: ket_qua.setdefault("rc", rc)
    c.connect(host, port, keepalive=30)
    c.loop_start()
    han = time.monotonic() + 10
    while "rc" not in ket_qua and time.monotonic() < han:
        time.sleep(0.05)
    rc = ket_qua.get("rc")
    if rc is None or rc.is_failure:
        c.loop_stop()
        raise SystemExit(f"gia-lap: MQTT {host}:{port} từ chối kết nối: {rc}")
    return c


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gia_lap", description="Giả lập trạm cảm biến gửi MQTT")
    che_do = ap.add_mutually_exclusive_group()
    che_do.add_argument("--mot-lan", action="store_true", help="gửi một bản tin cho mỗi trạm rồi thoát")
    che_do.add_argument("--lien-tuc", action="store_true", help="gửi định kỳ đến khi dừng (mặc định)")
    ap.add_argument("--kich-ban", choices=KICH_BAN, default=os.environ.get("GIA_LAP_KICH_BAN", "binh-thuong"))
    ap.add_argument("--tram", nargs="+", metavar="MA", help="mã trạm (mặc định: mọi trạm mẫu)")
    ap.add_argument("--chu-ky", type=float, default=float(os.environ.get("GIA_LAP_CHU_KY_GIAY", 10)),
                    help="giây giữa hai lần gửi (chế độ liên tục)")
    ap.add_argument("--so-buoc", type=int, default=6, help="số chu kỳ để nước lên tới đỉnh (vuot-nguong)")
    ap.add_argument("--host", default=os.environ.get("MQTT_HOST", "nats"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("MQTT_PORT", 1883)))
    a = ap.parse_args(argv)

    tram = TRAM_MAU if not a.tram else [t for t in TRAM_MAU if t.ma in a.tram]
    if a.tram and len(tram) != len(set(a.tram)):
        ap.error(f"mã trạm không có trong trạm mẫu: {sorted(set(a.tram) - {t.ma for t in tram})}")
    rng = random.Random()
    c = ket_noi(a.host, a.port, os.environ.get("MQTT_USERNAME"), os.environ.get("MQTT_PASSWORD"))
    buoc = 0
    try:
        while True:
            for t in tram:
                # --mot-lan + vuot-nguong: nhảy thẳng tới bước cuối (trên ngưỡng nguy hiểm)
                b = a.so_buoc if a.mot_lan else buoc
                gia_tri = gia_tri_kich_ban(t, a.kich_ban, b, a.so_buoc, rng)
                topic, payload = ban_tin(t, gia_tri, datetime.now(timezone.utc))
                info = c.publish(topic, payload, qos=1)
                info.wait_for_publish(timeout=10)
                print(json.dumps({"topic": topic, **json.loads(payload)}), flush=True)
            if a.mot_lan:
                return 0
            buoc += 1
            time.sleep(a.chu_ky)
    except KeyboardInterrupt:
        return 0
    finally:
        c.disconnect()
        c.loop_stop()


if __name__ == "__main__":
    sys.exit(main())
