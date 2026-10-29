#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Bộ mô phỏng trạm đo lũ + mô hình NGSI-LD trạm đo, bản công bố cho cộng đồng (#112).

Chỉ cần Python 3.9+, KHÔNG cài thêm gì (MQTT 3.1.1 và HTTP viết bằng thư viện chuẩn). Dùng được độc lập với
Disaster DX-OS: thử dashboard, broker MQTT, NGSI-LD context broker, luồng IoT của bạn bằng trận lũ mẫu 48 giờ
của 9 trạm ở Quảng Nam, Đà Nẵng (DỮ LIỆU GIẢ LẬP: địa danh, tọa độ gần đúng là thật; mực nước, ngưỡng là giả định).

Đầu ra (chọn một):
  (mặc định)            in mỗi bản tin một dòng JSON (NDJSON) ra stdout: {"topic", "ma_tram", "gia_tri", "don_vi", "thoi_diem"}
  --ngsi-ld             in thực thể NGSI-LD (dạng chuẩn hóa, @context nội tuyến) của mỗi trạm sau mỗi chu kỳ
  --mqtt HOST[:PORT]    gửi MQTT QoS 1 (chờ PUBACK); user/mật khẩu: --mqtt-user, biến MQTT_PASSWORD
  --ngsi-ld-url URL     upsert thực thể vào NGSI-LD broker (POST <URL>/ngsi-ld/v1/entityOperations/upsert);
                        token (nếu broker cần): biến NGSI_LD_TOKEN

Kịch bản: binh-thuong (dưới ngưỡng), vuot-nguong (nước lên dần quá ngưỡng nguy hiểm), tran-lu (trận lũ mẫu).
Ví dụ:
  python3 mo_phong.py --kich-ban tran-lu --phat-lai                    # 48 giờ × 9 trạm, NDJSON
  python3 mo_phong.py --kich-ban tran-lu --buoc-dau 20 --mot-lan --ngsi-ld --tram QN-CL-01
  MQTT_PASSWORD=... python3 mo_phong.py --mqtt localhost:1883 --mqtt-user thiet-bi --lien-tuc --kich-ban tran-lu
Định dạng bản tin, topic, mô hình NGSI-LD: README.md cùng thư mục.

Logic giá trị, topic, thực thể NGSI-LD trùng với backend apps/cuu-tro của Disaster DX-OS (gia_lap.py, cam_bien.py,
ngsi_ld.py); pytest của repo so từng thực thể và từng giá trị (tests/test_cuu_tro_cong_dong.py).
"""

import argparse
import json
import os
import random
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

THU_MUC = Path(__file__).resolve().parent
TEP_TRAN_LU = THU_MUC / "du-lieu" / "tran-lu-mau.json"
TEP_CONTEXT = THU_MUC / "ngsi-ld" / "context.jsonld"

# kind → (đại lượng trên topic, đơn vị, type NGSI-LD, thuộc tính đo, unitCode UN/CEFACT)
LOAI = {
    "muc_nuoc": ("muc-nuoc", "cm", "WaterLevelStation", "waterLevel", "CMT"),
    "luong_mua": ("luong-mua", "mm", "RainGauge", "precipitation", "MMT"),
    "gio": ("gio", "m/s", "WindStation", "windSpeed", "MTS"),
}
KICH_BAN = ("binh-thuong", "vuot-nguong", "tran-lu")


# ---------------- Dữ liệu và giá trị ----------------
def doc_tran_lu(duong_dan=TEP_TRAN_LU):
    """Tệp trận lũ mẫu → (thông tin chung, danh sách trạm dạng dict)."""
    with open(duong_dan, encoding="utf-8") as f:
        d = json.load(f)
    return {k: v for k, v in d.items() if k != "tram"}, d["tram"]


def gia_tri(tram, kich_ban, buoc, so_buoc, rng):
    """Giá trị đo ở chu kỳ `buoc` (0, 1, …), làm tròn 1 chữ số, không âm. Gọi rng.uniform đúng một lần mỗi bản tin."""
    nen = float(tram["muc_nen"])
    nhieu = rng.uniform(-1, 1) * 0.02 * nen
    if kich_ban == "binh-thuong":
        v = min(nen + nhieu, float(tram["nguong_canh_bao"]) * 0.95)
    elif kich_ban == "vuot-nguong":
        dinh = float(tram["nguong_nguy_hiem"]) * 1.05
        ti_le = 1.0 if so_buoc <= 1 else min(buoc / (so_buoc - 1), 1.0)
        v = nen + (dinh - nen) * ti_le
    elif kich_ban == "tran-lu":
        chuoi = tram["chuoi"]
        v = float(chuoi[min(max(buoc, 0), len(chuoi) - 1)])
    else:
        raise ValueError(f"kịch bản không có: {kich_ban}")
    return round(max(v, 0.0), 1)


def ban_tin(tram, gt, luc, tien_to="cuu-tro"):
    """(topic MQTT, payload dict). Topic: <tiền tố>/cam-bien/<mã trạm>/<đại lượng>."""
    dai_luong, don_vi = LOAI[tram["kind"]][:2]
    return (f"{tien_to}/cam-bien/{tram['ma']}/{dai_luong}",
            {"ma_tram": tram["ma"], "gia_tri": gt, "don_vi": don_vi, "thoi_diem": luc.isoformat(timespec="milliseconds")})


def muc_canh_bao(gt, nguong_canh_bao, nguong_nguy_hiem):
    if nguong_nguy_hiem is not None and gt >= nguong_nguy_hiem:
        return "nguy_hiem"
    if nguong_canh_bao is not None and gt >= nguong_canh_bao:
        return "canh_bao"
    return "binh_thuong"


def doc_context(duong_dan=TEP_CONTEXT):
    with open(duong_dan, encoding="utf-8") as f:
        return json.load(f)["@context"]


def thuc_the(tram, gt, luc, ctx):
    """Thực thể NGSI-LD dạng chuẩn hóa của trạm sau lần đo (gt, luc), @context nội tuyến."""
    _, _, kieu, thuoc_tinh, unit_code = LOAI[tram["kind"]]
    thoi_diem = luc.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    canh_bao = tram.get("nguong_canh_bao")
    nguy_hiem = tram.get("nguong_nguy_hiem")
    canh_bao = None if canh_bao is None else float(canh_bao)
    nguy_hiem = None if nguy_hiem is None else float(nguy_hiem)
    e = {
        "id": tram.get("ngsi_ld_id") or f"urn:ngsi-ld:{kieu}:{tram['ma']}",
        "type": kieu,
        "name": {"type": "Property", "value": tram["ten"]},
        "stationCode": {"type": "Property", "value": tram["ma"]},
        "location": {"type": "GeoProperty", "value": {"type": "Point", "coordinates": [float(tram["kinh_do"]), float(tram["vi_do"])]}},
        thuoc_tinh: {"type": "Property", "value": float(gt), "unitCode": unit_code, "observedAt": thoi_diem},
        "alertLevel": {"type": "Property", "value": muc_canh_bao(gt, canh_bao, nguy_hiem), "observedAt": thoi_diem},
    }
    if canh_bao is not None:
        e["warningThreshold"] = {"type": "Property", "value": canh_bao, "unitCode": unit_code}
    if nguy_hiem is not None:
        e["dangerThreshold"] = {"type": "Property", "value": nguy_hiem, "unitCode": unit_code}
    e["@context"] = [ctx]
    return e


def thoi_diem_phat_lai(bay_gio, so_buoc, buoc_gio):
    """Thời điểm của `so_buoc` bản tin phát lại, cách nhau buoc_gio giờ, bản cuối đúng `bay_gio`."""
    return [bay_gio - timedelta(hours=buoc_gio * (so_buoc - 1 - i)) for i in range(so_buoc)]


def lich_gui(tram_ds, kich_ban, *, mot_lan, phat_lai, buoc_dau, so_buoc, so_lan, rng, bay_gio, buoc_gio=1.0,
             ngu=lambda: None):
    """Sinh từng chu kỳ: danh sách (tram, giá trị, thời điểm) theo đúng thứ tự gửi. Phát lại: một chu kỳ duy nhất.
    Liên tục: không dừng nếu so_lan = 0; gọi ngu() giữa hai chu kỳ, trước khi lấy thời điểm của chu kỳ sau."""
    if phat_lai:
        chu_ky = []
        for t in tram_ds:
            buoc = range(max(buoc_dau, 0), len(t["chuoi"]))
            for b, luc in zip(buoc, thoi_diem_phat_lai(bay_gio(), len(buoc), buoc_gio)):
                chu_ky.append((t, gia_tri(t, kich_ban, b, so_buoc, rng), luc))
        yield chu_ky
        return
    lan = 0
    while True:
        if lan:
            ngu()
        chu_ky = []
        for t in tram_ds:
            # vuot-nguong + --mot-lan: nhảy thẳng tới bước cuối (trên ngưỡng nguy hiểm); tran-lu: từ --buoc-dau
            b = buoc_dau + lan if kich_ban == "tran-lu" else (so_buoc if mot_lan else lan)
            chu_ky.append((t, gia_tri(t, kich_ban, b, so_buoc, rng), bay_gio()))
        yield chu_ky
        lan += 1
        if mot_lan or (so_lan and lan >= so_lan):
            return


# ---------------- MQTT 3.1.1 tối giản (CONNECT, PUBLISH QoS 1, DISCONNECT) ----------------
def _do_dai(n):
    out = bytearray()
    while True:
        b, n = n % 128, n // 128
        out.append(b | 0x80 if n else b)
        if not n:
            return bytes(out)


def _chuoi(s):
    b = s.encode("utf-8")
    return len(b).to_bytes(2, "big") + b


def _goi(loai, than):
    return bytes([loai]) + _do_dai(len(than)) + than


def _doc_goi(sock):
    dau = sock.recv(1)
    if not dau:
        raise ConnectionError("broker đóng kết nối")
    n, nhan = 0, 1
    while True:
        bb = sock.recv(1)
        if not bb:
            raise ConnectionError("broker đóng kết nối giữa gói")
        b = bb[0]
        n += (b & 0x7F) * nhan
        nhan *= 128
        if not b & 0x80:
            break
    than = b""
    while len(than) < n:
        phan = sock.recv(n - len(than))
        if not phan:
            raise ConnectionError("broker đóng kết nối giữa gói")
        than += phan
    return dau[0], than


class MQTT:
    def __init__(self, host, port, user=None, password=None, client_id=None, timeout=10.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        co = 0x02 | (0xC0 if user else 0)  # clean session (+ username, password)
        than = _chuoi("MQTT") + bytes([4, co]) + (60).to_bytes(2, "big") + _chuoi(client_id or f"mo-phong-{os.getpid()}")
        if user:
            than += _chuoi(user) + _chuoi(password or "")
        self.sock.sendall(_goi(0x10, than))
        loai, tl = _doc_goi(self.sock)
        if loai != 0x20 or len(tl) < 2 or tl[1] != 0:
            raise ConnectionError(f"broker từ chối kết nối (CONNACK {tl[1] if len(tl) > 1 else '?'})")
        self.ma_goi = 0

    def gui(self, topic, payload):
        """PUBLISH QoS 1 rồi chờ PUBACK đúng mã gói."""
        self.ma_goi = self.ma_goi % 65535 + 1
        self.sock.sendall(_goi(0x32, _chuoi(topic) + self.ma_goi.to_bytes(2, "big") + payload))
        while True:
            loai, tl = _doc_goi(self.sock)
            if loai >> 4 == 4 and int.from_bytes(tl[:2], "big") == self.ma_goi:
                return

    def dong(self):
        try:
            self.sock.sendall(b"\xe0\x00")
        finally:
            self.sock.close()


# ---------------- NGSI-LD broker ----------------
def upsert(url, thuc_the_ds, token=None, timeout=15.0):
    """POST /ngsi-ld/v1/entityOperations/upsert (thay cả thực thể). Trả mã HTTP; lỗi HTTP → ném kèm nội dung."""
    req = urllib.request.Request(
        url.rstrip("/") + "/ngsi-ld/v1/entityOperations/upsert",
        data=json.dumps(thuc_the_ds, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/ld+json", **({"Authorization": f"Bearer {token}"} if token else {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"NGSI-LD broker trả HTTP {e.code}: {e.read()[:300].decode('utf-8', 'replace')}") from e


# ---------------- CLI ----------------
def main(argv=None):
    ap = argparse.ArgumentParser(prog="mo_phong.py", description="Mô phỏng trạm đo lũ (MQTT, NDJSON, NGSI-LD)")
    che_do = ap.add_mutually_exclusive_group()
    che_do.add_argument("--mot-lan", action="store_true", help="một bản tin mỗi trạm rồi thoát")
    che_do.add_argument("--lien-tuc", action="store_true", help="gửi định kỳ (mặc định)")
    che_do.add_argument("--phat-lai", action="store_true", help="tran-lu: gửi ngay cả chuỗi, thời điểm lùi mỗi bước một giờ")
    ap.add_argument("--kich-ban", choices=KICH_BAN, default="binh-thuong")
    ap.add_argument("--tram", nargs="+", metavar="MA", help="mã trạm (mặc định: cả 9 trạm)")
    ap.add_argument("--chu-ky", type=float, default=10.0, help="giây giữa hai chu kỳ (liên tục)")
    ap.add_argument("--so-buoc", type=int, default=6, help="số chu kỳ nước lên tới đỉnh (vuot-nguong)")
    ap.add_argument("--buoc-dau", type=int, default=0, help="giờ bắt đầu trong trận lũ mẫu (tran-lu)")
    ap.add_argument("--so-lan", type=int, default=0, help="số chu kỳ rồi thoát (0 = không giới hạn)")
    ap.add_argument("--seed", type=int, help="seed nhiễu: cùng seed cho cùng chuỗi")
    ap.add_argument("--tien-to", default="cuu-tro", help="tiền tố topic MQTT (mặc định cuu-tro)")
    dau_ra = ap.add_mutually_exclusive_group()
    dau_ra.add_argument("--ngsi-ld", action="store_true", help="in thực thể NGSI-LD của mỗi trạm sau mỗi chu kỳ (thay NDJSON)")
    dau_ra.add_argument("--mqtt", metavar="HOST[:PORT]", help="gửi MQTT QoS 1")
    dau_ra.add_argument("--ngsi-ld-url", metavar="URL", help="upsert vào NGSI-LD broker sau mỗi chu kỳ")
    ap.add_argument("--mqtt-user", default=os.environ.get("MQTT_USERNAME"), help="user MQTT (mật khẩu: biến MQTT_PASSWORD)")
    a = ap.parse_args(argv)
    if a.phat_lai and a.kich_ban != "tran-lu":
        ap.error("--phat-lai chỉ dùng với --kich-ban tran-lu")

    chung, tram_ds = doc_tran_lu()
    if a.tram:
        thieu = sorted(set(a.tram) - {t["ma"] for t in tram_ds})
        if thieu:
            ap.error(f"mã trạm không có trong dữ liệu mẫu: {thieu}")
        tram_ds = [t for t in tram_ds if t["ma"] in a.tram]
    ctx = doc_context()
    lich = lich_gui(tram_ds, a.kich_ban, mot_lan=a.mot_lan, phat_lai=a.phat_lai, buoc_dau=a.buoc_dau,
                    so_buoc=a.so_buoc, so_lan=a.so_lan, rng=random.Random(a.seed),
                    bay_gio=lambda: datetime.now(timezone.utc), buoc_gio=float(chung.get("buoc_gio", 1)),
                    ngu=lambda: time.sleep(a.chu_ky))
    mqtt = None
    if a.mqtt:
        host, _, port = a.mqtt.rpartition(":") if ":" in a.mqtt else (a.mqtt, "", "1883")
        mqtt = MQTT(host, int(port), a.mqtt_user, os.environ.get("MQTT_PASSWORD"))
    try:
        for chu_ky in lich:
            cuoi = {}
            for t, gt, luc in chu_ky:
                topic, payload = ban_tin(t, gt, luc, a.tien_to)
                cuoi[t["ma"]] = (t, gt, luc)
                if mqtt:
                    mqtt.gui(topic, json.dumps(payload).encode())
                if not a.ngsi_ld:
                    print(json.dumps({"topic": topic, **payload}, ensure_ascii=False), flush=True)
            thuc_the_ds = [thuc_the(*v, ctx) for v in cuoi.values()]
            if a.ngsi_ld:
                for e in thuc_the_ds:
                    print(json.dumps(e, ensure_ascii=False), flush=True)
            if a.ngsi_ld_url and thuc_the_ds:
                upsert(a.ngsi_ld_url, thuc_the_ds, os.environ.get("NGSI_LD_TOKEN"))
                print(f"đã upsert {len(thuc_the_ds)} thực thể", file=sys.stderr, flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        if mqtt:
            mqtt.dong()
    return 0


if __name__ == "__main__":
    sys.exit(main())
