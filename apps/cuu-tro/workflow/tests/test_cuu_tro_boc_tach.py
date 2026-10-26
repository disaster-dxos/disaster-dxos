# SPDX-License-Identifier: Apache-2.0
"""AI bóc tách tin kêu cứu (#102): bộ luật gia-lap, chống bịa khi ghép kết quả mô hình, hai nhà cung cấp HTTP
(Ollama, OpenAI-compatible) qua máy chủ giả httpx.MockTransport, dự phòng khi mô hình lỗi, cấu hình
LLM_PROVIDER/LLM_MODEL và endpoint POST /ai/boc-tach (quyền, Poka-yoke, kiểm trước tin trùng, không ghi SĐT
ra log). Không cần mô hình thật: CI không kéo Qwen2.5 7B.
"""

import asyncio
import functools
import json
import logging
import time
from pathlib import Path

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from cuu_tro_workflow import boc_tach, config
from cuu_tro_workflow.api import app
from cuu_tro_workflow.auth import HASURA_NS, XacThuc

MAU = json.loads((Path(boc_tach.__file__).parent / "du_lieu" / "tin_keu_cuu_mau.json").read_text())
TIN = ("Tôi là Nguyễn Văn An ở tổ 5 phường Hòa Khánh, nhà có 3 người già bị kẹt, cần thuốc. "
       "Gọi 0935 111 222. Vị trí 16.0712, 108.1503")


# ---------------- Bộ luật (gia-lap) ----------------
@pytest.mark.parametrize("m", MAU, ids=[f"mau-{i}" for i in range(len(MAU))])
def test_bo_luat_tren_tin_mau(m):
    d = boc_tach.bo_luat(m["van_ban"])
    for k, v in m["mong_doi"].items():
        if k == "nhu_cau_co":
            assert set(v) <= set(d.nhu_cau), (k, d.nhu_cau)
        elif k == "dia_chi_co":
            assert d.address_text and v in d.address_text, (k, d.address_text)
        else:
            assert getattr(d, k) == v, (k, getattr(d, k))


def test_bo_dau():
    assert boc_tach.bo_dau("Ngập Tới MÁI, Đà Nẵng") == "ngap toi mai, da nang"


@pytest.mark.parametrize("van_ban, mong_doi", [
    ("gọi 0905 123 456 hoặc 0905.123.456", ["0905123456"]),
    ("+84 935-111-222", ["0935111222"]),
    ("84935111222", ["0935111222"]),
    # 0123… không phải di động; 11 số liền không phải SĐT
    ("0123456789 và 090512345678", []),
    # Số có nhãn "SĐT" xếp trước số xuất hiện trước
    ("con tôi 0912000111 ở xa, sđt nhà 0905000222", ["0905000222", "0912000111"]),
])
def test_tim_sdt(van_ban, mong_doi):
    assert boc_tach.tim_sdt(van_ban) == mong_doi


@pytest.mark.parametrize("van_ban, mong_doi", [
    ("vị trí 16.0712, 108.1503", (16.0712, 108.1503)),
    ("https://maps.example/@16.0712,108.1503,17z", (16.0712, 108.1503)),
    # Viết "kinh độ, vĩ độ" thì đổi chỗ
    ("108.2021, 16.0544", (16.0544, 108.2021)),
    ("16.071 108.150", None),  # ít hơn 4 chữ số thập phân: không chắc là tọa độ
    ("giá 120.000, 45.500 đồng", None),
])
def test_tim_toa_do(van_ban, mong_doi):
    assert boc_tach.tim_toa_do(van_ban) == mong_doi


@pytest.mark.parametrize("van_ban, so", [
    ("nhà có 5 người", 5), ("ba người mắc kẹt", 3), ("2 cụ già và 1 cháu nhỏ", 3), ("12 hộ dân", None),
    ("có 5 nguoi trong do 2 tre em", 5), ("3 ngày chưa có điện", None),
])
def test_so_nguoi(van_ban, so):
    assert boc_tach.tim_so_nguoi(boc_tach.bo_dau(van_ban)) == so


@pytest.mark.parametrize("van_ban, muc", [
    ("nước ngập tới mái", "khan_cap"), ("bi lu cuon", "khan_cap"), ("có em bé", "cao"),
    ("cần hỗ trợ ít nước", "trung_binh"), ("xin tiếp tế gạo", "thap"),
])
def test_muc_khan_cap(van_ban, muc):
    assert boc_tach.tim_muc_khan_cap(boc_tach.bo_dau(van_ban)) == muc


def test_dia_chi_khong_nham_tu_thuong():
    # "xa quá", "mưa to", "áp thấp": từ địa chỉ ngắn nhưng chữ sau viết thường → không phải địa chỉ
    assert boc_tach.tim_dia_chi("mưa to quá, xa quá, áp thấp nhiệt đới") is None
    assert boc_tach.tim_dia_chi("Nhà ở thôn 3, xã Hòa Tiến, nước ngập") == "thôn 3, xã Hòa Tiến"


def test_mo_ta_che_sdt_va_gioi_han():
    mo_ta = boc_tach.mo_ta_tu_van_ban("Cứu\x07 với,\n\n gọi 0905 123 456 " + "x" * 600)
    assert "0905" not in mo_ta and "[SĐT]" in mo_ta and "\x07" not in mo_ta
    assert len(mo_ta) == 500 and mo_ta.endswith("…")


def test_body_keu_cuu_bo_truong_trong():
    d = boc_tach.bo_luat("Cứu với, 3 người, gọi 0905123456")
    assert d.body_keu_cuu("dien_thoai") == {"reporter_phone": "0905123456", "people_count": 3,
                                             "urgency": "trung_binh", "description": "Cứu với, 3 người, gọi [SĐT]",
                                             "source": "dien_thoai"}


# ---------------- Mô hình bị cấm, cấu hình ----------------
@pytest.mark.parametrize("ten", ["llama3.1:8b", "gemma2:9b", "qwen2.5:3b", "qwen2.5:72b", "Qwen2.5-3B-Instruct",
                                 "qwen2.5-coder:3b"])
def test_mo_hinh_bi_cam(ten):
    with pytest.raises(ValueError, match="không được phép"):
        boc_tach.kiem_mo_hinh(ten)


@pytest.mark.parametrize("ten", ["qwen2.5:7b", "qwen2.5:14b", "qwen2.5:7b-instruct-q4_K_M"])
def test_mo_hinh_duoc_phep(ten):
    boc_tach.kiem_mo_hinh(ten)


def test_config_llm(monkeypatch):
    for k in ("LLM_PROVIDER", "LLM_MODEL", "LLM_BASE_URL", "LLM_API_KEY", "LLM_TIMEOUT_GIAY"):
        monkeypatch.delenv(k, raising=False)
    cfg = config.load()
    assert (cfg.llm_provider, cfg.llm_model, cfg.llm_timeout_giay) == ("gia-lap", "qwen2.5:7b", 60.0)
    monkeypatch.setenv("LLM_PROVIDER", "Ollama")
    monkeypatch.setenv("LLM_TIMEOUT_GIAY", "5000")
    cfg = config.load()
    assert (cfg.llm_provider, cfg.llm_timeout_giay) == ("ollama", 600.0)
    monkeypatch.setenv("LLM_MODEL", "llama3.1:8b")
    with pytest.raises(ValueError, match="không được phép"):
        config.load()
    monkeypatch.setenv("LLM_PROVIDER", "gpt")
    with pytest.raises(ValueError, match="LLM_PROVIDER"):
        config.load()


def test_tao_theo_cau_hinh(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    with pytest.raises(ValueError, match="LLM_BASE_URL"):
        boc_tach.tao(config.load(), httpx.AsyncClient())
    monkeypatch.setenv("LLM_PROVIDER", "tat")
    assert not boc_tach.tao(config.load(), httpx.AsyncClient()).bat


# ---------------- Nhà cung cấp HTTP (máy chủ giả) ----------------
def tra_loi(**d):
    base = {"dia_chi": None, "vi_do": None, "kinh_do": None, "so_dien_thoai": None, "ten_nguoi_bao": None,
            "so_nguoi": None, "muc_khan_cap": "trung_binh", "nhu_cau": [], "tom_tat": ""}
    return {**base, **d}


def chay(f):
    """Test async chạy bằng asyncio.run (repo không dùng plugin pytest-asyncio)."""
    @functools.wraps(f)
    def w(*a, **k):
        return asyncio.run(f(*a, **k))
    return w


def may_chu(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@chay
async def test_ollama_goi_dung_va_ghep():
    nhan = {}

    def handler(req: httpx.Request):
        nhan["url"] = str(req.url)
        nhan["body"] = json.loads(req.content)
        noi_dung = tra_loi(dia_chi="tổ 5 phường Hòa Khánh", vi_do=16.0712, kinh_do=108.1503,
                           so_dien_thoai="0935 111 222", ten_nguoi_bao="Nguyễn Văn An", so_nguoi=3,
                           muc_khan_cap="cao", nhu_cau=["y_te", "cuu_nguoi", "y_te", "bay"],
                           tom_tat="3 người già bị kẹt ở tổ 5, cần thuốc. Gọi 0935111222")
        return httpx.Response(200, json={"message": {"role": "assistant", "content": json.dumps(noi_dung)}})

    async with may_chu(handler) as http:
        bt = boc_tach.BocTach("ollama", boc_tach.Ollama(http, "http://ollama:11434/", "qwen2.5:7b", 30))
        kq = await bt.boc_tach(TIN)
    assert nhan["url"] == "http://ollama:11434/api/chat"
    b = nhan["body"]
    assert b["model"] == "qwen2.5:7b" and b["stream"] is False and b["format"] == boc_tach.SCHEMA
    assert b["options"]["temperature"] == 0
    assert b["messages"][0]["role"] == "system" and b["messages"][1]["content"].startswith("<tin>\n")
    d = kq.de_xuat
    assert (d.lat, d.lon, d.reporter_phone, d.people_count, d.urgency) == (16.0712, 108.1503, "0935111222", 3, "cao")
    assert d.address_text == "tổ 5 phường Hòa Khánh" and d.reporter_name == "Nguyễn Văn An"
    assert d.nhu_cau == ["y_te", "cuu_nguoi"]
    # Tóm tắt của mô hình làm mô tả, SĐT trong đó cũng bị che
    assert d.description == "3 người già bị kẹt ở tổ 5, cần thuốc. Gọi [SĐT]"
    assert (kq.nha_cung_cap, kq.mo_hinh, kq.du_phong, kq.canh_bao) == ("ollama", "qwen2.5:7b", False, [])


@chay
async def test_chong_bia():
    """Mô hình bịa SĐT, tọa độ, địa chỉ, tên không có trong tin → bỏ, dùng kết quả bộ luật, có cảnh báo."""
    def handler(_req):
        noi_dung = tra_loi(dia_chi="123 Lê Duẩn, Hải Châu", vi_do=16.0544, kinh_do=108.2022,
                           so_dien_thoai="0999999999", ten_nguoi_bao="Trần Thị B", so_nguoi=0,
                           muc_khan_cap="rat_cao", nhu_cau="cuu_nguoi")
        return httpx.Response(200, json={"message": {"content": json.dumps(noi_dung)}})

    async with may_chu(handler) as http:
        kq = await boc_tach.BocTach("ollama", boc_tach.Ollama(http, "http://o", "qwen2.5:7b", 30)).boc_tach(TIN)
    d, luat = kq.de_xuat, boc_tach.bo_luat(TIN)
    assert d.reporter_phone == "0935111222" and (d.lat, d.lon) == (16.0712, 108.1503)
    assert d.address_text == luat.address_text and d.reporter_name == luat.reporter_name
    assert d.people_count == 3 and d.urgency == luat.urgency and d.nhu_cau == luat.nhu_cau
    assert len(kq.canh_bao) == 3 and any("SĐT" in c for c in kq.canh_bao) and not kq.du_phong


@chay
async def test_openai_compatible():
    nhan = {}

    def handler(req: httpx.Request):
        nhan["url"], nhan["auth"] = str(req.url), req.headers.get("authorization")
        nhan["body"] = json.loads(req.content)
        noi_dung = "```json\n" + json.dumps(tra_loi(so_dien_thoai="0935111222", so_nguoi=3)) + "\n```"
        return httpx.Response(200, json={"choices": [{"message": {"content": noi_dung}}]})

    async with may_chu(handler) as http:
        mh = boc_tach.OpenAICompatible(http, "https://llm.example/v1/", "qwen2.5:14b", "k-gia", 30)
        kq = await boc_tach.BocTach("openai-compatible", mh).boc_tach(TIN)
    assert nhan["url"] == "https://llm.example/v1/chat/completions" and nhan["auth"] == "Bearer k-gia"
    assert nhan["body"]["response_format"] == {"type": "json_object"} and nhan["body"]["temperature"] == 0
    assert kq.de_xuat.reporter_phone == "0935111222" and kq.nha_cung_cap == "openai-compatible"


@pytest.mark.parametrize("handler", [
    lambda _r: (_ for _ in ()).throw(httpx.ConnectTimeout("quá hạn")),
    lambda _r: httpx.Response(500, json={"error": "model not found"}),
    lambda _r: httpx.Response(200, json={"message": {"content": "xin lỗi, tôi không hiểu"}}),
    lambda _r: httpx.Response(200, json={"khac": 1}),
], ids=["qua-han", "http-500", "khong-phai-json", "sai-dang"])
@chay
async def test_mo_hinh_loi_dung_bo_luat(handler, caplog):
    async with may_chu(handler) as http:
        with caplog.at_level(logging.WARNING):
            kq = await boc_tach.BocTach("ollama", boc_tach.Ollama(http, "http://o", "qwen2.5:7b", 1)).boc_tach(TIN)
    assert kq.du_phong and kq.de_xuat == boc_tach.bo_luat(TIN) and kq.canh_bao
    assert "0935" not in caplog.text and "Hòa Khánh" not in caplog.text


# ---------------- Endpoint POST /ai/boc-tach ----------------
KHOA = rsa.generate_private_key(public_exponent=65537, key_size=2048)
ISS = "http://localhost:8080/realms/disaster"


def token(sub: str, *vai_tro: str) -> str:
    now = int(time.time())
    t = jwt.encode({"sub": sub, "iss": ISS, "iat": now, "exp": now + 300, "preferred_username": sub,
                    HASURA_NS: {"x-hasura-allowed-roles": list(vai_tro), "x-hasura-user-id": sub}},
                   KHOA, algorithm="RS256")
    return f"Bearer {t}"


DP, TN, CH = token("dp", "dieu-phoi"), token("tn", "tinh-nguyen"), token("ch", "cuu-ho")


class SoTinGia:
    def __init__(self):
        self.trung = None
        self.hoi = []

    async def tim_trung(self, sdt, lon, lat):
        self.hoi.append((sdt, lon, lat))
        return self.trung


@pytest.fixture
def so(monkeypatch):
    for k in ("KEU_CUU_VUNG_PHUC_VU", "LLM_PROVIDER", "LLM_MODEL"):
        monkeypatch.delenv(k, raising=False)
    s = SoTinGia()
    st = app.state
    st.xac_thuc = XacThuc(ISS, lay_khoa=lambda _t: KHOA.public_key())
    st.cfg = config.load()
    st.so_tin = s
    st.boc_tach = boc_tach.BocTach("gia-lap")
    yield s
    for k in ("so_tin", "cfg", "boc_tach"):
        delattr(st, k)


def gui(body, tok=DP):
    h = {"Content-Type": "application/json"}
    if tok:
        h["Authorization"] = tok
    return TestClient(app).post("/ai/boc-tach", content=body if isinstance(body, (bytes, str)) else json.dumps(body),
                                headers=h)


def test_endpoint_hop_le(so, caplog):
    with caplog.at_level(logging.DEBUG):
        r = gui({"van_ban": TIN, "nguon": "zalo"}, TN)
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    d = r.json()
    assert d["poka_yoke"] == {"hop_le": True, "loi": [], "tin_trung": None}
    assert d["tin_keu_cuu"]["source"] == "mang_xa_hoi" and d["tin_keu_cuu"]["reporter_phone"] == "0935111222"
    assert d["de_xuat"]["nhu_cau"] and d["ai"] == {"nha_cung_cap": "gia-lap", "mo_hinh": None,
                                                    "thoi_gian_ms": d["ai"]["thoi_gian_ms"], "du_phong": False}
    assert so.hoi == [("0935111222", 108.1503, 16.0712)]
    assert "0935" not in caplog.text


def test_endpoint_thieu_toa_do_va_sdt(so):
    d = gui({"van_ban": "Cứu với, nhà ở thôn 3 ngập tới mái, 4 người"}).json()
    assert d["poka_yoke"]["hop_le"] is False
    assert {x["truong"] for x in d["poka_yoke"]["loi"]} == {"lat", "lon", "reporter_phone"}
    assert so.hoi == []  # Poka-yoke chưa qua thì không hỏi CSDL


def test_endpoint_tin_trung(so):
    so.trung = {"incident_id": "11111111-2222-3333-4444-555555555555", "khoang_cach_m": 120, "ban_kinh_m": 200,
                "trong_vong_phut": 360}
    d = gui({"van_ban": TIN}).json()
    pk = d["poka_yoke"]
    assert pk["hop_le"] is False and pk["loi"] == []
    assert pk["tin_trung"]["incident_id"] == so.trung["incident_id"] and "120 m" in pk["tin_trung"]["thong_bao"]


def test_endpoint_khong_ro_so_nguoi(so):
    d = gui({"van_ban": "Cứu với ở 16.0712, 108.1503, gọi 0935111222"}).json()
    assert d["tin_keu_cuu"].get("people_count") is None and any("số người" in c for c in d["canh_bao"])


@pytest.mark.parametrize("body, truong", [
    ({}, "van_ban"), ({"van_ban": "   "}, "van_ban"), ({"van_ban": "x" * 2001}, "van_ban"),
    ({"van_ban": "cứu", "nguon": "fax"}, "nguon"), ({"van_ban": "cứu", "lat": 1}, "lat"), ([1], "body"),
    ("không phải json", "body"),
])
def test_endpoint_422(so, body, truong):
    r = gui(body)
    assert r.status_code == 422 and truong in {x["truong"] for x in r.json()["detail"]["loi"]}


def test_endpoint_quyen_va_gioi_han(so):
    assert gui({"van_ban": TIN}, CH).status_code == 403
    assert gui({"van_ban": TIN}, None).status_code == 401
    assert gui(b'{"van_ban": "' + b"x" * 9000 + b'"}').status_code == 413
    app.state.boc_tach = boc_tach.BocTach("tat")
    assert gui({"van_ban": TIN}).status_code == 503
