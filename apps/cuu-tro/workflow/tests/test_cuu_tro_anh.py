# SPDX-License-Identifier: Apache-2.0
"""Ảnh hiện trường (#27): ký SigV4, nhận dạng magic bytes, luật quyền theo vai trò, endpoint API.

Endpoint chạy trên TestClient không qua lifespan: Hasura (gateway /graphql) giả bằng httpx.MockTransport
trả kết quả theo vai trò như metadata thật; kho S3 và CSDL giả trong bộ nhớ.
"""

import json
import struct
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from cuu_tro_workflow import anh, config
from cuu_tro_workflow.api import app
from cuu_tro_workflow.auth import HASURA_NS, NguoiDung, XacThuc
from cuu_tro_workflow.s3 import KhoAnh, ky_header, presign

# ---------------- Mẫu tệp ----------------
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01" + b"\x00" * 64 + b"\xff\xd9"
PNG = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + b"\x00" * 64
WEBP = b"RIFF" + struct.pack("<I", 80) + b"WEBPVP8 " + b"\x00" * 64
GIF = b"GIF89a" + b"\x00" * 64
HTML = b"<html><script>alert(1)</script></html>"


# ---------------- SigV4: ví dụ chính thức của AWS ----------------
# https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-query-string-auth.html
# https://docs.aws.amazon.com/AmazonS3/latest/API/sig-v4-header-based-auth.html
AK, SK = "AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
LUC_AWS = datetime(2013, 5, 24, tzinfo=timezone.utc)


def test_presign_khop_vi_du_aws():
    q = presign(method="GET", host="examplebucket.s3.amazonaws.com", path="/test.txt",
                access_key=AK, secret_key=SK, han_giay=86400, luc=LUC_AWS)
    assert q.endswith("X-Amz-Signature=aeeed9bbccd4d02ee5c0109b86d86835f995330da4c265957d157751f604d404")
    assert "X-Amz-Credential=AKIAIOSFODNN7EXAMPLE%2F20130524%2Fus-east-1%2Fs3%2Faws4_request" in q


def test_ky_header_khop_vi_du_aws():
    h = ky_header(method="GET", host="examplebucket.s3.amazonaws.com", path="/test.txt",
                  payload_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                  access_key=AK, secret_key=SK, luc=LUC_AWS, header_khac={"Range": "bytes=0-9"})
    assert h["Authorization"] == (
        "AWS4-HMAC-SHA256 Credential=AKIAIOSFODNN7EXAMPLE/20130524/us-east-1/s3/aws4_request, "
        "SignedHeaders=host;range;x-amz-content-sha256;x-amz-date, "
        "Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"
    )
    assert h["x-amz-date"] == "20130524T000000Z"


def test_link_xem_tro_qua_gateway_files_va_ky_cho_host_cong_khai():
    kho = KhoAnh(endpoint="http://seaweedfs:8333", bucket="cuu-tro-media", access_key=AK, secret_key=SK,
                 gateway_public_url="https://dxos.example.vn/", http=None)  # type: ignore[arg-type]
    url = kho.link_xem("su-co/a/b.jpg", 60, luc=LUC_AWS)
    u = urlsplit(url)
    assert (u.scheme, u.netloc, u.path) == ("https", "dxos.example.vn", "/files/cuu-tro-media/su-co/a/b.jpg")
    q = parse_qs(u.query)
    assert q["X-Amz-Expires"] == ["60"] and q["X-Amz-SignedHeaders"] == ["host"]
    # Path ký là path S3 (không có /files), host là host công khai của gateway
    assert url.endswith(presign(method="GET", host="dxos.example.vn", path="/cuu-tro-media/su-co/a/b.jpg",
                                access_key=AK, secret_key=SK, han_giay=60, luc=LUC_AWS))


# ---------------- Magic bytes ----------------
@pytest.mark.parametrize("du_lieu, loai", [
    (JPEG, "image/jpeg"), (PNG, "image/png"), (WEBP, "image/webp"),
    (GIF, None), (HTML, None), (b"", None), (b"\xff\xd8", None),
    # Đầu PNG nhưng chunk đầu không phải IHDR; RIFF nhưng là WAVE
    (b"\x89PNG\r\n\x1a\n" + b"\x00" * 4 + b"XXXX", None),
    (b"RIFF" + b"\x00" * 4 + b"WAVEfmt ", None),
])
def test_nhan_dang_magic_bytes(du_lieu, loai):
    assert anh.nhan_dang(du_lieu[: anh.SO_BYTE_DAU]) == loai


def test_object_key_khong_dung_ten_tep_nguoi_dung():
    assert anh.object_key("i", "m", "image/webp") == "su-co/i/m.webp"
    assert anh.object_key("i", "m", "image/jpeg") == "su-co/i/m.jpg"


# ---------------- Luật quyền (logic thuần) ----------------
def nd(*vai_tro: str) -> NguoiDung:
    return NguoiDung(sub="s", ten_dang_nhap="u", vai_tro=frozenset(vai_tro), token="t")


def ma(tc):
    return None if tc is None else tc.ma


def test_vai_tro_chinh_uu_tien_vai_tro_rong_nhat():
    assert anh.vai_tro_chinh(nd("tinh-nguyen", "dieu-phoi")) == "dieu-phoi"
    assert anh.vai_tro_chinh(nd("cuu-ho", "tinh-nguyen")) == "cuu-ho"
    assert anh.vai_tro_chinh(nd("khach")) is None


@pytest.mark.parametrize("vai_tro, tin, mong_doi", [
    ("dieu-phoi", {"status": "dang_cuu"}, None),
    ("dieu-phoi", None, 404),
    ("dieu-phoi", {"status": "dong"}, 409),
    ("cuu-ho", {"status": "phan_cong"}, None),
    ("cuu-ho", None, 403),                         # tin của đội khác: Hasura trả null
    ("tinh-nguyen", {"status": "tiep_nhan"}, None),  # tin mình vừa tạo
    ("tinh-nguyen", {"status": "phan_cong"}, 403),   # không còn là tin mới
    ("tinh-nguyen", None, 403),                     # tin người khác
    (None, {"status": "tiep_nhan"}, 403),
])
def test_quyen_tai_len(vai_tro, tin, mong_doi):
    assert ma(anh.quyen_tai_len(vai_tro, tin)) == mong_doi


@pytest.mark.parametrize("vai_tro, tin, mong_doi", [
    ("dieu-phoi", {"media": []}, None), ("dieu-phoi", None, 404),
    ("cuu-ho", {"media": []}, None), ("cuu-ho", None, 403),
    ("tinh-nguyen", {"media": []}, 403), (None, {"media": []}, 403),
])
def test_quyen_liet_ke(vai_tro, tin, mong_doi):
    assert ma(anh.quyen_liet_ke(vai_tro, tin)) == mong_doi


@pytest.mark.parametrize("vai_tro, m, mong_doi", [
    ("dieu-phoi", {"id": "x"}, None), ("dieu-phoi", None, 404),
    ("cuu-ho", {"id": "x"}, None), ("cuu-ho", None, 403),
    ("tinh-nguyen", {"id": "x"}, None), ("tinh-nguyen", None, 403),
])
def test_quyen_xem(vai_tro, m, mong_doi):
    assert ma(anh.quyen_xem(vai_tro, m)) == mong_doi


# ---------------- Endpoint (Hasura, S3, CSDL giả) ----------------
KHOA = rsa.generate_private_key(public_exponent=65537, key_size=2048)
ISS = "http://localhost:8080/realms/disaster"
xt = XacThuc(ISS, lay_khoa=lambda _t: KHOA.public_key())

DOI_A, DOI_B = "doi-a", "doi-b"
INC_A = "b0000000-0000-4000-8000-000000000002"   # phân công cho đội A
INC_B = "b0000000-0000-4000-8000-000000000003"   # phân công cho đội B
INC_TN = "b0000000-0000-4000-8000-0000000000aa"  # tinh-nguyen "tn" vừa tạo, tiep_nhan
INC_DONG = "b0000000-0000-4000-8000-0000000000dd"
THANH_VIEN = {"cuuho-a": DOI_A}


def token(sub: str, *vai_tro: str) -> str:
    now = int(time.time())
    t = jwt.encode({"sub": sub, "iss": ISS, "iat": now, "exp": now + 300, "preferred_username": sub,
                    HASURA_NS: {"x-hasura-allowed-roles": list(vai_tro), "x-hasura-user-id": sub}},
                   KHOA, algorithm="RS256")
    return f"Bearer {t}"


@dataclass
class HeThongGia:
    tin: dict = field(default_factory=lambda: {
        INC_A: {"id": INC_A, "status": "phan_cong", "assigned_team_id": DOI_A, "created_by": "dp"},
        INC_B: {"id": INC_B, "status": "dang_cuu", "assigned_team_id": DOI_B, "created_by": "dp"},
        INC_TN: {"id": INC_TN, "status": "tiep_nhan", "assigned_team_id": None, "created_by": "tn"},
        INC_DONG: {"id": INC_DONG, "status": "dong", "assigned_team_id": DOI_A, "created_by": "dp"},
    })
    anh: dict = field(default_factory=dict)
    s3: dict = field(default_factory=dict)
    loi_db: bool = False

    # Luật lọc theo hàng giống metadata Hasura (incidents, incident_media)
    def thay_tin(self, vai_tro, sub, t):
        if vai_tro == "dieu-phoi":
            return True
        if vai_tro == "cuu-ho":
            return t["assigned_team_id"] is not None and THANH_VIEN.get(sub) == t["assigned_team_id"]
        return vai_tro == "tinh-nguyen" and t["created_by"] == sub

    def thay_anh(self, vai_tro, sub, m):
        if vai_tro == "tinh-nguyen":
            return m["uploaded_by"] == sub
        return self.thay_tin(vai_tro, sub, self.tin[m["incident_id"]])

    def graphql(self, req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        tok = req.headers["Authorization"][7:]
        claims = jwt.decode(tok, options={"verify_signature": False})
        vai_tro, sub = req.headers["X-Hasura-Role"], claims["sub"]
        assert vai_tro in claims[HASURA_NS]["x-hasura-allowed-roles"]
        # Như Hasura thật: hỏi cột mà vai trò không có quyền → lỗi validation (không phải null)
        cam = {"tinh-nguyen": ("assigned_team_id", "uploaded_by", "uploader_role", "created_by")}.get(vai_tro, ())
        if any(c in body["query"] for c in cam):
            return httpx.Response(200, json={"errors": [{"message": "field not found in type",
                                                         "extensions": {"code": "validation-failed"}}]})
        id_ = body["variables"]["id"]
        if "incident_media_by_pk" in body["query"]:
            m = self.anh.get(id_)
            return httpx.Response(200, json={"data": {"incident_media_by_pk":
                                                      m if m and self.thay_anh(vai_tro, sub, m) else None}})
        t = self.tin.get(id_)
        if not t or not self.thay_tin(vai_tro, sub, t):
            return httpx.Response(200, json={"data": {"incidents_by_pk": None}})
        out = dict(t)
        if "media" in body["query"]:
            out["media"] = [m for m in self.anh.values() if m["incident_id"] == id_]
        return httpx.Response(200, json={"data": {"incidents_by_pk": out}})


class KhoGia(KhoAnh):
    def __init__(self, ht: HeThongGia):
        super().__init__(endpoint="http://seaweedfs:8333", bucket="cuu-tro-media", access_key="ak",
                         secret_key="sk", gateway_public_url="http://localhost:9080", http=None)  # type: ignore[arg-type]
        self.ht = ht

    async def ghi(self, key, du_lieu, content_type):
        self.ht.s3[key] = (du_lieu, content_type)

    async def xoa(self, key):
        self.ht.s3.pop(key, None)


class SoGia:
    def __init__(self, ht: HeThongGia):
        self.ht = ht

    async def them(self, **d):
        if self.ht.loi_db:
            raise RuntimeError("mất kết nối CSDL")
        self.ht.anh[d["id"]] = {**d, "uploaded_at": "2026-10-20T08:00:00+00:00", "scan_status": "chua_quet"}
        return {"uploaded_at": "2026-10-20T08:00:00+00:00", "scan_status": "chua_quet"}


@pytest.fixture
def ht(monkeypatch):
    monkeypatch.setenv("ANH_MAX_BYTES", "1024")
    monkeypatch.setenv("ANH_LINK_HAN_GIAY", "300")
    h = HeThongGia()
    st = app.state
    st.xac_thuc = xt
    st.cfg = config.load()
    st.http = httpx.AsyncClient(base_url="http://apisix:9080", transport=httpx.MockTransport(h.graphql))
    st.kho_anh = KhoGia(h)
    st.so_anh = SoGia(h)
    yield h
    for k in ("http", "kho_anh", "so_anh", "cfg"):
        delattr(st, k)


DP = token("dp", "dieu-phoi")
CH_A = token("cuuho-a", "cuu-ho")
TN = token("tn", "tinh-nguyen")
TN2 = token("tn2", "tinh-nguyen")


def tai(c, inc, du_lieu, tok, ct="image/jpeg"):
    h = {"Content-Type": ct}
    if tok:
        h["Authorization"] = tok
    return c.post(f"/tai-len/su-co/{inc}/anh", content=du_lieu, headers=h)


def test_dieu_phoi_tai_anh_ghi_s3_va_csdl(ht):
    c = TestClient(app)
    r = tai(c, INC_A, PNG, DP, ct="image/jpeg")  # Content-Type khai sai: lấy loại thật từ nội dung
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["content_type"] == "image/png" and b["object_key"].endswith(".png")
    assert b["object_key"].startswith(f"su-co/{INC_A}/") and b["size_bytes"] == len(PNG)
    assert b["uploaded_by"] == "dp" and b["uploader_role"] == "dieu-phoi" and b["scan_status"] == "chua_quet"
    assert ht.s3[b["object_key"]] == (PNG, "image/png")
    assert b["id"] in ht.anh and len(b["sha256"]) == 64
    assert b["link"]["url"].startswith(f"http://localhost:9080/files/cuu-tro-media/{b['object_key']}?X-Amz-")
    assert r.headers["cache-control"] == "no-store"


def test_tu_choi_tep_gia_mao_va_qua_kich_thuoc(ht):
    c = TestClient(app)
    assert tai(c, INC_A, HTML, DP).status_code == 415      # đuôi/Content-Type ảnh nhưng nội dung HTML
    assert tai(c, INC_A, GIF, DP, ct="image/gif").status_code == 415
    assert tai(c, INC_A, b"", DP).status_code == 400
    assert tai(c, INC_A, JPEG + b"\x00" * 2000, DP).status_code == 413
    assert ht.s3 == {} and ht.anh == {}


def test_qua_kich_thuoc_khi_khong_co_content_length(ht):
    # Body gửi dạng chunked (không Content-Length): vẫn dừng ở giới hạn khi đọc luồng
    c = TestClient(app)

    def phan():
        yield JPEG
        yield b"\x00" * 2000

    r = c.post(f"/tai-len/su-co/{INC_A}/anh", content=phan(), headers={"Authorization": DP})
    assert r.status_code == 413 and ht.s3 == {}


def test_khong_token_401(ht):
    c = TestClient(app)
    assert tai(c, INC_A, JPEG, None).status_code == 401
    assert c.get(f"/su-co/{INC_A}/anh").status_code == 401
    assert c.get(f"/anh/{INC_A}/link").status_code == 401


def test_quyen_tai_len_theo_vai_tro(ht):
    c = TestClient(app)
    assert tai(c, INC_A, JPEG, CH_A).status_code == 201      # tin của đội mình
    assert tai(c, INC_B, JPEG, CH_A).status_code == 403      # tin của đội khác
    assert tai(c, INC_TN, JPEG, TN).status_code == 201       # tin mình vừa tạo, tiep_nhan
    assert tai(c, INC_TN, JPEG, TN2).status_code == 403      # tin của người khác
    assert tai(c, INC_A, JPEG, TN).status_code == 403
    assert tai(c, INC_DONG, JPEG, DP).status_code == 409
    assert tai(c, "b0000000-0000-4000-8000-0000000000ff", JPEG, DP).status_code == 404
    assert tai(c, INC_A, JPEG, token("khach", "khach")).status_code == 403
    assert len(ht.anh) == 2


def test_csdl_loi_thi_xoa_object_tren_s3(ht):
    ht.loi_db = True
    r = tai(TestClient(app), INC_A, JPEG, DP)
    assert r.status_code == 500 and ht.s3 == {}


def test_liet_ke_va_link_xem_theo_vai_tro(ht):
    c = TestClient(app)
    id_a = tai(c, INC_A, JPEG, DP).json()["id"]
    id_b = tai(c, INC_B, WEBP, DP).json()["id"]
    id_tn = tai(c, INC_TN, PNG, TN).json()["id"]

    r = c.get(f"/su-co/{INC_A}/anh", headers={"Authorization": CH_A})
    assert r.status_code == 200 and [m["id"] for m in r.json()["anh"]] == [id_a]
    assert "X-Amz-Signature=" in r.json()["anh"][0]["link"]["url"]
    assert c.get(f"/su-co/{INC_B}/anh", headers={"Authorization": CH_A}).status_code == 403
    assert c.get(f"/su-co/{INC_A}/anh", headers={"Authorization": TN}).status_code == 403
    assert c.get(f"/su-co/{INC_TN}/anh", headers={"Authorization": TN}).status_code == 403
    assert c.get(f"/su-co/{INC_B}/anh", headers={"Authorization": DP}).status_code == 200

    assert c.get(f"/anh/{id_a}/link", headers={"Authorization": CH_A}).status_code == 200
    assert c.get(f"/anh/{id_b}/link", headers={"Authorization": CH_A}).status_code == 403
    assert c.get(f"/anh/{id_a}/link", headers={"Authorization": TN}).status_code == 403   # ảnh người khác
    assert c.get(f"/anh/{id_tn}/link", headers={"Authorization": TN}).status_code == 200  # ảnh mình tải
    assert c.get(f"/anh/{id_tn}/link", headers={"Authorization": TN2}).status_code == 403
    assert c.get(f"/anh/{INC_A}/link", headers={"Authorization": DP}).status_code == 404


def test_han_link_xem(ht):
    c = TestClient(app)
    id_a = tai(c, INC_A, JPEG, DP).json()["id"]
    r = c.get(f"/anh/{id_a}/link", params={"han_giay": 5}, headers={"Authorization": DP})
    assert r.status_code == 200 and r.json()["link"]["han_giay"] == 5
    assert parse_qs(urlsplit(r.json()["link"]["url"]).query)["X-Amz-Expires"] == ["5"]
    assert c.get(f"/anh/{id_a}/link", headers={"Authorization": DP}).json()["link"]["han_giay"] == 300
    assert c.get(f"/anh/{id_a}/link", params={"han_giay": 301}, headers={"Authorization": DP}).status_code == 422
    assert c.get(f"/anh/{id_a}/link", params={"han_giay": 0}, headers={"Authorization": DP}).status_code == 422
