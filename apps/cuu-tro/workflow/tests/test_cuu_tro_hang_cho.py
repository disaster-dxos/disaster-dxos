# SPDX-License-Identifier: Apache-2.0
"""Hàng chờ duyệt tin do AI bóc tách (#104, HITL): so trường người sửa, kiểm body duyệt/hủy, POST /ai/boc-tach
với vao_hang_cho (lưu đúng đề xuất API vừa tạo), POST /hang-cho/{id}/duyet (đọc đề xuất qua Hasura bằng JWT
người duyệt, Poka-yoke của /keu-cuu, 404/409/422, tin trùng), POST /hang-cho/{id}/huy, quyền theo vai, hai người
duyệt cùng lúc. CSDL và gateway /graphql là bản giả; câu SQL thật: db/tests/0014_hang_cho_duyet.sql."""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone

import asyncpg
import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from cuu_tro_workflow import boc_tach, config, hang_cho, keu_cuu
from cuu_tro_workflow.api import app
from cuu_tro_workflow.auth import HASURA_NS, XacThuc

KHOA = rsa.generate_private_key(public_exponent=65537, key_size=2048)
ISS = "http://localhost:8080/realms/disaster"
TIN = ("Tôi là Nguyễn Văn An ở tổ 5 phường Hòa Khánh, nhà có 3 người già bị kẹt, cần thuốc. "
       "Gọi 0935 111 222. Vị trí 16.0712, 108.1503")
VUNG = keu_cuu.vung_tu_chuoi(keu_cuu.VUNG_VIET_NAM)


def token(sub: str, *vai_tro: str) -> str:
    now = int(time.time())
    return "Bearer " + jwt.encode(
        {"sub": sub, "iss": ISS, "iat": now, "exp": now + 300, "preferred_username": sub + "01",
         HASURA_NS: {"x-hasura-allowed-roles": list(vai_tro), "x-hasura-user-id": sub}},
        KHOA, algorithm="RS256")


DP, DP2, TN, CH = token("dp", "dieu-phoi"), token("dp2", "dieu-phoi"), token("tn", "tinh-nguyen"), token("ch", "cuu-ho")


# ---------------- Logic thuần ----------------
AI_BODY = {"lat": 16.0712, "lon": 108.1503, "reporter_phone": "0935111222", "reporter_name": "Nguyễn Văn An",
           "people_count": 3, "urgency": "cao", "description": "3 người già bị kẹt, cần thuốc. Gọi [SĐT].",
           "source": "mang_xa_hoi"}


def _cuoi(body):
    tin = keu_cuu.kiem_tra(body, VUNG)
    assert isinstance(tin, keu_cuu.TinKeuCuu), tin
    return hang_cho.body_cuoi(tin)


def test_duyet_nguyen_de_xuat_khong_co_truong_sua():
    assert hang_cho.truong_da_sua(AI_BODY, _cuoi(AI_BODY)) == {}


def test_go_lai_sdt_khac_dinh_dang_khong_tinh_la_sua():
    assert hang_cho.truong_da_sua(AI_BODY, _cuoi({**AI_BODY, "reporter_phone": "+84 935 111 222"})) == {}


def test_truong_sua_ghi_gia_tri_ai_va_nguoi():
    sua = hang_cho.truong_da_sua(AI_BODY, _cuoi({**AI_BODY, "people_count": 5, "urgency": "khan_cap",
                                                  "address_text": "tổ 5 Hòa Khánh"}))
    assert sua == {"people_count": {"ai": 3, "nguoi": 5}, "urgency": {"ai": "cao", "nguoi": "khan_cap"},
                   "address_text": {"ai": None, "nguoi": "tổ 5 Hòa Khánh"}}


def test_bo_sung_toa_do_chon_tren_ban_do_la_sua():
    ai = {k: v for k, v in AI_BODY.items() if k not in ("lat", "lon")}
    sua = hang_cho.truong_da_sua(ai, _cuoi({**ai, "lat": 16.08, "lon": 108.15}))
    assert sua == {"lat": {"ai": None, "nguoi": 16.08}, "lon": {"ai": None, "nguoi": 108.15}}


def test_kiem_duyet():
    assert hang_cho.kiem_duyet({}, AI_BODY) == AI_BODY
    # tin_keu_cuu là body đầy đủ; thiếu source thì giữ nguồn của đề xuất
    b = hang_cho.kiem_duyet({"tin_keu_cuu": {"lat": 1}}, AI_BODY)
    assert b == {"lat": 1, "source": "mang_xa_hoi"}
    assert hang_cho.kiem_duyet({"tin_keu_cuu": {"source": "web"}}, AI_BODY) == {"source": "web"}
    loi = hang_cho.kiem_duyet({"tin_keu_cuu": [1], "x": 1}, AI_BODY)
    assert {x.truong for x in loi} == {"x", "tin_keu_cuu"}
    assert hang_cho.kiem_duyet([1], AI_BODY)[0].truong == "body"


def test_kiem_huy():
    assert hang_cho.kiem_huy({}) is None and hang_cho.kiem_huy({"ly_do": "  "}) is None
    assert hang_cho.kiem_huy({"ly_do": " Tin rác "}) == "Tin rác"
    assert [x.truong for x in hang_cho.kiem_huy({"ly_do": "x" * 501})] == ["ly_do"]
    assert [x.truong for x in hang_cho.kiem_huy({"ly_do": "a\x00"})] == ["ly_do"]
    assert [x.truong for x in hang_cho.kiem_huy({"ly_do": 1, "y": 2})] == ["y", "ly_do"]


def test_loi_da_xu_ly():
    d = hang_cho.loi_da_xu_ly({"status": "da_duyet", "reviewed_by_name": "dieuphoi01",
                               "reviewed_at": datetime(2026, 10, 26, tzinfo=timezone.utc), "incident_id": uuid.UUID(int=1)})
    assert d["ma"] == "da_xu_ly" and "duyệt bởi dieuphoi01" in d["thong_bao"]
    assert d["incident_id"] == str(uuid.UUID(int=1)) and d["reviewed_at"].startswith("2026-10-26")
    assert "hủy" in hang_cho.loi_da_xu_ly({"status": "da_huy"})["thong_bao"]


def test_dau_vao_boc_tach_vao_hang_cho():
    v = boc_tach.kiem_dau_vao({"van_ban": " cứu ", "vao_hang_cho": True})
    assert v == boc_tach.DauVao("cứu", "van_ban", True)
    assert boc_tach.kiem_dau_vao({"van_ban": "cứu"}).vao_hang_cho is False
    assert [x.truong for x in boc_tach.kiem_dau_vao({"van_ban": "cứu", "vao_hang_cho": "co"})] == ["vao_hang_cho"]
    assert [x.truong for x in boc_tach.kiem_dau_vao({"van_ban": "cứu\x00"})] == ["van_ban"]
    # Xuống dòng, tab của tin SMS/Zalo giữ nguyên
    assert boc_tach.kiem_dau_vao({"van_ban": "cứu\nvới\tgấp"}).van_ban == "cứu\nvới\tgấp"


# ---------------- Endpoint (CSDL + Hasura giả) ----------------
def _trung(incident_id: str) -> asyncpg.UniqueViolationError:
    return asyncpg.UniqueViolationError.new({
        "C": "23505", "n": "incidents_no_duplicate", "M": "Tin kêu cứu trùng",
        "D": f"incident_id={incident_id} distance_m=80 radius_m=200 window_minutes=360"})


class HeThongGia:
    """Bảng ai_intake_reviews + incidents trong bộ nhớ, khóa dòng như SELECT … FOR UPDATE; Hasura giả trả dòng
    cho vai dieu-phoi (đọc qua gateway bằng JWT người duyệt)."""

    def __init__(self):
        self.muc: dict[str, dict] = {}
        self.tin: dict[str, dict] = {}
        self.khoa: dict[str, asyncio.Lock] = {}
        self.trung_voi: str | None = None
        self.hasura_hoi: list[tuple[str, str]] = []

    # --- so_tin (kiểm trước tin trùng của /ai/boc-tach) ---
    async def tim_trung(self, sdt, lon, lat):
        return None

    # --- so_hang_cho ---
    async def them(self, *, van_ban, nguon, ket_qua, nguoi_gui, ten_nguoi_gui, vai_tro):
        id_ = str(uuid.uuid4())
        self.muc[id_] = {"id": id_, "raw_text": van_ban, "text_source": nguon, "ai_result": json.loads(json.dumps(ket_qua)),
                         "submitted_by": nguoi_gui, "submitted_by_name": ten_nguoi_gui, "submitted_role": vai_tro,
                         "status": "cho_duyet", "reviewed_at": None, "reviewed_by_name": None, "incident_id": None}
        return {"id": id_, "trang_thai": "cho_duyet", "tao_luc": "2026-10-26T00:00:00+00:00"}

    async def _khoa(self, ma):
        m = self.muc.get(ma)
        if m is None:
            raise hang_cho.KhongCo(ma)
        if m["status"] != "cho_duyet":
            raise hang_cho.DaXuLy(dict(m))
        return m

    async def duyet(self, ma, tin, *, sua, nguoi_duyet, ten_nguoi_duyet):
        async with self.khoa.setdefault(ma, asyncio.Lock()):
            m = await self._khoa(ma)
            await asyncio.sleep(0.01)  # hai yêu cầu đồng thời chồng lên nhau
            if self.trung_voi:
                raise _trung(self.trung_voi)
            id_ = str(uuid.uuid4())
            self.tin[id_] = {**tin.__dict__, "created_by": m["submitted_by"]}
            m.update(status="da_duyet", final_body=hang_cho.body_cuoi(tin), edited_fields=sua, reviewed_by=nguoi_duyet,
                     reviewed_by_name=ten_nguoi_duyet, reviewed_at=datetime.now(timezone.utc), incident_id=id_)
            return {"tin": {"id": uuid.UUID(id_), "status": "tiep_nhan", "urgency": tin.urgency,
                            "people_count": tin.people_count, "created_at": datetime.now(timezone.utc)},
                    "reviewed_at": m["reviewed_at"]}

    async def huy(self, ma, ly_do, *, nguoi_duyet, ten_nguoi_duyet):
        async with self.khoa.setdefault(ma, asyncio.Lock()):
            m = await self._khoa(ma)
            m.update(status="da_huy", cancel_reason=ly_do, reviewed_by=nguoi_duyet, reviewed_by_name=ten_nguoi_duyet,
                     reviewed_at=datetime.now(timezone.utc))
            return m["reviewed_at"]

    def graphql(self, req: httpx.Request) -> httpx.Response:
        sub = jwt.decode(req.headers["Authorization"][7:], options={"verify_signature": False})["sub"]
        vai = req.headers["X-Hasura-Role"]
        self.hasura_hoi.append((sub, vai))
        body = json.loads(req.content)
        assert "ai_intake_reviews_by_pk" in body["query"]
        m = self.muc.get(body["variables"]["id"]) if vai == "dieu-phoi" else None
        if m is not None:
            m = {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in m.items()
                 if k in ("id", "status", "ai_result", "reviewed_at", "reviewed_by_name", "incident_id")}
        return httpx.Response(200, json={"data": {"ai_intake_reviews_by_pk": m}})


@pytest.fixture
def ht(monkeypatch):
    for k in ("KEU_CUU_VUNG_PHUC_VU", "LLM_PROVIDER", "LLM_MODEL"):
        monkeypatch.delenv(k, raising=False)
    h = HeThongGia()
    st = app.state
    st.xac_thuc = XacThuc(ISS, lay_khoa=lambda _t: KHOA.public_key())
    st.cfg = config.load()
    st.so_tin = h
    st.so_hang_cho = h
    st.boc_tach = boc_tach.BocTach("gia-lap")
    st.http = httpx.AsyncClient(base_url="http://apisix:9080", transport=httpx.MockTransport(h.graphql))
    yield h
    for k in ("so_tin", "so_hang_cho", "cfg", "boc_tach", "http"):
        delattr(st, k)


def post(path, body=None, tok=DP):
    h = {"Content-Type": "application/json"}
    if tok:
        h["Authorization"] = tok
    noi_dung = body if isinstance(body, (bytes, str)) else (json.dumps(body) if body is not None else b"")
    return TestClient(app).post(path, content=noi_dung, headers=h)


def vao_hang_cho(van_ban=TIN, tok=TN, nguon="zalo"):
    r = post("/ai/boc-tach", {"van_ban": van_ban, "nguon": nguon, "vao_hang_cho": True}, tok)
    assert r.status_code == 200, r.text
    return r.json()


def test_boc_tach_khong_co_co_thi_khong_vao_hang_cho(ht):
    d = post("/ai/boc-tach", {"van_ban": TIN}).json()
    assert "hang_cho" not in d and ht.muc == {}


def test_boc_tach_vao_hang_cho_luu_dung_de_xuat_va_nguoi_gui(ht, caplog):
    with caplog.at_level(logging.DEBUG):
        d = vao_hang_cho()
    hc = d.pop("hang_cho")
    assert hc["trang_thai"] == "cho_duyet"
    m = ht.muc[hc["id"]]
    # Lưu đúng phản hồi API vừa tạo (client không tự khai đề xuất), văn bản gốc, người gửi theo JWT
    assert m["ai_result"] == d and m["raw_text"] == TIN and m["text_source"] == "zalo"
    assert (m["submitted_by"], m["submitted_by_name"], m["submitted_role"]) == ("tn", "tn01", "tinh-nguyen")
    assert "0935" not in caplog.text and "Hòa Khánh" not in caplog.text
    # Không tạo tin kêu cứu nào khi chỉ đưa vào hàng chờ
    assert ht.tin == {}


def test_dieu_phoi_dua_vao_hang_cho_ghi_vai_dieu_phoi(ht):
    hc = vao_hang_cho(tok=DP)["hang_cho"]
    assert ht.muc[hc["id"]]["submitted_role"] == "dieu-phoi"


def test_cuu_ho_khong_dua_vao_hang_cho(ht):
    assert post("/ai/boc-tach", {"van_ban": TIN, "vao_hang_cho": True}, CH).status_code == 403
    assert ht.muc == {}


def test_duyet_nguyen_de_xuat_tao_tin_va_luu_vet(ht, caplog):
    hc = vao_hang_cho()["hang_cho"]
    with caplog.at_level(logging.DEBUG):
        r = post(f"/hang-cho/{hc['id']}/duyet")
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["trang_thai"] == "da_duyet" and d["truong_da_sua"] == [] and d["phan_cong"] == "tu_dong"
    assert r.headers["cache-control"] == "no-store"
    tin = ht.tin[d["incident_id"]]
    # Tin thuộc người đưa vào hàng chờ; người duyệt nằm trong vết
    assert tin["created_by"] == "tn" and tin["reporter_phone"] == "0935111222" and tin["source"] == "mang_xa_hoi"
    m = ht.muc[hc["id"]]
    assert (m["status"], m["reviewed_by"], m["reviewed_by_name"], m["incident_id"]) == ("da_duyet", "dp", "dp01",
                                                                                         d["incident_id"])
    assert m["edited_fields"] == {} and m["final_body"]["people_count"] == 3
    # Đề xuất đọc qua Hasura bằng JWT + vai của người duyệt
    assert ht.hasura_hoi == [("dp", "dieu-phoi")]
    assert "0935" not in caplog.text


def test_duyet_da_sua_ghi_truong_sua(ht):
    hc = vao_hang_cho()["hang_cho"]
    ai_body = ht.muc[hc["id"]]["ai_result"]["tin_keu_cuu"]
    r = post(f"/hang-cho/{hc['id']}/duyet", {"tin_keu_cuu": {**ai_body, "people_count": 4, "urgency": "khan_cap"}})
    assert r.status_code == 201 and r.json()["truong_da_sua"] == ["people_count", "urgency"]
    assert ht.muc[hc["id"]]["edited_fields"] == {"people_count": {"ai": 3, "nguoi": 4},
                                                 "urgency": {"ai": "cao", "nguoi": "khan_cap"}}


def test_tin_thieu_toa_do_phai_bo_sung_moi_duyet_duoc(ht):
    hc = vao_hang_cho("Cứu với, nhà ở thôn 3 ngập tới mái, 4 người, gọi 0935111333")["hang_cho"]
    r = post(f"/hang-cho/{hc['id']}/duyet")
    assert r.status_code == 422 and {x["truong"] for x in r.json()["detail"]["loi"]} == {"lat", "lon"}
    assert ht.muc[hc["id"]]["status"] == "cho_duyet" and ht.tin == {}
    ai_body = ht.muc[hc["id"]]["ai_result"]["tin_keu_cuu"]
    r = post(f"/hang-cho/{hc['id']}/duyet", {"tin_keu_cuu": {**ai_body, "lat": 15.95, "lon": 108.25}})
    assert r.status_code == 201 and r.json()["truong_da_sua"] == ["lat", "lon"]


@pytest.mark.parametrize("body, truong", [
    ({"tin_keu_cuu": {"lat": 1}}, "lon"),
    ({"tin_keu_cuu": "x"}, "tin_keu_cuu"),
    ({"x": 1}, "x"),
    ("không phải json", "body"),
])
def test_duyet_422(ht, body, truong):
    hc = vao_hang_cho()["hang_cho"]
    r = post(f"/hang-cho/{hc['id']}/duyet", body)
    assert r.status_code == 422 and truong in {x["truong"] for x in r.json()["detail"]["loi"]}
    assert ht.muc[hc["id"]]["status"] == "cho_duyet"


def test_duyet_tin_trung_409_muc_van_cho_duyet(ht):
    hc = vao_hang_cho()["hang_cho"]
    ht.trung_voi = "11111111-2222-3333-4444-555555555555"
    r = post(f"/hang-cho/{hc['id']}/duyet")
    assert r.status_code == 409
    d = r.json()["detail"]
    assert d["ma"] == "tin_trung" and d["incident_id"] == ht.trung_voi
    assert ht.muc[hc["id"]]["status"] == "cho_duyet"


def test_duyet_404_va_409_da_xu_ly(ht):
    assert post(f"/hang-cho/{uuid.uuid4()}/duyet").status_code == 404
    assert post("/hang-cho/khong-phai-uuid/duyet").status_code == 422
    hc = vao_hang_cho()["hang_cho"]
    assert post(f"/hang-cho/{hc['id']}/duyet").status_code == 201
    r = post(f"/hang-cho/{hc['id']}/duyet", tok=DP2)
    assert r.status_code == 409 and r.json()["detail"]["ma"] == "da_xu_ly"
    assert "dp01" in r.json()["detail"]["thong_bao"]
    assert post(f"/hang-cho/{hc['id']}/huy", {"ly_do": "x"}).status_code == 409


def test_hai_nguoi_duyet_cung_luc_chi_mot_thanh_cong(ht):
    hc = vao_hang_cho()["hang_cho"]

    async def chay():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://api") as c:
            return await asyncio.gather(*(c.post(f"/hang-cho/{hc['id']}/duyet", content=b"{}", headers={
                "Authorization": tok, "Content-Type": "application/json"}) for tok in (DP, DP2)))

    rs = asyncio.run(chay())
    assert sorted(r.status_code for r in rs) == [201, 409]
    assert len(ht.tin) == 1


def test_quyen_duyet_huy_chi_dieu_phoi(ht):
    hc = vao_hang_cho()["hang_cho"]
    for tok in (TN, CH):
        assert post(f"/hang-cho/{hc['id']}/duyet", tok=tok).status_code == 403
        assert post(f"/hang-cho/{hc['id']}/huy", tok=tok).status_code == 403
    assert post(f"/hang-cho/{hc['id']}/duyet", tok=None).status_code == 401
    assert ht.muc[hc["id"]]["status"] == "cho_duyet"


def test_huy_khong_tao_tin_va_luu_ly_do(ht):
    hc = vao_hang_cho()["hang_cho"]
    r = post(f"/hang-cho/{hc['id']}/huy", {"ly_do": "Tin thử"})
    assert r.status_code == 200 and r.json()["trang_thai"] == "da_huy" and r.json()["ly_do"] == "Tin thử"
    m = ht.muc[hc["id"]]
    assert (m["status"], m["cancel_reason"], m["reviewed_by"]) == ("da_huy", "Tin thử", "dp") and ht.tin == {}
    assert post(f"/hang-cho/{hc['id']}/duyet").status_code == 409


def test_huy_khong_ly_do_va_loi(ht):
    hc = vao_hang_cho()["hang_cho"]
    assert post(f"/hang-cho/{hc['id']}/huy", {"ly_do": "x" * 501}).status_code == 422
    assert post(f"/hang-cho/{uuid.uuid4()}/huy").status_code == 404
    r = post(f"/hang-cho/{hc['id']}/huy")
    assert r.status_code == 200 and r.json()["ly_do"] is None
