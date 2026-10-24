# SPDX-License-Identifier: Apache-2.0
"""Sổ cái minh bạch mở rộng (#89): bản ghi chuẩn hóa của bút toán tiền, lá không có dữ liệu cá nhân,
endpoint lập bút toán / xác minh chung / danh sách / tổng hợp, sửa dữ liệu thì xác minh thất bại, bằng
chứng đủ để tự kiểm, bộ niêm phong bù (outbox) với CSDL giả. Sổ cái giả và Merkle dùng lại từ
test_cuu_tro_so_cai.py (cùng giao thức core/ledger)."""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import asyncpg
import httpx
import pytest
from fastapi.testclient import TestClient
from test_cuu_tro_so_cai import CH, DP, TOKEN_GHI, SoCaiGia, SoPhieuGia, _mth, xt

from cuu_tro_workflow import config, so_cai, so_cai_csdl
from cuu_tro_workflow.api import app
from cuu_tro_workflow.so_cai_niem_phong import BoNiemPhong

DIEM = "c0000000-0000-4000-8000-000000000001"
LUC = datetime(2026, 10, 24, 3, 0, 1, 250000, tzinfo=timezone.utc)


def dong_tien(**kw) -> dict:
    d = {"id": uuid.UUID("e1000000-0000-4000-8000-000000000001"), "direction": "thu", "amount": Decimal("50000000"),
         "currency": "VND", "category": "ung_ho", "purpose": "Ủng hộ của doanh nghiệp", "shelter_id": None,
         "supply_movement_id": None, "created_at": LUC, "created_by": "dieuphoi01"}
    d.update(kw)
    return d


# ---------------- Bản ghi chuẩn hóa + lá ----------------
def test_ban_ghi_khoan_tien_chuan_hoa_on_dinh_khong_nguoi_lap():
    bg = so_cai.ban_ghi_khoan_tien(dong_tien())
    assert bg == {"loai": "cuu-tro.khoan-tien/v1", "id": "e1000000-0000-4000-8000-000000000001", "direction": "thu",
                  "amount": "50000000", "currency": "VND", "category": "ung_ho", "purpose": "Ủng hộ của doanh nghiệp",
                  "shelter_id": None, "supply_movement_id": None, "created_at": "2026-10-24T03:00:01.250000Z"}
    # Cùng dữ liệu, kiểu khác (int / Decimal có số mũ / múi giờ khác) → cùng bản ghi, cùng SHA-256
    bg2 = so_cai.ban_ghi_khoan_tien(dong_tien(amount=50_000_000, created_at=LUC.astimezone(
        __import__("datetime").timezone(__import__("datetime").timedelta(hours=7)))))
    assert bg2 == bg and so_cai.sha256_ban_ghi(bg2) == so_cai.sha256_ban_ghi(bg)
    assert so_cai.ban_ghi_khoan_tien(dong_tien(amount=Decimal("5E+7")))["amount"] == "50000000"
    la = so_cai.la_cho_khoan_tien(bg)
    assert la == {"type": "cuu-tro.khoan-tien", "ref": bg["id"], "sha256": so_cai.sha256_ban_ghi(bg),
                  "attrs": {"direction": "thu", "amount": "50000000", "currency": "VND",
                            "at": "2026-10-24T03:00:01.250000Z"}}
    assert "dieuphoi01" not in json.dumps(la) and "dieuphoi01" not in json.dumps(bg)


@pytest.mark.parametrize("sua", [
    {"amount": Decimal("50000001")}, {"direction": "chi"}, {"category": "ngan_sach"}, {"purpose": "khác"},
    {"shelter_id": uuid.UUID(DIEM)}, {"created_at": LUC.replace(microsecond=250001)},
])
def test_sua_bat_ky_truong_cong_khai_doi_sha(sua):
    assert so_cai.sha256_ban_ghi(so_cai.ban_ghi_khoan_tien(dong_tien(**sua))) != \
        so_cai.sha256_ban_ghi(so_cai.ban_ghi_khoan_tien(dong_tien()))


def test_loai_so_cai_khai_bao_du_hai_bang():
    assert set(so_cai_csdl.LOAI) == {"phieu_kho", "khoan_tien"}
    assert so_cai_csdl.LOAI["khoan_tien"].loai_la == "cuu-tro.khoan-tien"
    assert so_cai_csdl.LOAI["phieu_kho"].bang == "cuu_tro.supply_movements"


# ---------------- Endpoint với CSDL + sổ cái giả ----------------
class SoKhoanGia:
    def __init__(self) -> None:
        self.dong: dict[str, dict] = {}

    def so_du(self) -> Decimal:
        return sum((d["amount"] if d["direction"] == "thu" else -d["amount"] for d in self.dong.values()), Decimal(0))

    async def them(self, *, direction, amount, category, purpose, shelter_id, supply_movement_id, created_by):
        if direction == "chi" and amount > self.so_du():
            raise asyncpg.CheckViolationError("relief_fund_entries_balance")
        if shelter_id and shelter_id != DIEM:
            raise asyncpg.ForeignKeyViolationError("fk")
        ma = str(uuid.uuid4())
        self.dong[ma] = dong_tien(id=uuid.UUID(ma), direction=direction, amount=amount, category=category,
                                  purpose=purpose, shelter_id=uuid.UUID(shelter_id) if shelter_id else None,
                                  supply_movement_id=uuid.UUID(supply_movement_id) if supply_movement_id else None,
                                  created_at=datetime.now(timezone.utc), created_by=created_by, ledger_index=None,
                                  ledger_leaf_hash=None, ledger_logged_at=None,
                                  shelter_name="Trường THCS An Lạc" if shelter_id else None)
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


class CongKhaiGia:
    def __init__(self, sk: SoKhoanGia) -> None:
        self.sk = sk

    async def danh_sach(self, truoc, loai, gioi_han):
        ds = sorted((d for d in self.sk.dong.values() if d["ledger_index"] is not None),
                    key=lambda d: -d["ledger_index"])
        return [{"loai": "khoan_tien", "ma": str(d["id"]), "ledger_index": d["ledger_index"]} for d in ds
                if truoc is None or d["ledger_index"] < truoc][:gioi_han]

    async def tong_hop(self):
        return {"so_du": f"{self.sk.so_du():.0f}"}


@pytest.fixture
def ht():
    st = app.state
    sc, sp, sk = SoCaiGia(), SoPhieuGia(), SoKhoanGia()
    st.xac_thuc = xt
    st.cfg = config.load()
    st.so_phieu, st.so_khoan, st.so_cai_cong_khai = sp, sk, CongKhaiGia(sk)
    st.so_cai = so_cai.SoCai(httpx.AsyncClient(base_url="http://ledger:8090", transport=httpx.MockTransport(sc)),
                             TOKEN_GHI)
    yield sc, sk
    for k in ("so_phieu", "so_khoan", "so_cai_cong_khai", "so_cai", "cfg"):
        delattr(st, k)


def lap(c, tok, **kw):
    body = {"direction": "thu", "amount": 50000000, "category": "ung_ho", "purpose": "Ủng hộ"} | kw
    return c.post("/quy/khoan", json=body, headers={"Authorization": tok} if tok else {})


def test_thu_chi_ghi_so_va_xac_minh_cong_khai(ht):
    sc, sk = ht
    c = TestClient(app)
    ma = []
    for kw in ({}, {"direction": "chi", "amount": 12000000, "category": "mua_hang", "purpose": "Mua nước uống"},
               {"direction": "chi", "amount": 3000000, "category": "ho_tro_ho_dan", "shelter_id": DIEM}):
        r = lap(c, DP, **kw)
        assert r.status_code == 201, r.text
        assert r.json()["so_cai"]["trang_thai"] == "da_ghi" and r.json()["so_cai"]["index"] == len(ma)
        ma.append(r.json()["ban_ghi_chuan_hoa"]["id"])
    assert all(b"dieuphoi01" not in la for la in sc.la)
    for m in ma:
        b = c.get(f"/minh-bach/khoan-tien/{m}").json()   # không cần token
        assert b["trang_thai"] == so_cai.DA_XAC_MINH and b["loai"] == "khoan_tien", b
        assert b["hien_thi"]["don_vi"] == "VND" and "created_by" not in json.dumps(b)
        x = c.get(f"/minh-bach/xac-minh/{m}").json()
        assert x["hop_le"] is True and x["loai"] == "khoan_tien"
    assert c.get(f"/minh-bach/khoan-tien/{ma[2]}").json()["hien_thi"]["diem_nhan"] == "Trường THCS An Lạc"
    ds = c.get("/minh-bach/so-cai?gioi_han=2").json()
    assert [x["ledger_index"] for x in ds["muc"]] == [2, 1] and ds["truoc_tiep"] == 1
    assert c.get("/minh-bach/so-cai?truoc=1&gioi_han=2").json() == {"muc": [{"loai": "khoan_tien", "ma": ma[0],
                                                                              "ledger_index": 0}], "truoc_tiep": None}
    assert c.get("/minh-bach/quy").json() == {"so_du": "35000000"}


def test_bang_chung_du_de_tu_kiem_khong_can_tin_may_chu(ht):
    sc, _ = ht
    c = TestClient(app)
    m = lap(c, DP).json()["ban_ghi_chuan_hoa"]["id"]
    lap(c, DP, amount=1000)
    b = c.get(f"/minh-bach/xac-minh/{m}").json()
    bc = b["bang_chung"]
    # Tự kiểm phía client: băm bản ghi, so lá, dựng lại root từ inclusion proof, kiểm chữ ký checkpoint
    la = bc["leaf_index"], json.loads(b["so_cai"]["la"])
    assert la[1]["sha256"] == so_cai.sha256_ban_ghi(b["ban_ghi_chuan_hoa"]) and la[1]["ref"] == m
    cp = so_cai.kiem_checkpoint(bc["checkpoint"], so_cai.doc_khoa_cong_khai(sc.vkey))
    lh = so_cai.leaf_hash(b["so_cai"]["la"].encode())
    assert lh.hex() == bc["leaf_hash"] and cp.root == _mth(sc.la)
    assert so_cai.kiem_inclusion(bc["leaf_index"], cp.size, lh, [bytes.fromhex(h) for h in bc["inclusion_proof"]],
                                 cp.root)
    # Proof bị sửa một byte → không còn dẫn tới root đã ký
    hong = [bytes.fromhex(h) for h in bc["inclusion_proof"]]
    hong[0] = bytes([hong[0][0] ^ 1]) + hong[0][1:]
    assert not so_cai.kiem_inclusion(bc["leaf_index"], cp.size, lh, hong, cp.root)


def test_sua_csdl_hoac_doi_loai_la_bao_khong_khop(ht):
    sc, sk = ht
    c = TestClient(app)
    m = lap(c, DP).json()["ban_ghi_chuan_hoa"]["id"]
    sk.dong[m]["amount"] = Decimal("90000000")   # ai đó sửa thẳng số tiền trong CSDL
    b = c.get(f"/minh-bach/xac-minh/{m}").json()
    assert b["hop_le"] is False and b["trang_thai"] == so_cai.KHONG_KHOP
    assert any("đã bị sửa" in x for x in b["chi_tiet"])
    sk.dong[m]["amount"] = Decimal("50000000")
    assert c.get(f"/minh-bach/xac-minh/{m}").json()["hop_le"] is True
    # Lá của phiếu kho không được nhận làm bằng chứng cho bút toán tiền (cùng ref, khác loại)
    bg = so_cai.ban_ghi_khoan_tien(sk.dong[m])
    kq = asyncio.run(so_cai.xac_minh(app.state.so_cai, bg, sk.dong[m]["ledger_index"],
                                     bytes(sk.dong[m]["ledger_leaf_hash"]), so_cai.LOAI_LA))
    assert kq["trang_thai"] == so_cai.KHONG_KHOP and any("không phải của mã này" in x for x in kq["chi_tiet"])


def test_quyen_va_kiem_dau_vao(ht):
    c = TestClient(app)
    assert lap(c, None).status_code == 401
    assert lap(c, CH).status_code == 403
    assert lap(c, DP, purpose="Chuyển khoản tài khoản 0123456789").status_code == 422
    assert lap(c, DP, category="mua_hang").status_code == 422          # thu mà hạng mục chi
    assert lap(c, DP, direction="chi", category="ung_ho").status_code == 422
    assert lap(c, DP, amount=0).status_code == 422
    assert lap(c, DP, amount=1.5).status_code == 422
    assert lap(c, DP, direction="chi", category="mua_hang", amount=1).status_code == 409   # quỹ trống
    assert lap(c, DP, shelter_id=str(uuid.uuid4())).status_code == 404
    assert c.get("/minh-bach/xac-minh/khong-phai-uuid").status_code == 404
    assert c.get(f"/minh-bach/xac-minh/{uuid.uuid4()}").status_code == 404
    assert c.get("/minh-bach/so-cai?gioi_han=101").status_code == 422
    assert c.post(f"/quy/khoan/{uuid.uuid4()}/ghi-so", headers={"Authorization": CH}).status_code == 403


def test_xac_minh_chung_nhan_ca_ma_phieu(ht):
    c = TestClient(app)
    r = c.post("/kho/phieu", json={"supply_id": "d0000000-0000-4000-8000-000000000001", "direction": "nhap",
                                   "quantity": "10"}, headers={"Authorization": DP})
    m = r.json()["ban_ghi_chuan_hoa"]["id"]
    b = c.get(f"/minh-bach/xac-minh/{m}").json()
    assert b["hop_le"] is True and b["loai"] == "phieu_kho" and b["hien_thi"]["don_vi"] == "kg"


def test_so_cai_tat_thi_cho_ghi_bu(ht):
    sc, _ = ht
    c = TestClient(app)
    sc.hong = True
    r = lap(c, DP)
    assert r.status_code == 202 and r.json()["so_cai"]["trang_thai"] == so_cai.CHUA_GHI_SO
    m = r.json()["ban_ghi_chuan_hoa"]["id"]
    assert c.get(f"/minh-bach/xac-minh/{m}").json()["trang_thai"] == so_cai.CHUA_GHI_SO
    sc.hong = False
    r = c.post(f"/quy/khoan/{m}/ghi-so", headers={"Authorization": DP})
    assert r.status_code == 200 and r.json()["so_cai"]["trang_thai"] == "da_ghi"
    assert c.get(f"/minh-bach/xac-minh/{m}").json()["hop_le"] is True


# ---------------- Bộ niêm phong bù (outbox) ----------------
class ConGia:
    """Kết nối CSDL giả: fetch trả dòng chờ niêm phong của đúng bảng, fetchval điền ledger_*."""

    def __init__(self, bang: dict[str, list[dict]]) -> None:
        self.bang = bang

    def transaction(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def fetch(self, sql, cho, lo):
        ten = "supply_movements" if "supply_movements" in sql else "relief_fund_entries"
        return [d for d in self.bang[ten] if d["ledger_index"] is None][:lo]

    async def fetchval(self, sql, ma, index, lh):
        ten = "supply_movements" if "supply_movements" in sql else "relief_fund_entries"
        for d in self.bang[ten]:
            if str(d["id"]) == str(ma) and d["ledger_index"] is None:
                d.update(ledger_index=index, ledger_leaf_hash=lh, ledger_logged_at=datetime.now(timezone.utc))
                return d["ledger_logged_at"]
        return None


class PoolGia:
    def __init__(self, con: ConGia) -> None:
        self.con = con

    def acquire(self):
        return self.con


def test_bo_niem_phong_ghi_bu_ca_hai_loai_va_dung_khi_so_cai_tat():
    sc = SoCaiGia()
    phieu = {"id": uuid.uuid4(), "supply_id": uuid.uuid4(), "direction": "nhap", "quantity": Decimal("5"), "note": None,
             "shelter_id": None, "created_at": LUC, "ledger_index": None, "ledger_leaf_hash": None,
             "ledger_logged_at": None}
    tien = [dong_tien(id=uuid.uuid4(), ledger_index=None, ledger_leaf_hash=None, ledger_logged_at=None) for _ in range(2)]
    con = ConGia({"supply_movements": [phieu], "relief_fund_entries": tien})

    async def chay():
        async with httpx.AsyncClient(base_url="http://ledger:8090", transport=httpx.MockTransport(sc)) as h:
            bo = BoNiemPhong(PoolGia(con), so_cai.SoCai(h, TOKEN_GHI))
            sc.hong = True
            kq1 = await bo.mot_luot()
            kq1["phieu_sau_luot_1"] = phieu["ledger_index"]
            sc.hong = False
            kq2 = await bo.mot_luot()
            kq3 = await bo.mot_luot()
            return kq1, kq2, kq3

    kq1, kq2, kq3 = asyncio.run(chay())
    assert kq1["loi"] and kq1["phieu_kho"] == 0 and kq1["phieu_sau_luot_1"] is None
    assert kq2 == {"loi": None, "phieu_kho": 1, "khoan_tien": 2}
    assert kq3 == {"loi": None, "phieu_kho": 0, "khoan_tien": 0}   # đã niêm phong hết: lượt sau không ghi gì
    assert len(sc.la) == 3 and all(d["ledger_index"] is not None for d in [phieu, *tien])
    loai = [json.loads(la)["type"] for la in sc.la]
    assert loai == ["cuu-tro.phieu-kho", "cuu-tro.khoan-tien", "cuu-tro.khoan-tien"]
