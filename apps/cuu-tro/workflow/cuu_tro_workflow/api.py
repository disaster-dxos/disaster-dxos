# SPDX-License-Identifier: Apache-2.0
"""API mỏng khởi chạy và theo dõi workflow. Chạy: uvicorn cuu_tro_workflow.api:app

Client gọi qua API Gateway: APISIX route /workflow/* kiểm JWT + WAF + rate limit rồi bỏ tiền tố
/workflow (core/apisix/apisix.yaml). Đường dẫn bên dưới là đường dẫn SAU khi bỏ tiền tố:
  POST /hello                       chạy workflow Hello (mọi vai trò)
  POST /phan-cong/{incident_id}     khởi chạy PhanCongCuuHo (chỉ dieu-phoi)
  GET  /{workflow_id}               trạng thái (dieu-phoi; cuu-ho của đội được gán)
  POST /{workflow_id}/xac-nhan      signal "đã cứu" (dieu-phoi; cuu-ho của đội được gán)
  GET  /healthz                     sống + kết nối Temporal (healthcheck của container)
Ảnh hiện trường (#27, luật quyền: cuu_tro_workflow/anh.py, apps/cuu-tro/README.md):
  POST /tai-len/su-co/{incident_id}/anh   body = nội dung ảnh (route gateway /workflow/tai-len/*)
  GET  /su-co/{incident_id}/anh           liệt kê ảnh của tin kèm link xem ngắn hạn
  GET  /anh/{media_id}/link?han_giay=N    link xem presigned ngắn hạn cho một ảnh
"Cuu-ho của đội được gán" không viết lại luật ở đây: API hỏi Hasura qua gateway bằng chính JWT
người dùng; luật lọc theo đội của Hasura metadata (#26) trả null thì người dùng không có quyền.
"""

import hashlib
import logging
import re
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import asyncpg
import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.service import RPCError

from . import anh, config
from .auth import VAI_TRO_CUU_HO, VAI_TRO_DIEU_PHOI, NguoiDung, XacThuc, can_vai_tro
from .s3 import KhoAnh, LoiS3
from .logic import ThamSoPhanCong, TrangThaiPhanCong, XacNhan
from .workflows import QUERY_TRANG_THAI, SIGNAL_XAC_NHAN, Hello, PhanCongCuuHo

TIEN_TO_PHAN_CONG = "phan-cong-"
_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_WF_ID = re.compile(rf"^{TIEN_TO_PHAN_CONG}({_UUID})$")

Q_TIN = "query($id: uuid!) { incidents_by_pk(id: $id) { id status assigned_team_id } }"
# Ảnh hiện trường: chỉ hỏi cột mà cả 3 vai trò được đọc (tinh-nguyen không có assigned_team_id;
# hỏi cột không có quyền thì Hasura báo lỗi validation chứ không trả null)
Q_TIN_ANH = "query($id: uuid!) { incidents_by_pk(id: $id) { id status } }"
# Cột chung mọi vai trò được đọc (tinh-nguyen không có uploaded_by, uploader_role)
_COT_ANH = "id incident_id object_key content_type size_bytes sha256 uploaded_at scan_status"
Q_ANH_CUA_TIN = (
    "query($id: uuid!) { incidents_by_pk(id: $id) { id media(order_by: {uploaded_at: asc}) { "
    + _COT_ANH + " uploaded_by uploader_role } } }"
)
Q_ANH = "query($id: uuid!) { incident_media_by_pk(id: $id) { " + _COT_ANH + " } }"

log = logging.getLogger("cuu_tro_workflow.api")


class SoAnh:
    """Ghi siêu dữ liệu ảnh bằng role dịch vụ cuu_tro_app (chỉ SELECT/INSERT incident_media, migration 0005)."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def them(self, **d: Any) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            """INSERT INTO cuu_tro.incident_media
                 (id, incident_id, object_key, content_type, size_bytes, sha256, uploaded_by, uploader_role)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
               RETURNING uploaded_at, scan_status""",
            uuid.UUID(d["id"]), uuid.UUID(d["incident_id"]), d["object_key"], d["content_type"],
            d["size_bytes"], d["sha256"], d["uploaded_by"], d["uploader_role"],
        )
        return {"uploaded_at": row["uploaded_at"].isoformat(), "scan_status": row["scan_status"]}


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = config.load()
    st = app.state
    st.cfg = cfg
    if not hasattr(st, "xac_thuc"):
        st.xac_thuc = XacThuc(cfg.jwt_issuer, jwks_url=cfg.jwks_url)
    if not hasattr(st, "temporal"):
        st.temporal = await Client.connect(cfg.temporal_address, namespace=cfg.temporal_namespace)
    pool = None
    if not hasattr(st, "so_anh") and cfg.db_url:
        pool = await asyncpg.create_pool(cfg.db_url, min_size=0, max_size=4)
        st.so_anh = SoAnh(pool)
    try:
        async with httpx.AsyncClient(base_url=cfg.gateway_url, timeout=10) as http, \
                httpx.AsyncClient(timeout=30) as http_s3:
            st.http = http
            if not hasattr(st, "kho_anh"):
                st.kho_anh = KhoAnh(endpoint=cfg.s3_endpoint, bucket=cfg.anh_bucket, access_key=cfg.s3_access_key,
                                    secret_key=cfg.s3_secret_key, gateway_public_url=cfg.gateway_public_url,
                                    http=http_s3, region=cfg.s3_region)
            yield
    finally:
        if pool is not None:
            await pool.close()


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


async def hoi_hasura(request: Request, nd: NguoiDung, vai_tro: str, query: str, bien: dict[str, Any]) -> dict[str, Any]:
    """Truy vấn GraphQL qua gateway /graphql bằng JWT + vai trò của người dùng (Hasura lọc theo hàng)."""
    r = await request.app.state.http.post(
        "/graphql",
        json={"query": query, "variables": bien},
        headers={"Authorization": f"Bearer {nd.token}", "X-Hasura-Role": vai_tro},
    )
    if r.status_code != 200:
        raise HTTPException(502, f"Gateway /graphql trả HTTP {r.status_code}")
    body = r.json()
    if body.get("errors"):
        raise HTTPException(502, f"Hasura báo lỗi: {body['errors'][0].get('message')}")
    return body["data"]


async def hoi_tin(request: Request, nd: NguoiDung, vai_tro: str, incident_id: str) -> dict[str, Any] | None:
    """Đọc tin kêu cứu qua gateway /graphql với JWT và vai trò của người dùng (None = không thấy)."""
    return (await hoi_hasura(request, nd, vai_tro, Q_TIN, {"id": incident_id}))["incidents_by_pk"]


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


# ---------------- Ảnh hiện trường (#27) ----------------
# Khai báo trước GET /{workflow_id} (một đoạn path); các path dưới đều có nhiều đoạn.

def _tu_choi(tc: anh.TuChoi | None) -> None:
    if tc is not None:
        raise HTTPException(tc.ma, tc.ly_do)


def _link(request: Request, object_key: str, han_giay: int) -> dict[str, Any]:
    het_han = datetime.now(timezone.utc) + timedelta(seconds=han_giay)
    return {"url": request.app.state.kho_anh.link_xem(object_key, han_giay), "han_giay": han_giay,
            "het_han_luc": het_han.isoformat(timespec="seconds")}


async def doc_body_gioi_han(request: Request, toi_da: int) -> bytes:
    """Đọc body theo luồng, dừng ngay khi vượt `toi_da` byte (413); không tin Content-Length."""
    buf = bytearray()
    async for phan in request.stream():
        buf += phan
        if len(buf) > toi_da:
            raise HTTPException(413, f"Ảnh vượt {toi_da} byte")
    return bytes(buf)


@app.post("/tai-len/su-co/{incident_id}/anh", status_code=201)
async def tai_anh(request: Request, incident_id: uuid.UUID, nd: NguoiDungDep, response: Response) -> dict[str, Any]:
    st = request.app.state
    cfg = st.cfg
    can_vai_tro(nd, *anh.UU_TIEN)
    vai_tro = anh.vai_tro_chinh(nd)
    # Content-Length khai báo quá lớn: từ chối trước khi hỏi Hasura
    khai_bao = request.headers.get("content-length")
    if khai_bao and khai_bao.isdigit() and int(khai_bao) > cfg.anh_max_bytes:
        raise HTTPException(413, f"Ảnh vượt {cfg.anh_max_bytes} byte")
    tin = (await hoi_hasura(request, nd, vai_tro, Q_TIN_ANH, {"id": str(incident_id)}))["incidents_by_pk"]
    _tu_choi(anh.quyen_tai_len(vai_tro, tin))

    du_lieu = await doc_body_gioi_han(request, cfg.anh_max_bytes)
    if not du_lieu:
        raise HTTPException(400, "Body rỗng: gửi nội dung ảnh trong body request")
    # Loại thật từ magic bytes; Content-Type và tên tệp của client bị bỏ qua
    loai = anh.nhan_dang(du_lieu[: anh.SO_BYTE_DAU])
    if loai is None:
        raise HTTPException(415, "Chỉ nhận ảnh JPEG, PNG, WebP (kiểm theo nội dung tệp, không theo đuôi hay Content-Type)")

    media_id = str(uuid.uuid4())
    key = anh.object_key(str(incident_id), media_id, loai)
    sha = hashlib.sha256(du_lieu).hexdigest()
    try:
        await st.kho_anh.ghi(key, du_lieu, loai)
    except (LoiS3, httpx.HTTPError) as e:
        log.error("ghi S3 lỗi: %s", e)
        raise HTTPException(502, "Không ghi được ảnh lên kho lưu trữ") from e
    ban_ghi = {"id": media_id, "incident_id": str(incident_id), "object_key": key, "content_type": loai,
               "size_bytes": len(du_lieu), "sha256": sha, "uploaded_by": nd.sub, "uploader_role": vai_tro}
    try:
        them = await st.so_anh.them(**ban_ghi)
    except Exception as e:
        # Không để object mồ côi trên S3 khi không ghi được siêu dữ liệu
        log.error("ghi incident_media lỗi: %s", e)
        try:
            await st.kho_anh.xoa(key)
        except (LoiS3, httpx.HTTPError) as e2:
            log.error("xóa object mồ côi %s lỗi: %s", key, e2)
        raise HTTPException(500, "Không ghi được thông tin ảnh") from e
    response.headers["Cache-Control"] = "no-store"
    return {**ban_ghi, **them, "link": _link(request, key, cfg.anh_link_han_giay)}


@app.get("/su-co/{incident_id}/anh")
async def liet_ke_anh(request: Request, incident_id: uuid.UUID, nd: NguoiDungDep, response: Response) -> dict[str, Any]:
    can_vai_tro(nd, VAI_TRO_DIEU_PHOI, VAI_TRO_CUU_HO)
    vai_tro = anh.vai_tro_chinh(nd)
    data = await hoi_hasura(request, nd, vai_tro, Q_ANH_CUA_TIN, {"id": str(incident_id)})
    tin = data["incidents_by_pk"]
    _tu_choi(anh.quyen_liet_ke(vai_tro, tin))
    han = request.app.state.cfg.anh_link_han_giay
    response.headers["Cache-Control"] = "no-store"
    return {"incident_id": str(incident_id),
            "anh": [{**m, "link": _link(request, m["object_key"], han)} for m in tin["media"]]}


@app.get("/anh/{media_id}/link")
async def link_anh(
    request: Request, media_id: uuid.UUID, nd: NguoiDungDep, response: Response,
    han_giay: Annotated[int | None, Query(ge=1)] = None,
) -> dict[str, Any]:
    toi_da = request.app.state.cfg.anh_link_han_giay
    if han_giay is not None and han_giay > toi_da:
        raise HTTPException(422, f"han_giay tối đa {toi_da}")
    can_vai_tro(nd, *anh.UU_TIEN)
    vai_tro = anh.vai_tro_chinh(nd)
    m = (await hoi_hasura(request, nd, vai_tro, Q_ANH, {"id": str(media_id)}))["incident_media_by_pk"]
    _tu_choi(anh.quyen_xem(vai_tro, m))
    response.headers["Cache-Control"] = "no-store"
    return {**m, "link": _link(request, m["object_key"], han_giay or toi_da)}


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

