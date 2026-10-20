# SPDX-License-Identifier: Apache-2.0
"""API mỏng khởi chạy và theo dõi workflow. Chạy: uvicorn cuu_tro_workflow.api:app

Client gọi qua API Gateway: APISIX route /workflow/* kiểm JWT + WAF + rate limit rồi bỏ tiền tố
/workflow (core/apisix/apisix.yaml). Đường dẫn bên dưới là đường dẫn SAU khi bỏ tiền tố:
  POST /hello                       chạy workflow Hello (mọi vai trò)
  POST /phan-cong/{incident_id}     khởi chạy PhanCongCuuHo (chỉ dieu-phoi)
  GET  /{workflow_id}               trạng thái (dieu-phoi; cuu-ho của đội được gán)
  POST /{workflow_id}/xac-nhan      signal "đã cứu" (dieu-phoi; cuu-ho của đội được gán)
  GET  /healthz                     sống + kết nối Temporal (healthcheck của container)
"Cuu-ho của đội được gán" không viết lại luật ở đây: API hỏi Hasura qua gateway bằng chính JWT
người dùng; luật lọc theo đội của Hasura metadata (#26) trả null thì người dùng không có quyền.
"""

import re
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import timedelta
from typing import Annotated, Any

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field
from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.service import RPCError

from . import config
from .auth import VAI_TRO_CUU_HO, VAI_TRO_DIEU_PHOI, NguoiDung, XacThuc, can_vai_tro
from .logic import ThamSoPhanCong, TrangThaiPhanCong, XacNhan
from .workflows import QUERY_TRANG_THAI, SIGNAL_XAC_NHAN, Hello, PhanCongCuuHo

TIEN_TO_PHAN_CONG = "phan-cong-"
_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_WF_ID = re.compile(rf"^{TIEN_TO_PHAN_CONG}({_UUID})$")

Q_TIN = "query($id: uuid!) { incidents_by_pk(id: $id) { id status assigned_team_id } }"


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = config.load()
    st = app.state
    st.cfg = cfg
    if not hasattr(st, "xac_thuc"):
        st.xac_thuc = XacThuc(cfg.jwt_issuer, jwks_url=cfg.jwks_url)
    if not hasattr(st, "temporal"):
        st.temporal = await Client.connect(cfg.temporal_address, namespace=cfg.temporal_namespace)
    async with httpx.AsyncClient(base_url=cfg.gateway_url, timeout=10) as http:
        st.http = http
        yield


# Đường dẫn công khai /workflow/... phía sau gateway: uvicorn --root-path /workflow (compose)
app = FastAPI(
    title="cuu-tro workflow API",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)


def nguoi_dung(request: Request, authorization: Annotated[str | None, Header()] = None) -> NguoiDung:
    # Hàm đồng bộ: FastAPI chạy trong threadpool, lần đầu tải JWKS không chặn event loop
    return request.app.state.xac_thuc.kiem(authorization)


NguoiDungDep = Annotated[NguoiDung, Depends(nguoi_dung)]


async def hoi_tin(request: Request, nd: NguoiDung, vai_tro: str, incident_id: str) -> dict[str, Any] | None:
    """Đọc tin kêu cứu qua gateway /graphql với JWT và vai trò của người dùng (None = không thấy)."""
    r = await request.app.state.http.post(
        "/graphql",
        json={"query": Q_TIN, "variables": {"id": incident_id}},
        headers={"Authorization": f"Bearer {nd.token}", "X-Hasura-Role": vai_tro},
    )
    if r.status_code != 200:
        raise HTTPException(502, f"Gateway /graphql trả HTTP {r.status_code}")
    body = r.json()
    if body.get("errors"):
        raise HTTPException(502, f"Hasura báo lỗi: {body['errors'][0].get('message')}")
    return body["data"]["incidents_by_pk"]


async def kiem_quyen_workflow(request: Request, nd: NguoiDung, workflow_id: str) -> str:
    """Trả incident_id nếu người dùng được xem/xác nhận workflow phân công này, nếu không 403/404."""
    m = _WF_ID.match(workflow_id)
    if not m:
        raise HTTPException(404, "Không có workflow này")
    incident_id = m.group(1)
    can_vai_tro(nd, VAI_TRO_DIEU_PHOI, VAI_TRO_CUU_HO)
    if nd.co(VAI_TRO_DIEU_PHOI):
        return incident_id
    if await hoi_tin(request, nd, VAI_TRO_CUU_HO, incident_id) is None:
        raise HTTPException(403, "Tin kêu cứu không được phân công cho đội của bạn")
    return incident_id


async def trang_thai_wf(request: Request, workflow_id: str) -> tuple[str, TrangThaiPhanCong]:
    handle = request.app.state.temporal.get_workflow_handle(workflow_id)
    try:
        desc = await handle.describe()
        tt = await handle.query(QUERY_TRANG_THAI, result_type=TrangThaiPhanCong)
    except RPCError as e:
        raise HTTPException(404, f"Không có workflow {workflow_id}") from e
    return desc.status.name if desc.status else "UNKNOWN", tt


class HelloVao(BaseModel):
    ten: str = Field("bạn", min_length=1, max_length=100)


class XacNhanVao(BaseModel):
    ghi_chu: str = Field("", max_length=500)


@app.get("/healthz")
async def healthz(request: Request) -> dict[str, str]:
    await request.app.state.temporal.service_client.check_health()
    return {"status": "ok"}


@app.post("/hello")
async def hello(request: Request, nd: NguoiDungDep, vao: HelloVao | None = None) -> dict[str, str]:
    st = request.app.state
    wf_id = f"hello-{uuid.uuid4()}"
    ket_qua = await st.temporal.execute_workflow(
        Hello.run, (vao or HelloVao()).ten, id=wf_id, task_queue=st.cfg.task_queue,
        execution_timeout=timedelta(seconds=30),
    )
    return {"workflow_id": wf_id, "ket_qua": ket_qua, "nguoi_goi": nd.ten_dang_nhap}


@app.post("/phan-cong/{incident_id}", status_code=202)
async def phan_cong(request: Request, incident_id: uuid.UUID, nd: NguoiDungDep) -> dict[str, str]:
    can_vai_tro(nd, VAI_TRO_DIEU_PHOI)
    st = request.app.state
    tin = await hoi_tin(request, nd, VAI_TRO_DIEU_PHOI, str(incident_id))
    if tin is None:
        raise HTTPException(404, f"Không có tin kêu cứu {incident_id}")
    if tin["status"] != "tiep_nhan":
        raise HTTPException(409, f"Tin kêu cứu đang ở trạng thái {tin['status']}, chỉ phân công tin tiep_nhan")
    cfg = st.cfg
    ts = ThamSoPhanCong(
        incident_id=str(incident_id),
        nguoi_khoi_chay=nd.ten_dang_nhap or nd.sub,
        ban_kinh_m=cfg.ban_kinh_m,
        han_xac_nhan_giay=cfg.han_xac_nhan_giay,
        so_lan_tim_doi=cfg.so_lan_tim_doi,
        cho_tim_lai_giay=cfg.cho_tim_lai_giay,
    )
    wf_id = f"{TIEN_TO_PHAN_CONG}{incident_id}"
    try:
        handle = await st.temporal.start_workflow(
            PhanCongCuuHo.run,
            ts,
            id=wf_id,
            task_queue=cfg.task_queue,
            # Một tin chỉ có một luồng phân công đang chạy; chạy xong được khởi chạy lại
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
            id_conflict_policy=WorkflowIDConflictPolicy.FAIL,
        )
    except WorkflowAlreadyStartedError as e:
        raise HTTPException(409, f"Workflow {wf_id} đang chạy") from e
    return {"workflow_id": wf_id, "run_id": handle.result_run_id or "", "incident_id": str(incident_id)}


@app.get("/{workflow_id}")
async def xem(request: Request, workflow_id: str, nd: NguoiDungDep) -> dict[str, Any]:
    await kiem_quyen_workflow(request, nd, workflow_id)
    trang_thai, tt = await trang_thai_wf(request, workflow_id)
    return {"workflow_id": workflow_id, "trang_thai": trang_thai, "chi_tiet": asdict(tt)}


@app.post("/{workflow_id}/xac-nhan", status_code=202)
async def xac_nhan(
    request: Request, workflow_id: str, nd: NguoiDungDep, vao: XacNhanVao | None = None
) -> dict[str, str]:
    await kiem_quyen_workflow(request, nd, workflow_id)
    trang_thai, tt = await trang_thai_wf(request, workflow_id)
    if trang_thai != WorkflowExecutionStatus.RUNNING.name or tt.buoc != "cho_xac_nhan":
        raise HTTPException(409, f"Workflow không chờ xác nhận (trạng thái {trang_thai}, bước {tt.buoc})")
    vai_tro = VAI_TRO_DIEU_PHOI if nd.co(VAI_TRO_DIEU_PHOI) else VAI_TRO_CUU_HO
    xn = XacNhan(nguoi=nd.ten_dang_nhap or nd.sub, vai_tro=vai_tro, ghi_chu=(vao or XacNhanVao()).ghi_chu)
    await request.app.state.temporal.get_workflow_handle(workflow_id).signal(SIGNAL_XAC_NHAN, xn)
    return {"workflow_id": workflow_id, "da_gui": SIGNAL_XAC_NHAN}

