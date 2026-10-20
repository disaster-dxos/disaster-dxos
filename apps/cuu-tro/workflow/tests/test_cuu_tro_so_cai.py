# SPDX-License-Identifier: Apache-2.0
"""Sổ cái minh bạch (#28): JSON chuẩn tắc (vector chung với Go), Merkle RFC 6962, chữ ký checkpoint,
endpoint lập phiếu / ghi sổ / trang minh bạch công khai.

Endpoint chạy trên TestClient không qua lifespan: CSDL giả trong bộ nhớ; sổ cái giả bằng
httpx.MockTransport cài đúng giao thức core/ledger (lá, cây Merkle RFC 6962, checkpoint note Ed25519).
"""

import base64
import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi.testclient import TestClient

from cuu_tro_workflow import config, so_cai
from cuu_tro_workflow.api import app
from cuu_tro_workflow.auth import HASURA_NS, XacThuc

# ---------------- JSON chuẩn tắc: cùng vector với core/ledger/leaf/leaf_test.go ----------------
VECTOR = {"quantity": "1500.00", "note": 'Tiếp nhận <từ> huyện & "đội"',
          "id": "e0000000-0000-4000-8000-000000000001", "shelter_id": None}
VECTOR_CANON = ('{"id":"e0000000-0000-4000-8000-000000000001","note":"Tiếp nhận <từ> huyện & \\"đội\\"",'
                '"quantity":"1500.00","shelter_id":null}')
VECTOR_SHA = "5043285895e43aaebcfd6cdb4d9624aabb9b51514a477ed80dbaa5b7250a6429"


def test_json_chuan_tac_trung_vector_go():
    assert so_cai.json_chuan_tac(VECTOR) == VECTOR_CANON.encode()
    assert so_cai.sha256_ban_ghi(VECTOR) == VECTOR_SHA
    assert so_cai.json_chuan_tac({"a": "x y"}) == b'{"a":"x\\u2028y"}'
    with pytest.raises(ValueError):
        so_cai.json_chuan_tac({"quantity": 1500})


def test_ban_ghi_chuan_hoa_khong_co_nguoi_lap_va_on_dinh():
    dong = {"id": uuid.UUID("e0000000-0000-4000-8000-000000000001"),
            "supply_id": uuid.UUID("d0000000-0000-4000-8000-000000000001"), "direction": "nhap",
            "quantity": Decimal("1500"), "note": None, "shelter_id": None,
            "created_at": datetime(2026, 10, 20, 8, 15, 30, tzinfo=timezone.utc), "created_by": "dieuphoi01"}
    bg = so_cai.ban_ghi_chuan_hoa(dong)
    assert "created_by" not in bg and bg["quantity"] == "1500.00"
    assert bg["created_at"] == "2026-10-20T08:15:30.000000Z" and bg["shelter_id"] is None
    la = so_cai.la_cho_phieu(bg)
    assert la["ref"] == bg["id"] and la["attrs"] == {"direction": "nhap", "quantity": "1500.00",
                                                       "at": "2026-10-20T08:15:30.000000Z"}
    assert "dieuphoi01" not in json.dumps(la)


@pytest.mark.parametrize("ghi_chu, co", [
    ("Liên hệ 0905123456", True), ("CCCD 079203001234", True), ("Phiếu số 12/2026", False),
    ("Ủng hộ 150000000 đồng", False), (None, False), ("", False),
])
def test_chan_so_dinh_danh_trong_ghi_chu(ghi_chu, co):
    assert so_cai.co_so_dinh_danh(ghi_chu) is co


# ---------------- Merkle RFC 6962 ----------------
def _mth(la: list[bytes]) -> bytes:
    if len(la) == 1:
        return so_cai.leaf_hash(la[0])
    k = 1
    while k * 2 < len(la):
        k *= 2
    return hashlib.sha256(b"\x01" + _mth(la[:k]) + _mth(la[k:])).digest()


def _path(m: int, la: list[bytes]) -> list[bytes]:
    if len(la) == 1:
        return []
    k = 1
    while k * 2 < len(la):
        k *= 2
    if m < k:
        return _path(m, la[:k]) + [_mth(la[k:])]
    return _path(m - k, la[k:]) + [_mth(la[:k])]


def test_kiem_inclusion_moi_kich_thuoc():
    for n in range(1, 18):
        la = [f"la-{i}".encode() for i in range(n)]
        root = _mth(la)
        for i in range(n):
            p = _path(i, la)
            lh = so_cai.leaf_hash(la[i])
            assert so_cai.kiem_inclusion(i, n, lh, p, root), (n, i)
            assert not so_cai.kiem_inclusion(i, n, so_cai.leaf_hash(b"khac"), p, root)
            if p:
                assert not so_cai.kiem_inclusion(i, n, lh, p[:-1], root)
            if n > 1:
                assert not so_cai.kiem_inclusion((i + 1) % n, n, lh, p, root)
    assert not so_cai.kiem_inclusion(3, 3, b"x", [], b"x")


# ---------------- Checkpoint note Ed25519 ----------------
def _khoa(ten: str) -> tuple[Ed25519PrivateKey, str]:
    k = Ed25519PrivateKey.generate()
    pub = k.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    h = hashlib.sha256(ten.encode() + b"\n\x01" + pub).digest()[:4]
    return k, f"{ten}+{h.hex()}+{base64.b64encode(b'\x01' + pub).decode()}"


def _ky(k: Ed25519PrivateKey, vkey: str, size: int, root: bytes) -> str:
    ten, h, _ = vkey.split("+", 2)
    than = f"{ten}\n{size}\n{base64.b64encode(root).decode()}\n"
    sig = base64.b64encode(bytes.fromhex(h) + k.sign(than.encode())).decode()
    return f"{than}\n— {ten} {sig}\n"


def test_kiem_checkpoint():
    k, vkey = _khoa("test.local/ledger")
    cp = _ky(k, vkey, 5, b"\x07" * 32)
    khoa = so_cai.doc_khoa_cong_khai(vkey)
    c = so_cai.kiem_checkpoint(cp, khoa)
    assert (c.origin, c.size, c.root) == ("test.local/ledger", 5, b"\x07" * 32)
    with pytest.raises(so_cai.LoiXacMinh):
        so_cai.kiem_checkpoint(cp.replace("\n5\n", "\n6\n"), khoa)          # sửa kích thước cây
    _, khac = _khoa("test.local/ledger")
    with pytest.raises(so_cai.LoiXacMinh):
        so_cai.kiem_checkpoint(cp, so_cai.doc_khoa_cong_khai(khac))         # khóa khác
    with pytest.raises(so_cai.LoiXacMinh):
        so_cai.doc_khoa_cong_khai(vkey.replace("+", "+0", 1))               # hash sai


# ---------------- Endpoint ----------------
KHOA_JWT = rsa.generate_private_key(public_exponent=65537, key_size=2048)
ISS = "http://localhost:8080/realms/disaster"
xt = XacThuc(ISS, lay_khoa=lambda _t: KHOA_JWT.public_key())
TOKEN_GHI = "token-ghi-thu"
HANG = "d0000000-0000-4000-8000-000000000001"


def token(sub: str, *vai_tro: str) -> str:
    now = int(time.time())
    t = jwt.encode({"sub": sub, "iss": ISS, "iat": now, "exp": now + 300, "preferred_username": sub,
                    HASURA_NS: {"x-hasura-allowed-roles": list(vai_tro), "x-hasura-user-id": sub}},
                   KHOA_JWT, algorithm="RS256")
    return f"Bearer {t}"


DP = token("dieuphoi01", "dieu-phoi")
CH = token("cuuho01", "cuu-ho")


class SoCaiGia:
    """Sổ cái giả theo đúng giao thức core/ledger (POST /ledger/entries, GET /ledger/proof, verifier)."""

    def __init__(self) -> None:
        self.khoa, self.vkey = _khoa("test.local/ledger")
        self.la: list[bytes] = []
        self.hong = False
        self.token_nhan: list[str] = []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        if self.hong:
            raise httpx.ConnectError("sổ cái tắt")
        if req.url.path == "/ledger/verifier":
            return httpx.Response(200, text=self.vkey + "\n")
        if req.method == "POST" and req.url.path == "/ledger/entries":
            self.token_nhan.append(req.headers.get("Authorization", ""))
            if req.headers.get("Authorization") != f"Bearer {TOKEN_GHI}":
                return httpx.Response(401, json={"error": "cần token ghi"})
            body = json.loads(req.content)
            leaf = json.dumps({"attrs": body["attrs"], "ref": body["ref"], "sha256": body["sha256"],
                               "type": body["type"], "v": 1}, sort_keys=True, separators=(",", ":")).encode()
            trung = leaf in self.la
            if not trung:
                self.la.append(leaf)
            return httpx.Response(200 if trung else 201, json={
                "index": self.la.index(leaf), "leaf_hash": so_cai.leaf_hash(leaf).hex(),
                "duplicate": trung, "tree_size": len(self.la), "origin": "test.local/ledger"})
        if req.url.path.startswith("/ledger/proof/"):
            i = int(req.url.path.rsplit("/", 1)[1])
            if i >= len(self.la):
                return httpx.Response(404, json={"error": "chưa có"})
            root = _mth(self.la)
            return httpx.Response(200, json={
                "index": i, "tree_size": len(self.la), "root_hash": root.hex(), "leaf": self.la[i].decode(),
                "leaf_hash": so_cai.leaf_hash(self.la[i]).hex(),
                "proof": [h.hex() for h in _path(i, self.la)],
                "checkpoint": _ky(self.khoa, self.vkey, len(self.la), root)})
        return httpx.Response(404)


class SoPhieuGia:
    def __init__(self) -> None:
        self.dong: dict[str, dict] = {}
        self.ton = Decimal("0")

    async def them(self, *, supply_id, direction, quantity, note, shelter_id, created_by):
        if supply_id != HANG:
            import asyncpg
            raise asyncpg.ForeignKeyViolationError("fk")
        moi = self.ton + (quantity if direction == "nhap" else -quantity)
        if moi < 0:
            import asyncpg
            raise asyncpg.CheckViolationError("ton")
        self.ton = moi
        ma = str(uuid.uuid4())
        self.dong[ma] = {"id": uuid.UUID(ma), "supply_id": uuid.UUID(supply_id), "direction": direction,
                         "quantity": quantity, "note": note, "shelter_id": None,
                         "created_at": datetime.now(timezone.utc), "created_by": created_by,
                         "ledger_index": None, "ledger_leaf_hash": None, "ledger_logged_at": None,
                         "item_name": "Gạo", "unit": "kg", "storage_name": "Kho xã", "shelter_name": None}
        return {k: v for k, v in self.dong[ma].items() if k != "created_by"}

    async def doc(self, ma):
        d = self.dong.get(ma)
        return {k: v for k, v in d.items() if k != "created_by"} if d else None

    async def ghi_so(self, ma, index, leaf_hash):
        d = self.dong[ma]
        if d["ledger_index"] is not None:
            return None
        d.update(ledger_index=index, ledger_leaf_hash=leaf_hash, ledger_logged_at=datetime.now(timezone.utc))
        return d["ledger_logged_at"]


@pytest.fixture
def ht():
    st = app.state
    sc, sp = SoCaiGia(), SoPhieuGia()
    st.xac_thuc = xt
    st.cfg = config.load()
    st.so_phieu = sp
    st.so_cai = so_cai.SoCai(httpx.AsyncClient(base_url="http://ledger:8090", transport=httpx.MockTransport(sc)),
                             TOKEN_GHI)
    yield sc, sp
    for k in ("so_phieu", "so_cai", "cfg"):
        delattr(st, k)


def lap(c, tok, **kw):
    body = {"supply_id": HANG, "direction": "nhap", "quantity": "10"} | kw
    h = {"Authorization": tok} if tok else {}
    return c.post("/kho/phieu", json=body, headers=h)


def test_lap_phieu_ghi_so_va_minh_bach_da_xac_minh(ht):
    sc, sp = ht
    c = TestClient(app)
    ma = []
    for kw in ({}, {"direction": "xuat", "quantity": "4"}, {"direction": "xuat", "quantity": "6", "note": "Cấp điểm THCS"}):
        r = lap(c, DP, **kw)
        assert r.status_code == 201, r.text
        b = r.json()
        assert b["so_cai"]["trang_thai"] == "da_ghi" and b["so_cai"]["index"] == len(ma)
        assert "created_by" not in b["ban_ghi_chuan_hoa"]
        ma.append(b["ban_ghi_chuan_hoa"]["id"])
    assert sc.token_nhan == [f"Bearer {TOKEN_GHI}"] * 3
    # Lá không chứa người lập phiếu
    assert all(b"dieuphoi01" not in la for la in sc.la)
    for m in ma:
        r = c.get(f"/minh-bach/phieu/{m}")   # không cần token
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["trang_thai"] == so_cai.DA_XAC_MINH, b
        assert b["so_cai"]["checkpoint"]["tree_size"] == 3 and r.headers["cache-control"] == "no-store"
        assert b["hien_thi"]["mat_hang"] == "Gạo" and "created_by" not in json.dumps(b)
    assert sp.ton == 0


def test_sua_csdl_bao_khong_khop(ht):
    _, sp = ht
    c = TestClient(app)
    m = lap(c, DP).json()["ban_ghi_chuan_hoa"]["id"]
    sp.dong[m]["quantity"] = Decimal("100")   # ai đó sửa thẳng trong CSDL
    b = c.get(f"/minh-bach/phieu/{m}").json()
    assert b["trang_thai"] == so_cai.KHONG_KHOP
    assert any("đã bị sửa" in x for x in b["chi_tiet"])
    sp.dong[m]["quantity"] = Decimal("10")
    sp.dong[m]["ledger_leaf_hash"] = b"\x00" * 32   # leaf hash trong CSDL bị đổi
    b = c.get(f"/minh-bach/phieu/{m}").json()
    assert b["trang_thai"] == so_cai.KHONG_KHOP and any("Leaf hash" in x for x in b["chi_tiet"])


def test_quyen_va_kiem_dau_vao(ht):
    c = TestClient(app)
    assert lap(c, None).status_code == 401
    assert lap(c, CH).status_code == 403
    assert lap(c, DP, note="Người nhận 0905123456").status_code == 422
    assert lap(c, DP, quantity="0").status_code == 422
    assert lap(c, DP, quantity="1.234").status_code == 422
    assert lap(c, DP, direction="xuat", quantity="999").status_code == 409
    assert lap(c, DP, supply_id=str(uuid.uuid4())).status_code == 404
    assert c.get("/minh-bach/phieu/khong-phai-uuid").status_code == 404
    assert c.get(f"/minh-bach/phieu/{uuid.uuid4()}").status_code == 404
    assert c.post(f"/kho/phieu/{uuid.uuid4()}/ghi-so", headers={"Authorization": CH}).status_code == 403


def test_so_cai_tat_thi_phieu_cho_ghi_lai(ht):
    sc, _ = ht
    c = TestClient(app)
    sc.hong = True
    r = lap(c, DP)
    assert r.status_code == 202 and r.json()["so_cai"]["trang_thai"] == so_cai.CHUA_GHI_SO
    m = r.json()["ban_ghi_chuan_hoa"]["id"]
    assert c.get(f"/minh-bach/phieu/{m}").json()["trang_thai"] == so_cai.CHUA_GHI_SO
    assert c.post(f"/kho/phieu/{m}/ghi-so", headers={"Authorization": DP}).status_code == 503
    sc.hong = False
    r = c.post(f"/kho/phieu/{m}/ghi-so", headers={"Authorization": DP})
    assert r.status_code == 200 and r.json()["so_cai"]["trang_thai"] == "da_ghi"
    # Gọi lại khi đã ghi: không ghi thêm lá
    r2 = c.post(f"/kho/phieu/{m}/ghi-so", headers={"Authorization": DP})
    assert r2.json()["so_cai"]["index"] == r.json()["so_cai"]["index"] and len(sc.la) == 1
    assert c.get(f"/minh-bach/phieu/{m}").json()["trang_thai"] == so_cai.DA_XAC_MINH
