# SPDX-License-Identifier: Apache-2.0
"""API nhận / từ chối / hủy / xác nhận nhiệm vụ (#67): quyền theo vai trò JWT và theo đội (Hasura giả),
đúng bước của workflow, signal mang đúng đội. Temporal và gateway /graphql được thay bằng bản giả."""

import json
import time
from dataclasses import dataclass, field
from types import SimpleNamespace

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from temporalio.client import WorkflowExecutionStatus

from cuu_tro_workflow import config
from cuu_tro_workflow.api import app
from cuu_tro_workflow.auth import HASURA_NS, XacThuc
from cuu_tro_workflow.logic import PhanHoi, TrangThaiPhanCong, XacNhan, YeuCauHuy
from cuu_tro_workflow.workflows import SIGNAL_HUY, SIGNAL_NHAN, SIGNAL_TU_CHOI, SIGNAL_XAC_NHAN

KHOA = rsa.generate_private_key(public_exponent=65537, key_size=2048)
ISS = "http://localhost:8080/realms/disaster"
INC = "b0000000-0000-4000-8000-000000000004"
WF = f"phan-cong-{INC}"
DOI_A, DOI_B = "a0000000-0000-4000-8000-00000000000a", "a0000000-0000-4000-8000-00000000000b"
THANH_VIEN = {"cuuho-a": DOI_A, "cuuho-b": DOI_B}


def token(sub: str, *vai_tro: str) -> str:
    now = int(time.time())
    return "Bearer " + jwt.encode(
        {"sub": sub, "iss": ISS, "iat": now, "exp": now + 300, "preferred_username": sub,
         HASURA_NS: {"x-hasura-allowed-roles": list(vai_tro), "x-hasura-user-id": sub}},
        KHOA, algorithm="RS256")


DP, CH_A, CH_B, TN = token("dp", "dieu-phoi"), token("cuuho-a", "cuu-ho"), token("cuuho-b", "cuu-ho"), token("tn", "tinh-nguyen")


@dataclass
class HeThongGia:
    # Tin đang giao cho đội A (theo CSDL / Hasura)
    tin: dict = field(default_factory=lambda: {"id": INC, "status": "phan_cong", "assigned_team_id": DOI_A,
                                               "urgency": "cao"})
    tt: TrangThaiPhanCong = field(default_factory=lambda: TrangThaiPhanCong(incident_id=INC, buoc="cho_nhan", doi_id=DOI_A))
    trang_thai: WorkflowExecutionStatus = WorkflowExecutionStatus.RUNNING
    signals: list = field(default_factory=list)

    def graphql(self, req: httpx.Request) -> httpx.Response:
        claims = jwt.decode(req.headers["Authorization"][7:], options={"verify_signature": False})
        vai_tro, sub = req.headers["X-Hasura-Role"], claims["sub"]
        assert json.loads(req.content)["variables"]["id"] == INC
        thay = vai_tro == "dieu-phoi" or (vai_tro == "cuu-ho" and THANH_VIEN.get(sub) == self.tin["assigned_team_id"])
        return httpx.Response(200, json={"data": {"incidents_by_pk": dict(self.tin) if thay else None}})

    # Temporal client giả: chỉ những gì API dùng
    def get_workflow_handle(self, wid: str):
        assert wid == WF
        he = self

        class Handle:
            async def describe(self):
                return SimpleNamespace(status=he.trang_thai)

            async def query(self, _name, result_type=None):
                return he.tt

            async def signal(self, name, arg):
                he.signals.append((name, arg))

        return Handle()


@pytest.fixture
def ht():
    h = HeThongGia()
    st = app.state
    st.xac_thuc = XacThuc(ISS, lay_khoa=lambda _t: KHOA.public_key())
    st.cfg = config.load()
    st.http = httpx.AsyncClient(base_url="http://apisix:9080", transport=httpx.MockTransport(h.graphql))
    st.temporal = h
    yield h
    for k in ("http", "temporal", "cfg"):
        delattr(st, k)


def goi(path: str, tok: str, body: dict | None = None):
    return TestClient(app).post(f"/{WF}/{path}", headers={"Authorization": tok}, json=body)


def test_cuu_ho_cua_doi_duoc_giao_nhan_nhiem_vu(ht):
    r = goi("nhan", CH_A, {"ghi_chu": "đang tới"})
    assert r.status_code == 202 and r.json()["da_gui"] == SIGNAL_NHAN
    (ten, ph), = ht.signals
    assert isinstance(ph, PhanHoi) and (ph.nguoi, ph.vai_tro, ph.doi_id, ph.ghi_chu) == ("cuuho-a", "cuu-ho", DOI_A, "đang tới")


def test_tu_choi_boi_dieu_phoi_mang_doi_dang_giao(ht):
    r = goi("tu-choi", DP, {"ghi_chu": "đội báo hết xăng"})
    assert r.status_code == 202
    (ten, ph), = ht.signals
    assert ten == SIGNAL_TU_CHOI and (ph.vai_tro, ph.doi_id) == ("dieu-phoi", DOI_A)


@pytest.mark.parametrize("path", ["nhan", "tu-choi", "xac-nhan"])
def test_doi_khac_va_tinh_nguyen_khong_phan_hoi_duoc(ht, path):
    assert goi(path, CH_B).status_code == 403
    assert goi(path, TN).status_code == 403
    assert TestClient(app).post(f"/{WF}/{path}").status_code == 401
    assert not ht.signals


def test_sai_buoc_hoac_workflow_da_xong_thi_409(ht):
    ht.tt.buoc = "cho_xac_nhan"
    assert goi("nhan", CH_A).status_code == 409
    assert goi("tu-choi", CH_A).status_code == 409
    ht.tt.buoc = "cho_nhan"
    ht.trang_thai = WorkflowExecutionStatus.COMPLETED
    assert goi("nhan", CH_A).status_code == 409
    assert not ht.signals


def test_doi_trong_csdl_khac_doi_workflow_dang_giao_thi_409(ht):
    # Workflow vừa phân công lại cho đội B nhưng đội A còn đọc được tin (chưa kịp đổi): từ chối
    ht.tt.doi_id = DOI_B
    assert goi("nhan", CH_A).status_code == 409 and not ht.signals


def test_huy_chi_dieu_phoi_va_chi_truoc_khi_doi_nhan(ht):
    assert goi("huy", CH_A).status_code == 403
    r = goi("huy", DP, {"ly_do": "dân quân đã tới"})
    assert r.status_code == 202
    (ten, yc), = ht.signals
    assert ten == SIGNAL_HUY and isinstance(yc, YeuCauHuy) and (yc.nguoi, yc.ly_do) == ("dp", "dân quân đã tới")
    ht.tt.buoc = "cho_xac_nhan"
    assert goi("huy", DP).status_code == 409


def test_xac_nhan_khi_con_cho_nhan_hoac_dang_cuu(ht):
    assert goi("xac-nhan", CH_A).status_code == 202
    ht.tt.buoc = "cho_xac_nhan"
    assert goi("xac-nhan", DP, {"ghi_chu": "đã đưa lên trạm y tế"}).status_code == 202
    assert [(t, x.doi_id) for t, x in ht.signals if isinstance(x, XacNhan)] == [(SIGNAL_XAC_NHAN, DOI_A)] * 2


def test_workflow_id_sai_dang_thi_404(ht):
    r = TestClient(app).post("/phan-cong-khong-phai-uuid/nhan", headers={"Authorization": DP})
    assert r.status_code == 404
