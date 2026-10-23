# SPDX-License-Identifier: Apache-2.0
"""API mỏng khởi chạy và theo dõi workflow. Chạy: uvicorn cuu_tro_workflow.api:app

Client gọi qua API Gateway: APISIX route /workflow/* kiểm JWT + WAF + rate limit rồi bỏ tiền tố
/workflow (core/apisix/apisix.yaml). Đường dẫn bên dưới là đường dẫn SAU khi bỏ tiền tố:
  POST /hello                       chạy workflow Hello (mọi vai trò)
  POST /phan-cong/{incident_id}     khởi chạy tay PhanCongCuuHo (chỉ dieu-phoi). Tin mới đã TỰ khởi
                                    chạy (#67, khoi_chay.py); dùng khi luồng tự động đã dừng (báo điều phối)
  GET  /{workflow_id}               trạng thái (dieu-phoi; cuu-ho của đội được gán)
  POST /{workflow_id}/nhan          đội nhận nhiệm vụ trong hạn (dieu-phoi; cuu-ho của đội được gán)
  POST /{workflow_id}/tu-choi       đội từ chối → workflow giao đội kế tiếp (dieu-phoi; cuu-ho của đội)
  POST /{workflow_id}/huy           dừng luồng khi đội chưa nhận, gỡ đội (chỉ dieu-phoi)
  POST /{workflow_id}/xac-nhan      signal "đã cứu" (dieu-phoi; cuu-ho của đội được gán)
  GET  /healthz                     sống + kết nối Temporal (healthcheck của container)
Tiếp nhận tin kêu cứu (#66, Poka-yoke: cuu_tro_workflow/keu_cuu.py, apps/cuu-tro/README.md):
  POST /keu-cuu                     tạo tin (dieu-phoi, tinh-nguyen); 201 · 409 trùng kèm mã tin đang mở ·
                                    422 lỗi theo trường. Route gateway riêng /workflow/keu-cuu (rate limit chặt)
Ảnh hiện trường (#27, luật quyền: cuu_tro_workflow/anh.py, apps/cuu-tro/README.md):
  POST /tai-len/su-co/{incident_id}/anh   body = nội dung ảnh (route gateway /workflow/tai-len/*)
  GET  /su-co/{incident_id}/anh           liệt kê ảnh của tin kèm link xem ngắn hạn
  GET  /anh/{media_id}/link?han_giay=N    link xem presigned ngắn hạn cho một ảnh
Sổ cái minh bạch (#28, luồng: cuu_tro_workflow/so_cai.py, apps/cuu-tro/README.md):
  POST /kho/phieu                   lập phiếu nhập/xuất (chỉ dieu-phoi) rồi ghi lá lên sổ cái
  POST /kho/phieu/{id}/ghi-so       ghi lại sổ cái cho phiếu chưa ghi (chỉ dieu-phoi; gửi lại an toàn)
  GET  /minh-bach/phieu/{ma}        CÔNG KHAI, không cần đăng nhập (route /workflow/minh-bach/*):
                                    bản ghi không định danh + trạng thái xác minh trên sổ cái
Thông báo realtime (#68, cuu_tro_workflow/thong_bao.py):
  GET  /realtime/token              token kết nối Centrifugo ngắn hạn (dieu-phoi; quan-tri khi realm có),
                                    kênh server-side "dieu-phoi"; web mở WebSocket /realtime/websocket
"Cuu-ho của đội được gán" không viết lại luật ở đây: API hỏi Hasura qua gateway bằng chính JWT
người dùng; luật lọc theo đội của Hasura metadata (#26) trả null thì người dùng không có quyền.
"""

import hashlib
import json
import logging
import re
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated, Any, Literal

import asyncpg
import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.common import Priority, WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.service import RPCError

from . import anh, config, keu_cuu, so_cai, thong_bao
from .auth import VAI_TRO_CUU_HO, VAI_TRO_DIEU_PHOI, VAI_TRO_TINH_NGUYEN, NguoiDung, XacThuc, can_vai_tro
from .s3 import KhoAnh, LoiS3
from .logic import PhanHoi, TrangThaiPhanCong, XacNhan, YeuCauHuy, uu_tien
from .workflows import (
    BUOC_CHO_NHAN,
    BUOC_CHO_XAC_NHAN,
    BUOC_XONG,
    QUERY_TRANG_THAI,
    SIGNAL_HUY,
    SIGNAL_NHAN,
    SIGNAL_TU_CHOI,
    SIGNAL_XAC_NHAN,
    Hello,
    PhanCongCuuHo,
)

TIEN_TO_PHAN_CONG = "phan-cong-"
_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_WF_ID = re.compile(rf"^{TIEN_TO_PHAN_CONG}({_UUID})$")

Q_TIN = "query($id: uuid!) { incidents_by_pk(id: $id) { id status assigned_team_id urgency } }"
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


class SoPhieu:
    """Phiếu nhập/xuất bằng role dịch vụ cuu_tro_app (migration 0006): lập phiếu, đọc lại để băm,
    điền ledger_* một lần. Không đọc created_by (người lập phiếu không lên trang công khai)."""

    _COT = """m.id, m.supply_id, m.direction, m.quantity, m.note, m.shelter_id, m.created_at,
              m.ledger_index, m.ledger_leaf_hash, m.ledger_logged_at"""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def them(self, *, supply_id: str, direction: str, quantity: Decimal, note: str | None,
                   shelter_id: str | None, created_by: str) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            f"""INSERT INTO cuu_tro.supply_movements AS m (supply_id, direction, quantity, note, shelter_id, created_by)
                VALUES ($1, $2, $3, $4, $5, $6) RETURNING {self._COT}""",
            uuid.UUID(supply_id), direction, quantity, note, uuid.UUID(shelter_id) if shelter_id else None, created_by,
        )
        return dict(row)

    async def doc(self, ma: str) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            f"""SELECT {self._COT}, s.item_name, s.unit, s.storage_name, sh.name AS shelter_name
                  FROM cuu_tro.supply_movements m
                  JOIN cuu_tro.supplies s ON s.id = m.supply_id
                  LEFT JOIN cuu_tro.shelters sh ON sh.id = m.shelter_id
                 WHERE m.id = $1""",
            uuid.UUID(ma),
        )
        return dict(row) if row else None

    async def ghi_so(self, ma: str, index: int, leaf_hash: bytes) -> datetime | None:
        """Điền ledger_* nếu phiếu chưa ghi; None nếu đã có (trigger 0001 chặn ghi đè)."""
        return await self._pool.fetchval(
            """UPDATE cuu_tro.supply_movements
                  SET ledger_index = $2, ledger_leaf_hash = $3, ledger_logged_at = now()
                WHERE id = $1 AND ledger_index IS NULL
            RETURNING ledger_logged_at""",
            uuid.UUID(ma), index, leaf_hash,
        )


class SoTin:
    """Tạo tin kêu cứu bằng role dịch vụ cuu_tro_app (migration 0008: INSERT đúng các cột người báo được
    nhập; status/assigned_team_id lấy mặc định). Trigger của CSDL chặn trùng (0001) và ghi outbox để tự
    phân công (0007) trong cùng transaction với tin."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def them(self, tin: keu_cuu.TinKeuCuu, created_by: str) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            """INSERT INTO cuu_tro.incidents
                 (description, location, address_text, people_count, urgency, reporter_phone, reporter_name,
                  source, created_by)
               VALUES ($1, ST_SetSRID(ST_MakePoint($2, $3), 4326)::geography, $4, $5, $6, $7, $8, $9, $10)
               RETURNING id, status, urgency, people_count, created_at""",
            tin.description, tin.lon, tin.lat, tin.address_text, tin.people_count, tin.urgency,
            tin.reporter_phone, tin.reporter_name, tin.source, created_by,
        )
        return dict(row)


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
    if not (hasattr(st, "so_anh") and hasattr(st, "so_phieu") and hasattr(st, "so_tin")) and cfg.db_url:
        pool = await asyncpg.create_pool(cfg.db_url, min_size=0, max_size=4)
        if not hasattr(st, "so_anh"):
            st.so_anh = SoAnh(pool)
        if not hasattr(st, "so_phieu"):
            st.so_phieu = SoPhieu(pool)
        if not hasattr(st, "so_tin"):
            st.so_tin = SoTin(pool)
    try:
        async with httpx.AsyncClient(base_url=cfg.gateway_url, timeout=10) as http, \
                httpx.AsyncClient(timeout=30) as http_s3, \
                httpx.AsyncClient(base_url=cfg.ledger_url, timeout=20) as http_ledger:
            st.http = http
            if not hasattr(st, "so_cai"):
                st.so_cai = so_cai.SoCai(http_ledger, cfg.ledger_write_token, cfg.ledger_verifier_key)
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
    version="0.2.0",
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


async def kiem_quyen_workflow(request: Request, nd: NguoiDung, workflow_id: str) -> tuple[str, str | None]:
    """Kiểm người dùng được xem/phản hồi workflow phân công này, nếu không 403/404.

    Trả (incident_id, đội của người dùng): dieu-phoi → None; cuu-ho → đội đang được giao tin theo
    Hasura (luật lọc theo thành viên đội, #26), dùng để workflow bỏ phản hồi của đội đã bị thay.
    """
    m = _WF_ID.match(workflow_id)
    if not m:
        raise HTTPException(404, "Không có workflow này")
    incident_id = m.group(1)
    can_vai_tro(nd, VAI_TRO_DIEU_PHOI, VAI_TRO_CUU_HO)
    if nd.co(VAI_TRO_DIEU_PHOI):
        return incident_id, None
    tin = await hoi_tin(request, nd, VAI_TRO_CUU_HO, incident_id)
    if tin is None:
        raise HTTPException(403, "Tin kêu cứu không được phân công cho đội của bạn")
    return incident_id, tin["assigned_team_id"]


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


class HuyVao(BaseModel):
    ly_do: str = Field("", max_length=500)


@app.get("/healthz")
async def healthz(request: Request) -> dict[str, str]:
    await request.app.state.temporal.service_client.check_health()
    return {"status": "ok"}


@app.get("/realtime/token")
async def realtime_token(request: Request, response: Response, nd: NguoiDungDep) -> dict[str, Any]:
    """Token kết nối Centrifugo cho web điều phối. Không cache: token chỉ dùng một phiên kết nối."""
    kenh = thong_bao.kenh_cua(nd.vai_tro)
    if not kenh:
        raise HTTPException(403, f"Cần vai trò: {', '.join(thong_bao.VAI_TRO_NHAN)}")
    cfg = request.app.state.cfg
    if not cfg.realtime_token_secret:
        raise HTTPException(503, "Chưa cấu hình thông báo realtime (REALTIME_TOKEN_SECRET)")
    response.headers["Cache-Control"] = "no-store"
    han = cfg.realtime_token_han_giay
    return {"token": thong_bao.ky_token(nd.sub, kenh, cfg.realtime_token_secret, han), "han_giay": han,
            "kenh": kenh}


@app.post("/keu-cuu", status_code=201)
async def keu_cuu_moi(request: Request, nd: NguoiDungDep, response: Response) -> dict[str, Any]:
    """Tiếp nhận tin kêu cứu (#66). Body JSON: lat, lon, reporter_phone, description bắt buộc; urgency,
    people_count, address_text, reporter_name, source tùy chọn. Lỗi trả {"detail": {"ma", "thong_bao", …}}."""
    can_vai_tro(nd, VAI_TRO_DIEU_PHOI, VAI_TRO_TINH_NGUYEN)
    st = request.app.state
    # Body JSON tự đọc (không qua model pydantic) để lỗi theo trường bằng tiếng Việt, đủ mọi trường sai
    raw = await doc_body_gioi_han(request, keu_cuu.BODY_TOI_DA, "Nội dung tin kêu cứu")
    try:
        d = json.loads(raw)
    except ValueError:
        loi = keu_cuu.LoiTruong("body", "Nội dung gửi lên không phải JSON hợp lệ.")
        raise HTTPException(422, keu_cuu.loi_422([loi])) from None
    kq = keu_cuu.kiem_tra(d, st.cfg.keu_cuu_vung)
    if isinstance(kq, list):
        raise HTTPException(422, keu_cuu.loi_422(kq))
    try:
        dong = await st.so_tin.them(kq, nd.sub)
    except asyncpg.UniqueViolationError as e:
        trung = keu_cuu.tin_trung_tu_detail(e.detail) if e.constraint_name == "incidents_no_duplicate" else None
        if trung is None:
            raise
        # Chỉ ghi mã tin đang mở; không ghi SĐT
        log.info("tin kêu cứu trùng tin đang mở %s, không tạo mới", trung["incident_id"])
        raise HTTPException(409, keu_cuu.loi_409(trung)) from None
    except (asyncpg.CheckViolationError, asyncpg.NotNullViolationError) as e:
        # API đã kiểm trước; tới đây là lệch giữa API và ràng buộc CSDL. Không ghi thông điệp (có thể chứa giá trị)
        log.error("CSDL từ chối tin kêu cứu: %s %s", type(e).__name__, e.constraint_name)
        loi = keu_cuu.LoiTruong("body", "Dữ liệu không qua được ràng buộc của CSDL.")
        raise HTTPException(422, keu_cuu.loi_422([loi])) from None
    response.headers["Cache-Control"] = "no-store"
    return {
        "id": str(dong["id"]),
        "status": dong["status"],
        "urgency": dong["urgency"],
        "people_count": dong["people_count"],
        "lat": kq.lat,
        "lon": kq.lon,
        "created_at": dong["created_at"].isoformat(),
        # Trigger outbox (0007) đã xếp tin vào hàng phân công tự động; bản đồ thấy tin qua subscription (#60)
        "phan_cong": "tu_dong",
    }


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
    ts = config.tham_so_phan_cong(cfg, str(incident_id), nd.ten_dang_nhap or nd.sub)
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
            priority=Priority(priority_key=uu_tien(tin.get("urgency"))),
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


async def doc_body_gioi_han(request: Request, toi_da: int, ten: str = "Ảnh") -> bytes:
    """Đọc body theo luồng, dừng ngay khi vượt `toi_da` byte (413); không tin Content-Length."""
    buf = bytearray()
    async for phan in request.stream():
        buf += phan
        if len(buf) > toi_da:
            raise HTTPException(413, f"{ten} vượt {toi_da} byte")
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


# ---------------- Sổ cái minh bạch (#28) ----------------
# Khai báo trước GET /{workflow_id}; mọi path dưới đều có nhiều đoạn.

class PhieuVao(BaseModel):
    supply_id: uuid.UUID
    direction: Literal["nhap", "xuat"]
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    # Ghi chú hiện trên trang công khai: lý do/chứng từ, KHÔNG ghi tên, SĐT, CCCD
    note: str | None = Field(None, max_length=200)
    shelter_id: uuid.UUID | None = None


async def ghi_so_phieu(st: Any, dong: dict[str, Any]) -> dict[str, Any]:
    """Gửi lá của phiếu lên sổ cái và điền ledger_*. Lỗi sổ cái → phiếu vẫn còn, trạng thái chua_ghi_so."""
    ban_ghi = so_cai.ban_ghi_chuan_hoa(dong)
    try:
        kq = await st.so_cai.ghi(so_cai.la_cho_phieu(ban_ghi))
    except so_cai.LoiSoCai as e:
        log.error("ghi sổ cái phiếu %s lỗi: %s", ban_ghi["id"], e)
        return {"trang_thai": so_cai.CHUA_GHI_SO, "loi": str(e)}
    lh = bytes.fromhex(kq["leaf_hash"])
    luc = await st.so_phieu.ghi_so(ban_ghi["id"], kq["index"], lh)
    return {"trang_thai": "da_ghi", "index": kq["index"], "leaf_hash": kq["leaf_hash"],
            "tree_size": kq.get("tree_size"), "trung": bool(kq.get("duplicate")),
            "logged_at": luc.isoformat() if luc else None}


def _phieu_ra(dong: dict[str, Any]) -> dict[str, Any]:
    ban_ghi = so_cai.ban_ghi_chuan_hoa(dong)
    return {"ban_ghi_chuan_hoa": ban_ghi, "sha256": so_cai.sha256_ban_ghi(ban_ghi)}


@app.post("/kho/phieu", status_code=201)
async def lap_phieu(request: Request, vao: PhieuVao, nd: NguoiDungDep, response: Response) -> dict[str, Any]:
    can_vai_tro(nd, VAI_TRO_DIEU_PHOI)
    if so_cai.co_so_dinh_danh(vao.note):
        raise HTTPException(422, "Ghi chú hiện công khai: không ghi SĐT, CCCD (dãy số bắt đầu bằng 0)")
    st = request.app.state
    try:
        dong = await st.so_phieu.them(
            supply_id=str(vao.supply_id), direction=vao.direction, quantity=vao.quantity,
            note=vao.note or None, shelter_id=str(vao.shelter_id) if vao.shelter_id else None,
            created_by=nd.ten_dang_nhap or nd.sub,
        )
    except asyncpg.CheckViolationError as e:
        raise HTTPException(409, "Xuất quá số lượng tồn kho") from e
    except asyncpg.ForeignKeyViolationError as e:
        raise HTTPException(404, "Không có mặt hàng hoặc điểm nhận này") from e
    ghi = await ghi_so_phieu(st, dong)
    if ghi["trang_thai"] != "da_ghi":
        # Phiếu đã lập (tồn kho đã đổi) nhưng chưa lên sổ cái: gọi lại POST /kho/phieu/{id}/ghi-so
        response.status_code = 202
    return {**_phieu_ra(dong), "so_cai": ghi}


@app.post("/kho/phieu/{ma}/ghi-so")
async def ghi_lai_so(request: Request, ma: uuid.UUID, nd: NguoiDungDep, response: Response) -> dict[str, Any]:
    can_vai_tro(nd, VAI_TRO_DIEU_PHOI)
    st = request.app.state
    dong = await st.so_phieu.doc(str(ma))
    if dong is None:
        raise HTTPException(404, f"Không có phiếu {ma}")
    if dong["ledger_index"] is not None:
        return {**_phieu_ra(dong), "so_cai": {"trang_thai": "da_ghi", "index": dong["ledger_index"],
                                               "leaf_hash": bytes(dong["ledger_leaf_hash"]).hex()}}
    ghi = await ghi_so_phieu(st, dong)
    if ghi["trang_thai"] != "da_ghi":
        response.status_code = 503
    return {**_phieu_ra(dong), "so_cai": ghi}


@app.get("/minh-bach/phieu/{ma}")
async def minh_bach_phieu(request: Request, ma: str, response: Response) -> dict[str, Any]:
    """Trang "Minh bạch cứu trợ": ai cũng tra được bằng mã phiếu, không cần đăng nhập."""
    try:
        ma = str(uuid.UUID(ma))
    except ValueError as e:
        raise HTTPException(404, "Mã phiếu không hợp lệ") from e
    st = request.app.state
    dong = await st.so_phieu.doc(ma)
    if dong is None:
        raise HTTPException(404, "Không có phiếu này")
    ban_ghi = so_cai.ban_ghi_chuan_hoa(dong)
    kq = await so_cai.xac_minh(st.so_cai, ban_ghi, dong["ledger_index"],
                               bytes(dong["ledger_leaf_hash"]) if dong["ledger_leaf_hash"] is not None else None)
    response.headers["Cache-Control"] = "no-store"
    return {
        "ma": ma,
        "trang_thai": kq["trang_thai"],
        "chi_tiet": kq["chi_tiet"],
        "ban_ghi_chuan_hoa": ban_ghi,
        "sha256": kq["sha256_ban_ghi"],
        # Thông tin hiển thị kèm, KHÔNG nằm trong bản ghi đã băm (tên hàng/kho có thể đổi về sau)
        "hien_thi": {"mat_hang": dong["item_name"], "don_vi": dong["unit"], "kho": dong["storage_name"],
                     "diem_nhan": dong["shelter_name"]},
        "so_cai": {
            "index": dong["ledger_index"],
            "leaf_hash": bytes(dong["ledger_leaf_hash"]).hex() if dong["ledger_leaf_hash"] is not None else None,
            "logged_at": dong["ledger_logged_at"].isoformat() if dong["ledger_logged_at"] else None,
            "checkpoint": kq.get("checkpoint"),
            "la": kq.get("la"),
        },
        "tu_kiem_chung": "go run ./core/ledger/cmd/ledger-verify -log <gateway>/ledger/ -verifier <khóa công khai> "
                         "-index <so_cai.index> -record <file lưu phản hồi này>",
    }


@app.get("/{workflow_id}")
async def xem(request: Request, workflow_id: str, nd: NguoiDungDep) -> dict[str, Any]:
    await kiem_quyen_workflow(request, nd, workflow_id)
    trang_thai, tt = await trang_thai_wf(request, workflow_id)
    return {"workflow_id": workflow_id, "trang_thai": trang_thai, "chi_tiet": asdict(tt)}


async def _chuan_bi_signal(
    request: Request, workflow_id: str, nd: NguoiDung, buoc: tuple[str, ...]
) -> tuple[str, str | None]:
    """Kiểm quyền + workflow đang ở đúng bước. Trả (vai trò người gửi, đội người gửi thay mặt)."""
    _, doi_cua_nd = await kiem_quyen_workflow(request, nd, workflow_id)
    trang_thai, tt = await trang_thai_wf(request, workflow_id)
    if trang_thai != WorkflowExecutionStatus.RUNNING.name or tt.buoc not in buoc:
        raise HTTPException(409, f"Workflow không ở bước {'/'.join(buoc)} (trạng thái {trang_thai}, bước {tt.buoc})")
    if doi_cua_nd is not None and doi_cua_nd != tt.doi_id:
        raise HTTPException(409, "Nhiệm vụ đã được giao cho đội khác")
    vai_tro = VAI_TRO_DIEU_PHOI if nd.co(VAI_TRO_DIEU_PHOI) else VAI_TRO_CUU_HO
    return vai_tro, doi_cua_nd or tt.doi_id


async def _gui(request: Request, workflow_id: str, signal: str, arg: Any) -> dict[str, str]:
    await request.app.state.temporal.get_workflow_handle(workflow_id).signal(signal, arg)
    return {"workflow_id": workflow_id, "da_gui": signal}


@app.post("/{workflow_id}/nhan", status_code=202)
async def nhan(
    request: Request, workflow_id: str, nd: NguoiDungDep, vao: XacNhanVao | None = None
) -> dict[str, str]:
    vai_tro, doi_id = await _chuan_bi_signal(request, workflow_id, nd, (BUOC_CHO_NHAN,))
    ph = PhanHoi(loai="", nguoi=nd.ten_dang_nhap or nd.sub, vai_tro=vai_tro, doi_id=doi_id,
                 ghi_chu=(vao or XacNhanVao()).ghi_chu)
    return await _gui(request, workflow_id, SIGNAL_NHAN, ph)


@app.post("/{workflow_id}/tu-choi", status_code=202)
async def tu_choi(
    request: Request, workflow_id: str, nd: NguoiDungDep, vao: XacNhanVao | None = None
) -> dict[str, str]:
    vai_tro, doi_id = await _chuan_bi_signal(request, workflow_id, nd, (BUOC_CHO_NHAN,))
    ph = PhanHoi(loai="", nguoi=nd.ten_dang_nhap or nd.sub, vai_tro=vai_tro, doi_id=doi_id,
                 ghi_chu=(vao or XacNhanVao()).ghi_chu)
    return await _gui(request, workflow_id, SIGNAL_TU_CHOI, ph)


@app.post("/{workflow_id}/huy", status_code=202)
async def huy(request: Request, workflow_id: str, nd: NguoiDungDep, vao: HuyVao | None = None) -> dict[str, str]:
    can_vai_tro(nd, VAI_TRO_DIEU_PHOI)
    await kiem_quyen_workflow(request, nd, workflow_id)
    trang_thai, tt = await trang_thai_wf(request, workflow_id)
    if trang_thai != WorkflowExecutionStatus.RUNNING.name or tt.buoc in (BUOC_CHO_XAC_NHAN, BUOC_XONG):
        raise HTTPException(409, f"Không hủy được: đội đã nhận hoặc workflow đã xong (trạng thái {trang_thai}, bước {tt.buoc})")
    yc = YeuCauHuy(nguoi=nd.ten_dang_nhap or nd.sub, ly_do=(vao or HuyVao()).ly_do)
    return await _gui(request, workflow_id, SIGNAL_HUY, yc)


@app.post("/{workflow_id}/xac-nhan", status_code=202)
async def xac_nhan(
    request: Request, workflow_id: str, nd: NguoiDungDep, vao: XacNhanVao | None = None
) -> dict[str, str]:
    # Đội xác nhận "đã cứu" ngay khi còn chờ nhận cũng được: workflow coi như đã nhận rồi đóng tin
    vai_tro, doi_id = await _chuan_bi_signal(request, workflow_id, nd, (BUOC_CHO_NHAN, BUOC_CHO_XAC_NHAN))
    xn = XacNhan(nguoi=nd.ten_dang_nhap or nd.sub, vai_tro=vai_tro, ghi_chu=(vao or XacNhanVao()).ghi_chu,
                 doi_id=doi_id)
    return await _gui(request, workflow_id, SIGNAL_XAC_NHAN, xn)
