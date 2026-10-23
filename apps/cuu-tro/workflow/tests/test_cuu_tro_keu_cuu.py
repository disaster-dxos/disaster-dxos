# SPDX-License-Identifier: Apache-2.0
"""API tiếp nhận tin kêu cứu (#66): kiểm dữ liệu (logic thuần), ánh xạ lỗi CSDL → 409/422, quyền theo vai,
không ghi SĐT ra log.

Endpoint chạy không qua lifespan, CSDL giả trong bộ nhớ mô phỏng đúng trigger incidents_no_duplicate (0001):
cùng SĐT, tin còn mở, khoảng cách ≤ bán kính, trong khoảng thời gian → asyncpg.UniqueViolationError với
DETAIL như PostgreSQL; khóa theo SĐT như pg_advisory_xact_lock. Gửi đồng thời trên PostgreSQL thật:
scripts/smoke-keu-cuu.sh.
"""

import asyncio
import json
import logging
import math
import time
import uuid
from datetime import datetime, timezone

import asyncpg
import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from cuu_tro_workflow import config, keu_cuu
from cuu_tro_workflow.api import app
from cuu_tro_workflow.auth import HASURA_NS, XacThuc

VN = keu_cuu.vung_tu_chuoi(keu_cuu.VUNG_VIET_NAM)
HOP_LE = {"lat": 15.8502, "lon": 108.1035, "reporter_phone": "0900066001", "description": "Nước ngập tới mái, 3 người"}


def loi(d):
    kq = keu_cuu.kiem_tra(d, VN)
    assert isinstance(kq, list), kq
    return {x.truong: x.thong_bao for x in kq}


# ---------------- Kiểm dữ liệu (logic thuần) ----------------
def test_hop_le_dien_mac_dinh():
    kq = keu_cuu.kiem_tra(HOP_LE, VN)
    assert kq == keu_cuu.TinKeuCuu(lat=15.8502, lon=108.1035, reporter_phone="0900066001",
                                   description="Nước ngập tới mái, 3 người", urgency="trung_binh", people_count=1,
                                   address_text=None, reporter_name=None, source="app")


def test_thieu_toa_do():
    e = loi({k: v for k, v in HOP_LE.items() if k not in ("lat", "lon")})
    assert set(e) == {"lat", "lon"} and "bắt buộc có vị trí" in e["lat"]
    assert set(loi({**HOP_LE, "lon": None})) == {"lon"}


@pytest.mark.parametrize("lat, lon, truong, cum_tu", [
    (95, 108, "lat", "-90 đến 90"),
    (16, -181, "lon", "-180 đến 180"),
    ("16.0", 108, "lat", "phải là số"),
    (True, 108, "lat", "phải là số"),
    (16, float("nan"), "lon", "phải là số"),
    (16, float("inf"), "lon", "phải là số"),
    # Đổi chỗ vĩ độ/kinh độ: 108 không phải vĩ độ; điểm hợp lệ nhưng ngoài vùng phục vụ
    (108.1035, 15.8502, "lat", "-90 đến 90"),
    (21.03, 85.0, "lat", "ngoài vùng phục vụ"),
    (48.85, 2.35, "lat", "ngoài vùng phục vụ"),
])
def test_toa_do_sai(lat, lon, truong, cum_tu):
    e = loi({**HOP_LE, "lat": lat, "lon": lon})
    assert cum_tu in e[truong]


def test_vung_phuc_vu_cau_hinh_duoc():
    vung = keu_cuu.vung_tu_chuoi("108.0,15.0,109.0,16.5")
    assert isinstance(keu_cuu.kiem_tra(HOP_LE, vung), keu_cuu.TinKeuCuu)
    assert "ngoài vùng phục vụ" in {x.truong: x.thong_bao for x in
                                    keu_cuu.kiem_tra({**HOP_LE, "lat": 10.77, "lon": 106.70}, vung)}["lat"]
    for sai in ("1,2,3", "109,15,108,16", "a,b,c,d", "0,0,200,10"):
        with pytest.raises(ValueError):
            keu_cuu.vung_tu_chuoi(sai)


@pytest.mark.parametrize("vao, ra", [
    ("0900066001", "0900066001"), ("090 006 6001", "0900066001"), ("090.006.6001", "0900066001"),
    ("+84900066001", "0900066001"), ("84900066001", "0900066001"), ("(090) 006-6001", "0900066001"),
    ("0300066001", "0300066001"),
    ("12345", None), ("0200066001", None), ("02363822222", None), ("090006600", None), ("09000660011", None),
    ("0900O66001", None), ("+1 900066001", None),
])
def test_chuan_hoa_sdt(vao, ra):
    assert keu_cuu.chuan_hoa_sdt(vao) == ra


@pytest.mark.parametrize("sdt", ["12345", "", 900066001, None])
def test_sdt_sai(sdt):
    d = {**HOP_LE, "reporter_phone": sdt}
    e = loi(d)
    assert set(e) == {"reporter_phone"}
    # Thông báo lỗi không lặp lại giá trị người dùng nhập
    assert str(sdt) not in e["reporter_phone"] or sdt in ("", None)


def test_mo_ta_urgency_so_nguoi_nguon():
    e = loi({**HOP_LE, "description": "  ", "urgency": "rat_gap", "people_count": 0, "source": "zalo"})
    assert set(e) == {"description", "urgency", "people_count", "source"}
    assert "Thiếu mô tả" in e["description"] and "khan_cap" in e["urgency"]
    assert "tối đa 500" in loi({**HOP_LE, "description": "x" * 501})["description"]
    assert "ký tự điều khiển" in loi({**HOP_LE, "description": "a\x00b"})["description"]
    assert "số nguyên" in loi({**HOP_LE, "people_count": 2.5})["people_count"]
    assert "số nguyên" in loi({**HOP_LE, "people_count": True})["people_count"]
    assert "1 đến 10000" in loi({**HOP_LE, "people_count": 10001})["people_count"]
    assert "tối đa 300" in loi({**HOP_LE, "address_text": "x" * 301})["address_text"]
    assert "tối đa 100" in loi({**HOP_LE, "reporter_name": "x" * 101})["reporter_name"]
    for u in keu_cuu.URGENCY:
        assert keu_cuu.kiem_tra({**HOP_LE, "urgency": u}, VN).urgency == u


def test_truong_la_va_body_khong_phai_object():
    assert "không được hỗ trợ" in loi({**HOP_LE, "latitude": 16})["latitude"]
    assert set(loi([HOP_LE])) == {"body"}
    # Báo đủ mọi trường sai trong một lần
    assert set(loi({})) == {"lat", "lon", "reporter_phone", "description"}


def test_doc_detail_trigger():
    detail = "incident_id=b0000000-0000-4000-8000-000000000001 distance_m=37 radius_m=200 window_minutes=360"
    assert keu_cuu.tin_trung_tu_detail(detail) == {"incident_id": "b0000000-0000-4000-8000-000000000001",
                                                   "khoang_cach_m": 37, "ban_kinh_m": 200, "trong_vong_phut": 360}
    assert keu_cuu.tin_trung_tu_detail("khác") is None and keu_cuu.tin_trung_tu_detail(None) is None


# ---------------- Endpoint (CSDL giả mô phỏng trigger chặn trùng) ----------------
KHOA = rsa.generate_private_key(public_exponent=65537, key_size=2048)
ISS = "http://localhost:8080/realms/disaster"
xt = XacThuc(ISS, lay_khoa=lambda _t: KHOA.public_key())


def token(sub: str, *vai_tro: str) -> str:
    now = int(time.time())
    t = jwt.encode({"sub": sub, "iss": ISS, "iat": now, "exp": now + 300, "preferred_username": sub,
                    HASURA_NS: {"x-hasura-allowed-roles": list(vai_tro), "x-hasura-user-id": sub}},
                   KHOA, algorithm="RS256")
    return f"Bearer {t}"


DP, TN, CH = token("dp", "dieu-phoi"), token("tn", "tinh-nguyen"), token("ch", "cuu-ho")


def _met(a, b) -> float:
    # Haversine, đủ chính xác ở vài trăm mét
    (lat1, lon1), (lat2, lon2) = (map(math.radians, p) for p in (a, b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(h))


class SoTinGia:
    """incidents + trigger incidents_no_duplicate (0001) trong bộ nhớ; khóa theo SĐT như advisory lock."""

    def __init__(self, ban_kinh_m=200, phut=360):
        self.tin: dict[str, dict] = {}
        self.cfg = (ban_kinh_m, phut)
        self.khoa: dict[str, asyncio.Lock] = {}
        self.loi_khac: Exception | None = None

    async def them(self, tin: keu_cuu.TinKeuCuu, created_by: str) -> dict:
        if self.loi_khac:
            raise self.loi_khac
        async with self.khoa.setdefault(tin.reporter_phone, asyncio.Lock()):
            now = time.time()
            for t in self.tin.values():
                d = _met((t["lat"], t["lon"]), (tin.lat, tin.lon))
                if (t["reporter_phone"] == tin.reporter_phone and t["status"] not in ("da_cuu", "dong")
                        and now - t["ts"] < self.cfg[1] * 60 and d <= self.cfg[0]):
                    raise asyncpg.UniqueViolationError.new({
                        "C": "23505", "n": "incidents_no_duplicate", "M": "Tin kêu cứu trùng",
                        "D": f"incident_id={t['id']} distance_m={round(d)} radius_m={self.cfg[0]} "
                             f"window_minutes={self.cfg[1]}"})
            await asyncio.sleep(0.01)  # mô phỏng thời gian ghi: yêu cầu đồng thời chồng lên nhau
            id_ = str(uuid.uuid4())
            self.tin[id_] = {**tin.__dict__, "id": id_, "status": "tiep_nhan", "created_by": created_by, "ts": now}
            return {"id": uuid.UUID(id_), "status": "tiep_nhan", "urgency": tin.urgency,
                    "people_count": tin.people_count, "created_at": datetime.now(timezone.utc)}


@pytest.fixture
def so(monkeypatch):
    monkeypatch.delenv("KEU_CUU_VUNG_PHUC_VU", raising=False)
    s = SoTinGia()
    st = app.state
    st.xac_thuc = xt
    st.cfg = config.load()
    st.so_tin = s
    yield s
    for k in ("so_tin", "cfg"):
        delattr(st, k)


def gui(c, body, tok=TN):
    h = {"Content-Type": "application/json"}
    if tok:
        h["Authorization"] = tok
    return c.post("/keu-cuu", content=body if isinstance(body, (bytes, str)) else json.dumps(body), headers=h)


def test_tao_tin_201(so):
    c = TestClient(app)
    r = gui(c, {**HOP_LE, "urgency": "khan_cap", "people_count": 3, "reporter_phone": "+84 900 066 001"})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["status"] == "tiep_nhan" and d["urgency"] == "khan_cap" and d["people_count"] == 3
    assert d["phan_cong"] == "tu_dong" and r.headers["cache-control"] == "no-store"
    # Không trả lại SĐT; CSDL nhận SĐT đã chuẩn hóa và created_by = sub của token
    assert "0900066001" not in r.text
    t = so.tin[d["id"]]
    assert t["reporter_phone"] == "0900066001" and t["created_by"] == "tn"


@pytest.mark.parametrize("tok, ma", [(None, 401), (CH, 403), (DP, 201), (TN, 201)],
                         ids=["khong-token", "cuu-ho", "dieu-phoi", "tinh-nguyen"])
def test_quyen_theo_vai(so, tok, ma):
    c = TestClient(app)
    assert gui(c, HOP_LE, tok).status_code == ma


def test_422_cau_truc_loi_tieng_viet(so):
    c = TestClient(app)
    r = gui(c, {"reporter_phone": "12345", "description": "x"})
    r2 = gui(c, b"{khong phai json")
    r3 = gui(c, b"x" * (keu_cuu.BODY_TOI_DA + 1))
    assert r.status_code == 422
    d = r.json()["detail"]
    assert d["ma"] == "du_lieu_khong_hop_le" and "kiểm tra lại" in d["thong_bao"]
    assert {x["truong"] for x in d["loi"]} == {"lat", "lon", "reporter_phone"}
    assert "12345" not in r.text
    assert r2.status_code == 422 and r2.json()["detail"]["loi"][0]["truong"] == "body"
    assert r3.status_code == 413
    assert so.tin == {}


def test_trung_trong_200m_409_kem_ma_tin(so):
    c = TestClient(app)
    id_cu = gui(c, HOP_LE).json()["id"]
    # ~150 m về phía bắc, SĐT viết khác dạng nhưng cùng số
    r = gui(c, {**HOP_LE, "lat": HOP_LE["lat"] + 0.00135, "reporter_phone": "090 006 6001"})
    khac_sdt = gui(c, {**HOP_LE, "reporter_phone": "0900066002"})
    xa = gui(c, {**HOP_LE, "lat": HOP_LE["lat"] + 0.0025})  # ~277 m
    assert r.status_code == 409
    d = r.json()["detail"]
    assert d["ma"] == "tin_trung" and d["incident_id"] == id_cu and d["ban_kinh_m"] == 200
    assert 140 <= d["khoang_cach_m"] <= 160 and "Không tạo tin mới" in d["thong_bao"]
    assert khac_sdt.status_code == 201 and xa.status_code == 201
    assert len(so.tin) == 3


def test_tin_cu_da_dong_thi_tao_moi(so):
    c = TestClient(app)
    id_cu = gui(c, HOP_LE).json()["id"]
    so.tin[id_cu]["status"] = "dong"
    assert gui(c, HOP_LE).status_code == 201


def test_gui_dong_thoi_chi_mot_tin(so):
    async def _main():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://api") as c:
            return await asyncio.gather(*[
                c.post("/keu-cuu", json={**HOP_LE, "lat": HOP_LE["lat"] + i * 0.0001},
                       headers={"Authorization": TN}) for i in range(8)])

    rs = asyncio.run(_main())
    ma = sorted(r.status_code for r in rs)
    assert ma == [201] + [409] * 7
    id_moi = next(r.json()["id"] for r in rs if r.status_code == 201)
    assert {r.json()["detail"]["incident_id"] for r in rs if r.status_code == 409} == {id_moi}
    assert len(so.tin) == 1


def test_loi_unique_khac_khong_bi_nuot(so):
    so.loi_khac = asyncpg.UniqueViolationError.new({"C": "23505", "n": "incidents_pkey", "M": "trùng khóa"})
    c = TestClient(app, raise_server_exceptions=False)
    assert gui(c, HOP_LE).status_code == 500


def test_check_violation_422_khong_ghi_thong_diep(so, caplog):
    so.loi_khac = asyncpg.CheckViolationError.new({"C": "23514", "n": "incidents_people_count_check",
                                                   "M": "giá trị 0900066001 vi phạm"})
    c = TestClient(app)
    with caplog.at_level(logging.INFO, logger="cuu_tro_workflow.api"):
        r = gui(c, HOP_LE)
    assert r.status_code == 422 and "0900066001" not in caplog.text


def test_khong_ghi_sdt_ra_log(so, caplog):
    c = TestClient(app)
    with caplog.at_level(logging.DEBUG):
        gui(c, HOP_LE)
        assert gui(c, HOP_LE).status_code == 409
        gui(c, {**HOP_LE, "reporter_phone": "0900066xyz"})
    assert "0900066" not in caplog.text
    assert "tin kêu cứu trùng tin đang mở" in caplog.text
