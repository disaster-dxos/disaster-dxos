# SPDX-License-Identifier: Apache-2.0
"""Bộ giả lập trạm cảm biến (#30, #84): gửi bản tin MQTT vào cổng MQTT của NATS (lõi).

Chạy (trong container, mật khẩu thiết bị do bao agent render):
  docker compose --profile core --profile app run --rm --no-deps cuu-tro-gia-lap python -m cuu_tro_workflow.gia_lap --mot-lan
  docker compose --profile gia-lap up -d cuu-tro-gia-lap          # chạy liên tục
Chạy trên máy host (cổng MQTT công bố ở 127.0.0.1:${NATS_MQTT_PORT}):
  MQTT_HOST=127.0.0.1 MQTT_PASSWORD=... uv run python -m cuu_tro_workflow.gia_lap --lien-tuc

Kịch bản:
  binh-thuong   dao động quanh mực nền của trạm, dưới ngưỡng cảnh báo
  vuot-nguong   nước lên dần từ mực nền tới trên ngưỡng nguy hiểm trong --so-buoc chu kỳ rồi giữ
                (--mot-lan: gửi ngay một bản tin trên ngưỡng nguy hiểm)
  tran-lu       trận lũ mẫu (#84): mỗi chu kỳ gửi giá trị của giờ kế tiếp trong du_lieu/tran_lu_mau.json
                (dâng → đỉnh → rút), hết chuỗi thì giữ giá trị cuối. --buoc-dau chọn giờ bắt đầu
                (--mot-lan gửi đúng giờ đó). --phat-lai gửi ngay cả chuỗi với thời điểm lùi về quá khứ
                mỗi bước một giờ, bước cuối là bây giờ (dựng lịch sử trận lũ trong vài giây).
Nhiễu của binh-thuong lấy từ random.Random(--seed): cùng seed cho cùng chuỗi giá trị (kiểm thử lặp lại được).
Mỗi bản tin gửi QoS 1 (NATS xác nhận PUBACK sau khi nhận) và in ra một dòng JSON trên stdout.
Thông tin trạm (mã, loại, ngưỡng, chuỗi trận lũ) nằm trong du_lieu/tran_lu_mau.json, là DỮ LIỆU GIẢ LẬP,
khớp seed apps/cuu-tro/db/seed/0001_xa_mau.sql; bộ giả lập không đọc CSDL (như thiết bị thật, nó chỉ
biết mã trạm của mình).
"""

import argparse
import json
import os
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from . import cam_bien


TEP_TRAN_LU = Path(__file__).with_name("du_lieu") / "tran_lu_mau.json"


@dataclass(frozen=True)
class TramGiaLap:
    ma: str
    kind: str
    muc_nen: float
    nguong_canh_bao: float
    nguong_nguy_hiem: float
    ten: str = ""
    kinh_do: float = 0.0
    vi_do: float = 0.0
    # Giá trị theo từng giờ của trận lũ mẫu (kịch bản tran-lu)
    chuoi: tuple[float, ...] = ()


def doc_tran_lu(duong_dan: Path = TEP_TRAN_LU) -> tuple[dict, list[TramGiaLap]]:
    """Đọc tệp trận lũ mẫu → (thông tin chung, danh sách trạm)."""
    with open(duong_dan, encoding="utf-8") as f:
        d = json.load(f)
    tram = [
        TramGiaLap(
            ma=t["ma"], kind=t["kind"], muc_nen=float(t["muc_nen"]),
            nguong_canh_bao=float(t["nguong_canh_bao"]), nguong_nguy_hiem=float(t["nguong_nguy_hiem"]),
            ten=t["ten"], kinh_do=float(t["kinh_do"]), vi_do=float(t["vi_do"]),
            chuoi=tuple(float(v) for v in t["chuoi"]),
        )
        for t in d["tram"]
    ]
    return {k: v for k, v in d.items() if k != "tram"}, tram


TRAN_LU, TRAM_MAU = doc_tran_lu()
KICH_BAN = ("binh-thuong", "vuot-nguong", "tran-lu")


def gia_tri_kich_ban(tram: TramGiaLap, kich_ban: str, buoc: int, so_buoc: int, rng: random.Random) -> float:
    """Giá trị đo ở chu kỳ `buoc` (0, 1, ...). Kết quả làm tròn 1 chữ số thập phân, không âm."""
    nhieu = rng.uniform(-1, 1) * 0.02 * tram.muc_nen
    if kich_ban == "binh-thuong":
        v = min(tram.muc_nen + nhieu, tram.nguong_canh_bao * 0.95)
    elif kich_ban == "vuot-nguong":
        dinh = tram.nguong_nguy_hiem * 1.05
        ti_le = 1.0 if so_buoc <= 1 else min(buoc / (so_buoc - 1), 1.0)
        v = tram.muc_nen + (dinh - tram.muc_nen) * ti_le
    elif kich_ban == "tran-lu":
        if not tram.chuoi:
            raise ValueError(f"trạm {tram.ma} không có chuỗi trận lũ mẫu")
        v = tram.chuoi[min(max(buoc, 0), len(tram.chuoi) - 1)]
    else:
        raise ValueError(f"kịch bản không có: {kich_ban}")
    return round(max(v, 0.0), 1)


def thoi_diem_phat_lai(bay_gio: datetime, so_buoc: int, buoc_gio: float) -> list[datetime]:
    """Thời điểm của `so_buoc` bản tin phát lại: cách nhau buoc_gio giờ, bản cuối đúng `bay_gio`."""
    return [bay_gio - timedelta(hours=buoc_gio * (so_buoc - 1 - i)) for i in range(so_buoc)]


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
    che_do.add_argument("--phat-lai", action="store_true",
                        help="tran-lu: gửi ngay cả chuỗi từ --buoc-dau, thời điểm lùi mỗi bước một giờ, rồi thoát")
    ap.add_argument("--kich-ban", choices=KICH_BAN, default=os.environ.get("GIA_LAP_KICH_BAN", "binh-thuong"))
    ap.add_argument("--tram", nargs="+", metavar="MA", help="mã trạm (mặc định: mọi trạm mẫu)")
    ap.add_argument("--chu-ky", type=float, default=float(os.environ.get("GIA_LAP_CHU_KY_GIAY", 10)),
                    help="giây giữa hai lần gửi (chế độ liên tục)")
    ap.add_argument("--so-buoc", type=int, default=6, help="số chu kỳ để nước lên tới đỉnh (vuot-nguong)")
    ap.add_argument("--buoc-dau", type=int, default=0, help="giờ bắt đầu trong chuỗi trận lũ (tran-lu)")
    ap.add_argument("--so-lan", type=int, default=0, help="số chu kỳ gửi rồi thoát (liên tục; 0 = không giới hạn)")
    ap.add_argument("--seed", type=int, default=int(os.environ["GIA_LAP_SEED"]) if os.environ.get("GIA_LAP_SEED") else None,
                    help="seed của nhiễu (mặc định ngẫu nhiên)")
    ap.add_argument("--host", default=os.environ.get("MQTT_HOST", "nats"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("MQTT_PORT", 1883)))
    a = ap.parse_args(argv)
    if a.phat_lai and a.kich_ban != "tran-lu":
        ap.error("--phat-lai chỉ dùng với --kich-ban tran-lu")

    tram = TRAM_MAU if not a.tram else [t for t in TRAM_MAU if t.ma in a.tram]
    if a.tram and len(tram) != len(set(a.tram)):
        ap.error(f"mã trạm không có trong trạm mẫu: {sorted(set(a.tram) - {t.ma for t in tram})}")
    rng = random.Random(a.seed)
    c = ket_noi(a.host, a.port, os.environ.get("MQTT_USERNAME"), os.environ.get("MQTT_PASSWORD"))

    def gui(t: TramGiaLap, gia_tri: float, thoi_diem: datetime) -> None:
        topic, payload = ban_tin(t, gia_tri, thoi_diem)
        info = c.publish(topic, payload, qos=1)
        info.wait_for_publish(timeout=10)
        print(json.dumps({"topic": topic, **json.loads(payload)}), flush=True)

    try:
        if a.phat_lai:
            for t in tram:
                buoc = range(max(a.buoc_dau, 0), len(t.chuoi))
                moc = thoi_diem_phat_lai(datetime.now(timezone.utc), len(buoc), float(TRAN_LU.get("buoc_gio", 1)))
                for b, td in zip(buoc, moc):
                    gui(t, gia_tri_kich_ban(t, a.kich_ban, b, a.so_buoc, rng), td)
            return 0
        lan = 0
        while True:
            for t in tram:
                # --mot-lan + vuot-nguong: nhảy thẳng tới bước cuối (trên ngưỡng nguy hiểm);
                # tran-lu: bắt đầu từ --buoc-dau
                if a.kich_ban == "tran-lu":
                    b = a.buoc_dau + lan
                else:
                    b = a.so_buoc if a.mot_lan else lan
                gui(t, gia_tri_kich_ban(t, a.kich_ban, b, a.so_buoc, rng), datetime.now(timezone.utc))
            lan += 1
            if a.mot_lan or (a.so_lan and lan >= a.so_lan):
                return 0
            time.sleep(a.chu_ky)
    except KeyboardInterrupt:
        return 0
    finally:
        c.disconnect()
        c.loop_stop()


if __name__ == "__main__":
    sys.exit(main())
