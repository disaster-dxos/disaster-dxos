# SPDX-License-Identifier: Apache-2.0
"""Bản công bố cho cộng đồng cong-dong/tram-do-lu (#112) không được lệch backend apps/cuu-tro.

So dữ liệu, @context, giá trị từng kịch bản, topic + payload, thực thể NGSI-LD, ví dụ; kiểm MQTT tối giản
với broker giả (socket) và upsert với HTTP server giả; mo_phong.py chỉ import thư viện chuẩn.
"""

import ast
import http.server
import importlib.util
import json
import random
import socket
import sys
import threading
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from cuu_tro_workflow import cam_bien as cb
from cuu_tro_workflow import gia_lap, ngsi_ld

GOC = Path(__file__).resolve().parents[4]
CONG_DONG = GOC / "cong-dong" / "tram-do-lu"
BAY_GIO = datetime(2026, 10, 24, 1, 0, tzinfo=timezone.utc)


def _nap():
    spec = importlib.util.spec_from_file_location("mo_phong", CONG_DONG / "mo_phong.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mp = _nap()
CTX = ngsi_ld.doc_context(str(GOC / "apps" / "cuu-tro" / "ngsi-ld" / "context.jsonld"))
_, TRAM_DICT = mp.doc_tran_lu()


def tram_backend(t: dict) -> ngsi_ld.Tram:
    return ngsi_ld.Tram(
        ma=t["ma"], ten=t["ten"], kind=t["kind"], unit=cb.DAI_LUONG[cb.KIND_SANG_DAI_LUONG[t["kind"]]][1],
        kinh_do=float(t["kinh_do"]), vi_do=float(t["vi_do"]),
        nguong_canh_bao=Decimal(str(t["nguong_canh_bao"])), nguong_nguy_hiem=Decimal(str(t["nguong_nguy_hiem"])),
        active=True, ngsi_ld_id=None)


# ---------- Dữ liệu, context, ánh xạ loại ----------
def test_du_lieu_va_context_trung_backend():
    assert json.loads((CONG_DONG / "du-lieu" / "tran-lu-mau.json").read_text(encoding="utf-8")) == \
        json.loads(gia_lap.TEP_TRAN_LU.read_text(encoding="utf-8"))
    assert mp.doc_context() == CTX


def test_loai_trung_backend():
    for kind, (dai_luong, don_vi, kieu, thuoc_tinh, unit_code) in mp.LOAI.items():
        assert cb.DAI_LUONG[dai_luong] == (kind, don_vi)
        assert ngsi_ld.LOAI[kind] == (kieu, thuoc_tinh, unit_code)
    assert set(mp.LOAI) == set(ngsi_ld.LOAI) and mp.KICH_BAN == gia_lap.KICH_BAN


# ---------- Giá trị, bản tin, thực thể ----------
@pytest.mark.parametrize("kich_ban", gia_lap.KICH_BAN)
def test_gia_tri_trung_backend_cung_seed(kich_ban):
    r1, r2 = random.Random(7), random.Random(7)
    for t_dict, t in zip(TRAM_DICT, gia_lap.TRAM_MAU):
        for buoc in range(-1, 60):
            assert mp.gia_tri(t_dict, kich_ban, buoc, 6, r1) == gia_lap.gia_tri_kich_ban(t, kich_ban, buoc, 6, r2)


def test_ban_tin_trung_backend_va_qua_kiem_tra_cua_loi():
    for t_dict, t in zip(TRAM_DICT, gia_lap.TRAM_MAU):
        topic, payload = mp.ban_tin(t_dict, 123.4, BAY_GIO)
        topic_be, payload_be = gia_lap.ban_tin(t, 123.4, BAY_GIO)
        assert topic == topic_be and json.dumps(payload).encode() == payload_be
        bt = cb.phan_tich(topic.replace("/", "."), json.dumps(payload).encode(), BAY_GIO)
        assert (bt.ma_tram, bt.kind, bt.gia_tri) == (t.ma, t.kind, Decimal("123.40"))
    assert mp.ban_tin(TRAM_DICT[0], 1.0, BAY_GIO, "xa-a")[0].startswith("xa-a/cam-bien/")


@pytest.mark.parametrize("gt", [0.0, 299.9, 300.0, 399.9, 400.0, 1080.0])
def test_thuc_the_trung_backend(gt):
    for t_dict in TRAM_DICT:
        tram = tram_backend(t_dict)
        bt = cb.BanTin(tram.ma, tram.kind, Decimal(str(gt)), tram.unit, BAY_GIO)
        assert mp.thuc_the(t_dict, gt, BAY_GIO, CTX) == ngsi_ld.thuc_the(tram, bt, CTX)


def test_thuc_the_khong_nguong_va_ngsi_ld_id():
    t = {**TRAM_DICT[0], "nguong_canh_bao": None, "nguong_nguy_hiem": None, "ngsi_ld_id": "urn:ngsi-ld:WaterLevelStation:X"}
    e = mp.thuc_the(t, 999.0, BAY_GIO, CTX)
    assert e["id"] == "urn:ngsi-ld:WaterLevelStation:X" and e["alertLevel"]["value"] == "binh_thuong"
    assert "warningThreshold" not in e and "dangerThreshold" not in e


def test_vi_du_sinh_lai_duoc_tu_mo_phong():
    tram = {t["ma"]: t for t in TRAM_DICT}
    gio = {"ma": "VD-GIO-01", "ten": "Trạm gió ví dụ (giả định)", "kind": "gio", "kinh_do": 108.25, "vi_do": 15.88,
           "nguong_canh_bao": 17, "nguong_nguy_hiem": 25}
    vd = {"water-level-station": (tram["QN-CL-01"], 450.0), "rain-gauge": (tram["AL-LM-01"], 120.0),
          "wind-station": (gio, 19.4)}
    for ten, (t, gt) in vd.items():
        tep = json.loads((CONG_DONG / "ngsi-ld" / "vi-du" / f"{ten}.jsonld").read_text(encoding="utf-8"))
        assert tep == mp.thuc_the(t, gt, BAY_GIO, CTX), ten


# ---------- Lịch gửi ----------
def test_phat_lai_mot_chu_ky_lui_moi_buoc_mot_gio():
    (chu_ky,) = list(mp.lich_gui(TRAM_DICT[:2], "tran-lu", mot_lan=False, phat_lai=True, buoc_dau=40, so_buoc=6,
                                 so_lan=0, rng=random.Random(1), bay_gio=lambda: BAY_GIO))
    assert len(chu_ky) == 2 * (len(TRAM_DICT[0]["chuoi"]) - 40)
    cua_tram_dau = [c for c in chu_ky if c[0] is TRAM_DICT[0]]
    assert [c[2] for c in cua_tram_dau] == gia_lap.thoi_diem_phat_lai(BAY_GIO, len(cua_tram_dau), 1.0)
    assert [c[1] for c in cua_tram_dau] == TRAM_DICT[0]["chuoi"][40:]


def test_lien_tuc_ngu_giua_hai_chu_ky_truoc_khi_lay_thoi_diem():
    su_kien = []
    lich = mp.lich_gui(TRAM_DICT[:1], "vuot-nguong", mot_lan=False, phat_lai=False, buoc_dau=0, so_buoc=3,
                       so_lan=3, rng=random.Random(1), bay_gio=lambda: su_kien.append("gio") or BAY_GIO,
                       ngu=lambda: su_kien.append("ngu"))
    gia = [c[0][1] for c in lich]
    assert su_kien == ["gio", "ngu", "gio", "ngu", "gio"]
    t = TRAM_DICT[0]
    assert gia[0] == float(t["muc_nen"]) and gia[-1] == round(t["nguong_nguy_hiem"] * 1.05, 1)


def test_mot_lan_vuot_nguong_tren_nguong_nguy_hiem():
    (chu_ky,) = list(mp.lich_gui(TRAM_DICT, "vuot-nguong", mot_lan=True, phat_lai=False, buoc_dau=0, so_buoc=6,
                                 so_lan=0, rng=random.Random(1), bay_gio=lambda: BAY_GIO))
    assert all(gt >= t["nguong_nguy_hiem"] for t, gt, _ in chu_ky)


# ---------- MQTT tối giản với broker giả ----------
_doc_goi = mp._doc_goi


def _broker_gia(nhan: list, connack_rc: int = 0):
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]

    def chay():
        conn, _ = srv.accept()
        srv.close()
        with conn:
            loai, than = _doc_goi(conn)
            nhan.append(("CONNECT", than))
            conn.sendall(bytes([0x20, 2, 0, connack_rc]))
            if connack_rc:
                return
            while True:
                try:
                    loai, than = _doc_goi(conn)
                except (ConnectionError, OSError):
                    return
                if loai == 0xE0:
                    nhan.append(("DISCONNECT", b""))
                    return
                n = int.from_bytes(than[:2], "big")
                topic, ma_goi, payload = than[2:2 + n].decode(), than[2 + n:4 + n], than[4 + n:]
                nhan.append((topic, (loai, int.from_bytes(ma_goi, "big"), payload)))
                conn.sendall(bytes([0x40, 2]) + ma_goi)

    th = threading.Thread(target=chay, daemon=True)
    th.start()
    return port, th


def test_mqtt_qos1_cho_puback_va_xac_thuc():
    nhan: list = []
    port, th = _broker_gia(nhan)
    c = mp.MQTT("127.0.0.1", port, "thiet-bi", "mk-gia")
    payload = json.dumps({"x": "é" * 200}).encode()  # > 127 byte: độ dài nhiều byte
    c.gui("cuu-tro/cam-bien/AL-MN-01/muc-nuoc", payload)
    c.gui("cuu-tro/cam-bien/AL-MN-02/muc-nuoc", b"{}")
    c.dong()
    th.join(5)
    connect = nhan[0][1]
    assert connect[:7] == b"\x00\x04MQTT\x04" and connect[7] == 0xC2  # 3.1.1, user + mật khẩu + clean session
    assert connect.endswith(b"\x00\x08thiet-bi\x00\x06mk-gia")
    assert nhan[1] == ("cuu-tro/cam-bien/AL-MN-01/muc-nuoc", (0x32, 1, payload))
    assert nhan[2] == ("cuu-tro/cam-bien/AL-MN-02/muc-nuoc", (0x32, 2, b"{}"))
    assert nhan[3][0] == "DISCONNECT"


def test_mqtt_bi_tu_choi_bao_loi():
    port, th = _broker_gia([], connack_rc=5)
    with pytest.raises(ConnectionError, match="CONNACK 5"):
        mp.MQTT("127.0.0.1", port, "thiet-bi", "sai")
    th.join(5)


def test_main_gui_mqtt_tu_dau_den_cuoi(monkeypatch, capsys):
    nhan: list = []
    port, th = _broker_gia(nhan)
    monkeypatch.setenv("MQTT_PASSWORD", "mk")
    assert mp.main(["--mqtt", f"127.0.0.1:{port}", "--mqtt-user", "u", "--kich-ban", "tran-lu", "--buoc-dau", "20",
                    "--mot-lan", "--tram", "AL-MN-01", "QN-CL-01"]) == 0
    th.join(5)
    goi = [x for x in nhan if x[0].startswith("cuu-tro/")]
    assert [g[0] for g in goi] == ["cuu-tro/cam-bien/AL-MN-01/muc-nuoc", "cuu-tro/cam-bien/QN-CL-01/muc-nuoc"]
    dong = [json.loads(x) for x in capsys.readouterr().out.splitlines()]
    assert [d["gia_tri"] for d in dong] == [470.0, TRAM_DICT[5]["chuoi"][20]]
    assert json.loads(goi[0][1][2]) == {k: v for k, v in dong[0].items() if k != "topic"}


# ---------- Upsert NGSI-LD với HTTP server giả ----------
def _http_gia(ma: int, nhan: list):
    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            nhan.append((self.path, dict(self.headers), json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
            self.send_response(ma)
            self.end_headers()
            if ma >= 400:
                self.wfile.write(b'{"title":"loi gia"}')

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_upsert_gui_dung_duong_dan_va_header():
    nhan: list = []
    srv = _http_gia(204, nhan)
    try:
        e = mp.thuc_the(TRAM_DICT[0], 400.0, BAY_GIO, CTX)
        assert mp.upsert(f"http://127.0.0.1:{srv.server_port}/", [e], token="tk") == 204
    finally:
        srv.shutdown()
    duong_dan, header, than = nhan[0]
    assert duong_dan == "/ngsi-ld/v1/entityOperations/upsert"
    assert header["Content-Type"] == "application/ld+json" and header["Authorization"] == "Bearer tk"
    assert than == [e]


def test_upsert_loi_http_bao_noi_dung():
    srv = _http_gia(400, [])
    try:
        with pytest.raises(RuntimeError, match="HTTP 400.*loi gia"):
            mp.upsert(f"http://127.0.0.1:{srv.server_port}", [{}])
    finally:
        srv.shutdown()


# ---------- CLI, phụ thuộc ----------
def test_ngsi_ld_in_thuc_the_sau_moi_chu_ky(capsys):
    assert mp.main(["--kich-ban", "tran-lu", "--buoc-dau", "20", "--so-lan", "2", "--chu-ky", "0",
                    "--ngsi-ld", "--tram", "AL-MN-01"]) == 0
    dong = [json.loads(x) for x in capsys.readouterr().out.splitlines()]
    assert [d["waterLevel"]["value"] for d in dong] == TRAM_DICT[0]["chuoi"][20:22]


def test_cli_tu_choi_tham_so_sai(capsys):
    with pytest.raises(SystemExit):
        mp.main(["--phat-lai"])
    with pytest.raises(SystemExit):
        mp.main(["--mot-lan", "--tram", "KHONG-CO"])
    assert "KHONG-CO" in capsys.readouterr().err


def test_mo_phong_chi_dung_thu_vien_chuan():
    cay = ast.parse((CONG_DONG / "mo_phong.py").read_text(encoding="utf-8"))
    goi = {a.name.split(".")[0] for n in ast.walk(cay) if isinstance(n, ast.Import) for a in n.names}
    goi |= {n.module.split(".")[0] for n in ast.walk(cay) if isinstance(n, ast.ImportFrom) and n.module}
    assert goi and goi <= set(sys.stdlib_module_names), goi - set(sys.stdlib_module_names)
