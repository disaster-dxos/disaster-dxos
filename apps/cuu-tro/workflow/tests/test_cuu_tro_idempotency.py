# SPDX-License-Identifier: Apache-2.0
"""Header Idempotency-Key (#106): app hiện trường gửi lại bản ghi từ hàng đợi offline không tạo trùng.
Kiểm dạng khóa, băm yêu cầu, và ba đường ghi: POST /keu-cuu, POST /tai-len/su-co/{id}/anh, POST /ai/boc-tach có
vao_hang_cho. CSDL là bản giả có cùng ngữ nghĩa với SoIdempotency.chay (khóa theo người dùng + khóa, yêu cầu đồng
thời cùng khóa chờ nhau, lỗi nghiệp vụ không giữ khóa); câu SQL thật: db/tests/0015_khoa_idempotency.sql."""

import asyncio
import json
import uuid
from datetime import datetime, timezone

import asyncpg
import httpx
import pytest
from fastapi.testclient import TestClient

from cuu_tro_workflow import boc_tach, config, idempotency
from cuu_tro_workflow.api import app
from tests.test_cuu_tro_anh import INC_TN, HeThongGia, KhoGia, SoGia, token, xt

DP, TN, TN2 = token("dp", "dieu-phoi"), token("tn", "tinh-nguyen"), token("tn2", "tinh-nguyen")
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 60
TIN = {"lat": 16.0712, "lon": 108.1503, "reporter_phone": "0935111222", "description": "Ngập tới mái, 3 người",
       "urgency": "khan_cap", "people_count": 3}


# ---------------- Logic thuần ----------------
def test_doc_khoa():
    assert idempotency.doc_khoa(None) is None
    k = str(uuid.uuid4())
    assert idempotency.doc_khoa(f" {k} ") == k
    for sai in ("", "ngan", "a" * 129, "co dau cach 123", "khóa-tiếng-việt", "a/b/c/d/e/f"):
        with pytest.raises(idempotency.KhoaSai):
            idempotency.doc_khoa(sai)


def test_bam_phan_biet_duong_dan_va_noi_dung():
    a = idempotency.bam("POST /keu-cuu", b"{}")
    assert len(a) == 32 and a == idempotency.bam("POST /keu-cuu", b"{}")
    assert a != idempotency.bam("POST /keu-cuu", b"{ }") and a != idempotency.bam("POST /ai/boc-tach", b"{}")


# ---------------- CSDL giả ----------------
class SoIdemGia:
    """Ngữ nghĩa của SoIdempotency: khóa (sub, key); xong mới lưu; đồng thời cùng khóa thì chờ rồi phát lại."""

    def __init__(self):
        self.dong: dict[tuple[str, str], dict] = {}
        self.khoa: dict[tuple[str, str], asyncio.Lock] = {}

    def _phat_lai(self, d, endpoint, sha):
        if d["endpoint"] != endpoint or d["sha"] != sha:
            raise idempotency.KhoaDungLai()
        return idempotency.KetQua(d["status"], json.loads(json.dumps(d["luu"])), True)

    async def tim(self, sub, khoa, endpoint, sha):
        d = self.dong.get((sub, khoa))
        return self._phat_lai(d, endpoint, sha) if d else None

    async def chay(self, sub, khoa, endpoint, sha, xu_ly):
        async with self.khoa.setdefault((sub, khoa), asyncio.Lock()):
            if (d := self.dong.get((sub, khoa))) is not None:
                return self._phat_lai(d, endpoint, sha)
            status, body, luu = await xu_ly(None)
            self.dong[(sub, khoa)] = {"endpoint": endpoint, "sha": sha, "status": status, "luu": luu}
            return idempotency.KetQua(status, body, False)


class SoTinGia:
    """incidents: chặn trùng cùng SĐT như trigger (đơn giản: cùng SĐT là trùng)."""

    def __init__(self):
        self.tin: dict[str, dict] = {}

    async def them(self, tin, created_by):
        await asyncio.sleep(0.01)  # yêu cầu đồng thời chồng lên nhau
        for t in self.tin.values():
            if t["reporter_phone"] == tin.reporter_phone:
                raise asyncpg.UniqueViolationError.new({
                    "C": "23505", "n": "incidents_no_duplicate", "M": "trùng",
                    "D": f"incident_id={t['id']} distance_m=0 radius_m=200 window_minutes=360"})
        id_ = str(uuid.uuid4())
        self.tin[id_] = {**tin.__dict__, "id": id_}
        return {"id": uuid.UUID(id_), "status": "tiep_nhan", "urgency": tin.urgency, "people_count": tin.people_count,
                "created_at": datetime.now(timezone.utc)}

    async def tim_trung(self, *_a):
        return None


class SoHangChoGia:
    def __init__(self):
        self.muc: list[dict] = []

    async def them(self, **d):
        self.muc.append(d)
        return {"id": str(uuid.uuid4()), "trang_thai": "cho_duyet", "tao_luc": "2026-10-26T00:00:00+00:00"}


class BocTachDem(boc_tach.BocTach):
    def __init__(self):
        super().__init__("gia-lap")
        self.so_lan = 0

    async def boc_tach(self, van_ban):
        self.so_lan += 1
        return await super().boc_tach(van_ban)


@pytest.fixture
def ht(monkeypatch):
    for k in ("KEU_CUU_VUNG_PHUC_VU", "LLM_PROVIDER", "LLM_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("ANH_MAX_BYTES", "1024")
    h = HeThongGia()
    st = app.state
    st.xac_thuc = xt
    st.cfg = config.load()
    st.http = httpx.AsyncClient(base_url="http://apisix:9080", transport=httpx.MockTransport(h.graphql))
    st.kho_anh, st.so_anh = KhoGia(h), SoGia(h)
    st.so_tin, st.so_hang_cho, st.so_idem, st.boc_tach = SoTinGia(), SoHangChoGia(), SoIdemGia(), BocTachDem()
    yield h
    for k in ("http", "kho_anh", "so_anh", "cfg", "so_tin", "so_hang_cho", "so_idem", "boc_tach"):
        delattr(st, k)


def post(path, body, tok=TN, khoa=None, ct="application/json"):
    h = {"Authorization": tok, "Content-Type": ct}
    if khoa is not None:
        h[idempotency.HEADER] = khoa
    noi_dung = body if isinstance(body, bytes) else json.dumps(body).encode()
    return TestClient(app).post(path, content=noi_dung, headers=h)


# ---------------- POST /keu-cuu ----------------
def test_keu_cuu_gui_lai_cung_khoa_phat_lai_khong_tao_trung(ht):
    k = str(uuid.uuid4())
    r1 = post("/keu-cuu", TIN, khoa=k)
    r2 = post("/keu-cuu", TIN, khoa=k)
    assert r1.status_code == r2.status_code == 201
    assert r2.json() == r1.json() and r2.headers[idempotency.HEADER_PHAT_LAI] == "true"
    assert idempotency.HEADER_PHAT_LAI not in r1.headers
    assert len(app.state.so_tin.tin) == 1


def test_keu_cuu_khong_khoa_thi_lan_gui_lai_bi_chan_trung(ht):
    # Vì sao cần khóa: gửi lại không khóa bị chốt chặn trùng trả 409, app không biết tin của mình đã vào
    assert post("/keu-cuu", TIN).status_code == 201
    assert post("/keu-cuu", TIN).status_code == 409


def test_keu_cuu_cung_khoa_khac_noi_dung_hoac_khoa_sai_422(ht):
    k = str(uuid.uuid4())
    assert post("/keu-cuu", TIN, khoa=k).status_code == 201
    r = post("/keu-cuu", {**TIN, "people_count": 4}, khoa=k)
    assert r.status_code == 422 and r.json()["detail"]["ma"] == "khoa_idempotency_dung_lai"
    r = post("/keu-cuu", {**TIN, "reporter_phone": "0935111333"}, khoa="ngan")
    assert r.status_code == 422 and r.json()["detail"]["ma"] == "khoa_idempotency_sai"
    assert len(app.state.so_tin.tin) == 1


def test_keu_cuu_loi_khong_giu_khoa(ht):
    # Tin trùng (409) không lưu vào khóa: gửi lại vẫn 409 (không phát lại phản hồi lỗi như thành công)
    assert post("/keu-cuu", TIN, tok=TN2).status_code == 201
    k = str(uuid.uuid4())
    assert post("/keu-cuu", TIN, khoa=k).status_code == 409
    assert post("/keu-cuu", TIN, khoa=k).status_code == 409
    assert app.state.so_idem.dong == {}


def test_keu_cuu_khoa_theo_nguoi_dung(ht):
    k = str(uuid.uuid4())
    assert post("/keu-cuu", TIN, khoa=k).status_code == 201
    # Người khác dùng trùng khóa: không phát lại tin của người kia, xử lý như yêu cầu mới (ở đây bị chặn trùng)
    assert post("/keu-cuu", TIN, tok=TN2, khoa=k).status_code == 409


def test_keu_cuu_hai_yeu_cau_dong_thoi_cung_khoa(ht):
    k = str(uuid.uuid4())

    async def chay():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://api") as c:
            return await asyncio.gather(*(c.post("/keu-cuu", content=json.dumps(TIN), headers={
                "Authorization": TN, "Content-Type": "application/json", idempotency.HEADER: k}) for _ in range(3)))

    rs = asyncio.run(chay())
    assert [r.status_code for r in rs] == [201, 201, 201]
    assert len({r.json()["id"] for r in rs}) == 1 and len(app.state.so_tin.tin) == 1
    assert sum(r.headers.get(idempotency.HEADER_PHAT_LAI) == "true" for r in rs) == 2


# ---------------- Ảnh hiện trường ----------------
def test_anh_gui_lai_khong_ghi_them_va_ky_link_moi(ht):
    k = str(uuid.uuid4())
    r1 = post(f"/tai-len/su-co/{INC_TN}/anh", JPEG, khoa=k, ct="image/jpeg")
    assert r1.status_code == 201
    # Tin đã sang phân công sau lần gửi đầu: tinh-nguyen không còn quyền tải ảnh mới, nhưng gửi lại cùng khóa
    # vẫn nhận kết quả cũ (khóa chỉ của chính người gửi)
    ht.tin[INC_TN]["status"] = "phan_cong"
    r2 = post(f"/tai-len/su-co/{INC_TN}/anh", JPEG, khoa=k, ct="image/jpeg")
    assert r2.status_code == 201 and r2.headers[idempotency.HEADER_PHAT_LAI] == "true"
    assert r2.json()["id"] == r1.json()["id"] and r2.json()["link"]["url"].startswith("http://localhost:9080/files/")
    assert len(ht.anh) == 1 and len(ht.s3) == 1
    # Ảnh mới (khóa mới) thì kiểm quyền như thường
    assert post(f"/tai-len/su-co/{INC_TN}/anh", JPEG, khoa=str(uuid.uuid4()), ct="image/jpeg").status_code == 403


def test_anh_csdl_loi_xoa_object_va_khong_giu_khoa(ht):
    ht.loi_db = True
    k = str(uuid.uuid4())
    assert post(f"/tai-len/su-co/{INC_TN}/anh", JPEG, khoa=k, ct="image/jpeg").status_code == 500
    assert ht.s3 == {} and app.state.so_idem.dong == {}
    ht.loi_db = False
    assert post(f"/tai-len/su-co/{INC_TN}/anh", JPEG, khoa=k, ct="image/jpeg").status_code == 201


# ---------------- Chuyển tin vào hàng chờ duyệt ----------------
VB = {"van_ban": "Cuu voi o 16.0712, 108.1503, 3 nguoi, goi 0935111222", "nguon": "sms", "vao_hang_cho": True}


def test_chuyen_tin_gui_lai_khong_them_muc_khong_goi_lai_ai(ht):
    k = str(uuid.uuid4())
    r1 = post("/ai/boc-tach", VB, khoa=k)
    r2 = post("/ai/boc-tach", VB, khoa=k)
    assert r1.status_code == r2.status_code == 200
    assert r2.json()["hang_cho"] == r1.json()["hang_cho"] and r2.headers[idempotency.HEADER_PHAT_LAI] == "true"
    # Phản hồi lưu để phát lại không có dữ liệu cá nhân (đề xuất có SĐT, tên)
    assert "de_xuat" in r1.json() and "de_xuat" not in r2.json() and "0935" not in r2.text
    assert r2.json()["phat_lai_rut_gon"] is True
    assert len(app.state.so_hang_cho.muc) == 1 and app.state.boc_tach.so_lan == 1


def test_boc_tach_khong_vao_hang_cho_bo_qua_khoa(ht):
    k = str(uuid.uuid4())
    vb = {**VB, "vao_hang_cho": False}
    assert post("/ai/boc-tach", vb, khoa=k).status_code == 200
    assert post("/ai/boc-tach", vb, khoa="sai dang").status_code == 200
    assert app.state.so_idem.dong == {} and app.state.boc_tach.so_lan == 2
