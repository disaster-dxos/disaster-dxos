# SPDX-License-Identifier: Apache-2.0
"""Thông báo realtime (#68): chuyển sự kiện NATS → thông báo (danh sách trắng, không SĐT/tên),
cầu nối ack/nak/term theo phản hồi Centrifugo (giả), token kết nối, API cấp token theo vai trò."""

import asyncio
import dataclasses
import json
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from cuu_tro_workflow import config, thong_bao as tb
from cuu_tro_workflow.api import app
from cuu_tro_workflow.auth import HASURA_NS, XacThuc
from cuu_tro_workflow.cam_bien_consumer import doc_khai_bao
from cuu_tro_workflow.khoi_chay import BoKhoiChay
from cuu_tro_workflow.thong_bao_cau_noi import TIEN_TO_CONSUMER, CauNoi

STREAMS_JSON = Path(__file__).resolve().parents[2] / "nats" / "streams.json"
INC = "b0000000-0000-4000-8000-000000000004"
KHOA_HMAC = "khoa-thu-nghiem-chi-dung-trong-test"


# ---------- Chuyển sự kiện ----------
def test_can_xu_ly_chi_giu_truong_trong_danh_sach_trang():
    goc = {"incident_id": INC, "ly_do": "het_lan_giao", "urgency": "khan_cap", "so_lan_giao": 3,
           "workflow_id": f"phan-cong-{INC}", "mo_ta": "đã giao 3 lần", "luc": "2026-10-22T10:00:00+00:00",
           "reporter_phone": "0912345678", "reporter_name": "Nguyễn Văn A"}
    t = tb.chuyen_su_kien(f"cuu-tro.dieu-phoi.can-xu-ly.{INC}", json.dumps(goc).encode(), "run1:het_lan_giao",
                          "CUU_TRO_DIEU_PHOI", 7)
    assert t.kenh == "dieu-phoi"
    assert t.khoa == "CUU_TRO_DIEU_PHOI:run1:het_lan_giao" == t.du_lieu["id"]
    assert t.du_lieu == {"loai": "can_xu_ly", "id": t.khoa, "incident_id": INC, "ly_do": "het_lan_giao",
                         "urgency": "khan_cap", "so_lan_giao": 3, "mo_ta": "đã giao 3 lần",
                         "luc": "2026-10-22T10:00:00+00:00"}
    assert "0912345678" not in json.dumps(t.du_lieu) and "Nguyễn" not in json.dumps(t.du_lieu, ensure_ascii=False)


def test_chuoi_co_so_dang_sdt_bi_bo():
    goc = {"incident_id": INC, "ly_do": "khong_co_doi", "mo_ta": "gọi 0912345678 để hỏi"}
    t = tb.chuyen_su_kien(f"cuu-tro.dieu-phoi.can-xu-ly.{INC}", json.dumps(goc).encode(), None, "S", 9)
    assert t.du_lieu["mo_ta"] is None and t.khoa == "S:9"


def test_tin_moi_khu_hoi_tu_ham_phat():
    subject, du_lieu, msg_id = tb.tin_moi(INC, "cao", "2026-10-22T10:00:00+00:00")
    assert subject == f"cuu-tro.dieu-phoi.tin-moi.{INC}" and msg_id == f"tin-moi:{INC}"
    t = tb.chuyen_su_kien(subject, du_lieu, msg_id, "CUU_TRO_DIEU_PHOI", 1)
    assert t.du_lieu == {"loai": "tin_moi", "id": f"CUU_TRO_DIEU_PHOI:tin-moi:{INC}", "incident_id": INC,
                         "urgency": "cao", "luc": "2026-10-22T10:00:00+00:00"}


def test_canh_bao_vuot_nguong():
    goc = {"loai": "vuot_nguong", "ma_tram": "TRAM-01", "ten_tram": "Cầu Trắng", "dai_luong": "muc_nuoc",
           "muc": "nguy_hiem", "muc_truoc": "canh_bao", "gia_tri": 4.2, "nguong": 4.0, "don_vi": "m",
           "thoi_diem": "2026-10-22T10:00:00+00:00", "la": {"long": "nhau"}}
    t = tb.chuyen_su_kien("cuu-tro.canh-bao.cam-bien.TRAM-01", json.dumps(goc).encode(), "m1", "CUU_TRO_CANH_BAO", 2)
    assert t.du_lieu["loai"] == "canh_bao" and t.du_lieu["ma_tram"] == "TRAM-01"
    assert t.du_lieu["gia_tri"] == 4.2 and t.du_lieu["muc"] == "nguy_hiem" and "la" not in t.du_lieu


@pytest.mark.parametrize("subject,du_lieu", [
    ("cuu-tro.cam-bien.TRAM-01.muc_nuoc", b"{}"),                  # không phải sự kiện điều phối
    ("cuu-tro.dieu-phoi.can-xu-ly.khong-phai-uuid", b"{}"),
    ("cuu-tro.canh-bao.cam-bien.tram có dấu cách", b"{}"),
    (f"cuu-tro.dieu-phoi.tin-moi.{INC}", b"khong-phai-json"),
    (f"cuu-tro.dieu-phoi.tin-moi.{INC}", b"[1, 2]"),
    (f"cuu-tro.dieu-phoi.tin-moi.{INC}", json.dumps({"incident_id": "b0000000-0000-4000-8000-000000000005"}).encode()),
])
def test_ban_tin_sai_bi_tu_choi(subject, du_lieu):
    with pytest.raises(tb.SuKienKhongHopLe):
        tb.chuyen_su_kien(subject, du_lieu, None, "S", 1)


def test_lenh_publish_mang_idempotency_key():
    t = tb.chuyen_su_kien(*tb.tin_moi(INC, "thap", "x")[:2], None, "S", 3)
    assert tb.lenh_publish(t) == {"channel": "dieu-phoi", "data": t.du_lieu, "idempotency_key": "S:3"}


# ---------- Token ----------
def test_kenh_theo_vai_tro():
    assert tb.kenh_cua(frozenset({"dieu-phoi"})) == ["dieu-phoi"]
    assert tb.kenh_cua(frozenset({"quan-tri"})) == ["dieu-phoi"]
    assert tb.kenh_cua(frozenset({"cuu-ho", "tinh-nguyen", "offline_access"})) == []


def test_ky_token_hs256_co_iss_aud_han_ngan():
    t = tb.ky_token("user-1", ["dieu-phoi"], KHOA_HMAC, 300, bay_gio=1_000)
    c = jwt.decode(t, KHOA_HMAC, algorithms=["HS256"], audience="centrifugo", issuer="cuu-tro-api",
                   options={"verify_exp": False})
    assert c == {"sub": "user-1", "iat": 1_000, "exp": 1_300, "iss": "cuu-tro-api", "aud": "centrifugo",
                 "channels": ["dieu-phoi"]}
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(t, "khoa-khac-cung-du-dai-32-byte-tro-len", algorithms=["HS256"], audience="centrifugo", options={"verify_exp": False})


def test_ky_token_thieu_khoa_hoac_kenh():
    with pytest.raises(ValueError):
        tb.ky_token("u", ["dieu-phoi"], "", 300)
    with pytest.raises(ValueError):
        tb.ky_token("u", [], KHOA_HMAC, 300)


# ---------- API /realtime/token ----------
KHOA_RSA = rsa.generate_private_key(public_exponent=65537, key_size=2048)
ISS = "http://localhost:8080/realms/disaster"


def token_kc(sub: str, *vai_tro: str) -> str:
    now = int(time.time())
    return "Bearer " + jwt.encode(
        {"sub": sub, "iss": ISS, "iat": now, "exp": now + 300, "preferred_username": sub,
         "name": "Điều phối Mẫu", "email": "dp@example.invalid",
         HASURA_NS: {"x-hasura-allowed-roles": list(vai_tro), "x-hasura-user-id": sub}},
        KHOA_RSA, algorithm="RS256")


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("REALTIME_TOKEN_SECRET", KHOA_HMAC)
    monkeypatch.setenv("REALTIME_TOKEN_HAN_GIAY", "120")
    st = app.state
    st.xac_thuc = XacThuc(ISS, lay_khoa=lambda _t: KHOA_RSA.public_key())
    st.cfg = config.load()
    yield TestClient(app)
    delattr(st, "cfg")


def test_dieu_phoi_nhan_token_chi_co_sub_va_kenh(api):
    r = api.get("/realtime/token", headers={"Authorization": token_kc("dp-1", "dieu-phoi")})
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    body = r.json()
    assert body["han_giay"] == 120 and body["kenh"] == ["dieu-phoi"]
    c = jwt.decode(body["token"], KHOA_HMAC, algorithms=["HS256"], audience="centrifugo", issuer="cuu-tro-api")
    assert set(c) == {"sub", "iat", "exp", "iss", "aud", "channels"} and c["sub"] == "dp-1"
    assert c["exp"] - c["iat"] == 120


@pytest.mark.parametrize("vai_tro", [("cuu-ho",), ("tinh-nguyen",), ()])
def test_vai_khac_bi_403(api, vai_tro):
    assert api.get("/realtime/token", headers={"Authorization": token_kc("u", *vai_tro)}).status_code == 403


def test_khong_token_401(api):
    assert api.get("/realtime/token").status_code == 401


def test_chua_cau_hinh_khoa_503(api):
    app.state.cfg = dataclasses.replace(app.state.cfg, realtime_token_secret="")
    assert api.get("/realtime/token", headers={"Authorization": token_kc("dp", "dieu-phoi")}).status_code == 503


# ---------- Cầu nối ----------
class MsgGia:
    def __init__(self, subject: str, data: bytes, msg_id: str | None = None, seq: int = 1,
                 stream: str = "CUU_TRO_DIEU_PHOI"):
        self.subject, self.data = subject, data
        self.headers = {"Nats-Msg-Id": msg_id} if msg_id else None
        self.metadata = SimpleNamespace(stream=stream, sequence=SimpleNamespace(stream=seq))
        self.ket_qua: list[str] = []

    async def ack(self):
        self.ket_qua.append("ack")

    async def nak(self, delay=None):
        self.ket_qua.append("nak")

    async def term(self):
        self.ket_qua.append("term")


def chay_cau_noi(msg: MsgGia, tra_loi) -> tuple[str, list[httpx.Request]]:
    goi: list[httpx.Request] = []

    def xu_ly(req: httpx.Request) -> httpx.Response:
        goi.append(req)
        return tra_loi(req)

    async def _main():
        async with httpx.AsyncClient(base_url="http://centrifugo:8000", transport=httpx.MockTransport(xu_ly)) as h:
            return await CauNoi(h, "khoa-api").mot_ban_tin(msg)

    return asyncio.run(_main()), goi


def test_cau_noi_day_len_centrifugo_roi_ack():
    subject, du_lieu, msg_id = tb.tin_moi(INC, "cao", "x")
    msg = MsgGia(subject, du_lieu, msg_id)
    kq, goi = chay_cau_noi(msg, lambda _r: httpx.Response(200, json={"result": {"offset": 1}}))
    assert kq == "gui" and msg.ket_qua == ["ack"]
    (req,) = goi
    assert req.url.path == "/api/publish" and req.headers["X-API-Key"] == "khoa-api"
    body = json.loads(req.content)
    assert body["channel"] == "dieu-phoi" and body["idempotency_key"] == f"CUU_TRO_DIEU_PHOI:tin-moi:{INC}"


@pytest.mark.parametrize("tra_loi", [
    lambda _r: httpx.Response(500),
    lambda _r: httpx.Response(401),
    lambda _r: httpx.Response(200, json={"error": {"code": 100, "message": "internal"}}),
])
def test_cau_noi_loi_centrifugo_thi_nak(tra_loi):
    msg = MsgGia(*tb.tin_moi(INC, "cao", "x")[:2])
    kq, _ = chay_cau_noi(msg, tra_loi)
    assert kq == "loi" and msg.ket_qua == ["nak"]


def test_cau_noi_mat_ket_noi_thi_nak():
    def dut(_r):
        raise httpx.ConnectError("không tới được")
    msg = MsgGia(*tb.tin_moi(INC, "cao", "x")[:2])
    kq, _ = chay_cau_noi(msg, dut)
    assert kq == "loi" and msg.ket_qua == ["nak"]


def test_cau_noi_ban_tin_sai_thi_term_khong_goi_centrifugo():
    msg = MsgGia("cuu-tro.dieu-phoi.can-xu-ly.sai", b"{}")
    kq, goi = chay_cau_noi(msg, lambda _r: httpx.Response(200, json={"result": {}}))
    assert kq == "bo" and msg.ket_qua == ["term"] and not goi


# ---------- Bộ khởi chạy phát tin mới ----------
class JsGia:
    def __init__(self, loi: Exception | None = None):
        self.da_phat: list[tuple[str, bytes, dict]] = []
        self.loi = loi

    async def publish(self, subject, payload, headers=None):
        if self.loi:
            raise self.loi
        self.da_phat.append((subject, payload, headers))


def test_khoi_chay_phat_tin_moi_khong_du_lieu_ca_nhan():
    js = JsGia()
    bo = BoKhoiChay(None, None, None, js)
    assert asyncio.run(bo.bao_tin_moi(INC, "khan_cap")) is True
    ((subject, payload, headers),) = js.da_phat
    assert subject == f"cuu-tro.dieu-phoi.tin-moi.{INC}" and headers == {"Nats-Msg-Id": f"tin-moi:{INC}"}
    assert set(json.loads(payload)) == {"incident_id", "urgency", "luc"}


def test_khoi_chay_loi_nats_khong_chan_phan_cong():
    assert asyncio.run(BoKhoiChay(None, None, None, JsGia(ConnectionError("mất NATS"))).bao_tin_moi(INC, "cao")) is False
    assert asyncio.run(BoKhoiChay(None, None, None).bao_tin_moi(INC, "cao")) is False


# ---------- Khai báo consumer ----------
def test_consumer_realtime_chi_nhan_su_kien_moi():
    streams, consumers = doc_khai_bao(str(STREAMS_JSON))
    rt = {c.durable_name: (s, c) for s, c in consumers if c.durable_name.startswith(TIEN_TO_CONSUMER)}
    assert set(rt) == {"realtime-dieu-phoi", "realtime-canh-bao"}
    s, c = rt["realtime-dieu-phoi"]
    assert s == "CUU_TRO_DIEU_PHOI" and c.filter_subject == "cuu-tro.dieu-phoi.>"
    assert rt["realtime-canh-bao"][0] == "CUU_TRO_CANH_BAO"
    assert all(c.deliver_policy.value == "new" for _, c in rt.values())
    ghi = [c for _, c in consumers if c.durable_name == "ghi-csdl"]
    assert ghi and ghi[0].deliver_policy.value == "all"
    # Subject các loại thông báo nằm trong stream đã khai báo
    subj = {x for st in streams for x in st.subjects}
    assert {"cuu-tro.dieu-phoi.>", "cuu-tro.canh-bao.>"} <= subj
