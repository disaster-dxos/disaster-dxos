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
  GET  /ngsi-ld/context.jsonld      @context NGSI-LD của trạm đo (#85, apps/cuu-tro/ngsi-ld). Không cần
                                    đăng nhập: Scorpio tải trong mạng nội bộ theo header Link mà APISIX đặt
                                    cho route /ngsi-ld/v1/*; qua gateway (/workflow/*) vẫn cần JWT
Tiếp nhận tin kêu cứu (#66, Poka-yoke: cuu_tro_workflow/keu_cuu.py, apps/cuu-tro/README.md):
  POST /keu-cuu                     tạo tin (dieu-phoi, tinh-nguyen); 201 · 409 trùng kèm mã tin đang mở ·
                                    422 lỗi theo trường. Route gateway riêng /workflow/keu-cuu (rate limit chặt)
AI bóc tách tin kêu cứu (#102, cuu_tro_workflow/boc_tach.py, LLM_PROVIDER):
  POST /ai/boc-tach                 văn bản tự do → đề xuất theo trường của /keu-cuu + kết quả Poka-yoke và kiểm
                                    trước tin trùng (dieu-phoi, tinh-nguyen). KHÔNG tạo tin: người duyệt quyết
                                    định. Route gateway riêng /workflow/ai/* (rate limit riêng).
                                    "vao_hang_cho": true → lưu vào hàng chờ duyệt của điều phối (#104)
Hàng chờ duyệt HITL (#104, cuu_tro_workflow/hang_cho.py; đọc hàng chờ qua /graphql, chỉ dieu-phoi):
  POST /hang-cho/{id}/duyet         duyệt (body tùy chọn {"tin_keu_cuu": {…}} đã sửa) → tạo tin kêu cứu qua
                                    Poka-yoke của /keu-cuu, lưu vết trường sửa + người duyệt (chỉ dieu-phoi)
  POST /hang-cho/{id}/huy           hủy {"ly_do"}: không tạo tin (chỉ dieu-phoi)
Ảnh hiện trường (#27, luật quyền: cuu_tro_workflow/anh.py, apps/cuu-tro/README.md; quét mã độc ClamAV trước khi
lưu, #111, cuu_tro_workflow/quet_ma_doc.py: nhiễm → 422 anh_nhiem_ma_doc):
  POST /tai-len/su-co/{incident_id}/anh   body = nội dung ảnh (route gateway /workflow/tai-len/*)
  GET  /su-co/{incident_id}/anh           liệt kê ảnh của tin kèm link xem ngắn hạn
  GET  /anh/{media_id}/link?han_giay=N    link xem presigned ngắn hạn cho một ảnh
Sổ cái minh bạch (#28, luồng: cuu_tro_workflow/so_cai.py, apps/cuu-tro/README.md):
  POST /kho/phieu                   lập phiếu nhập/xuất (chỉ dieu-phoi) rồi ghi lá lên sổ cái
  POST /kho/phieu/{id}/ghi-so       ghi lại sổ cái cho phiếu chưa ghi (chỉ dieu-phoi; gửi lại an toàn)
  GET  /minh-bach/phieu/{ma}        CÔNG KHAI, không cần đăng nhập (route /workflow/minh-bach/*):
                                    bản ghi không định danh + trạng thái xác minh trên sổ cái
Tiền cứu trợ + xác minh chung (#89, cuu_tro_workflow/so_cai_csdl.py, apps/cuu-tro/README.md):
  POST /quy/khoan                   lập bút toán thu/chi (chỉ dieu-phoi; chi không vượt số dư) rồi ghi lá
  POST /quy/khoan/{id}/ghi-so       ghi lại sổ cái cho bút toán chưa ghi (chỉ dieu-phoi; worker cũng tự ghi bù)
  GET  /minh-bach/khoan-tien/{ma}   CÔNG KHAI: bút toán + xác minh + bằng chứng (lá, inclusion proof, checkpoint)
  GET  /minh-bach/xac-minh/{ma}     CÔNG KHAI: mã phiếu hoặc mã bút toán → hợp lệ hay không + bằng chứng
  GET  /minh-bach/so-cai            CÔNG KHAI: phiếu/bút toán đã niêm phong, mới nhất trước (?loai=&truoc=&gioi_han=)
  GET  /minh-bach/quy               CÔNG KHAI: tổng thu, tổng chi, số dư, số bút toán chờ niêm phong
Thông báo realtime (#68, cuu_tro_workflow/thong_bao.py):
  GET  /realtime/token              token kết nối Centrifugo ngắn hạn (dieu-phoi; quan-tri khi realm có),
                                    kênh server-side "dieu-phoi"; web mở WebSocket /realtime/websocket
Idempotency-Key (#106, cuu_tro_workflow/idempotency.py): POST /keu-cuu, POST /tai-len/su-co/{id}/anh và
  POST /ai/boc-tach có vao_hang_cho nhận header Idempotency-Key; gửi lại cùng khóa → phản hồi cũ (header
  Idempotent-Replayed: true), không tạo trùng. App hiện trường gửi lại từ hàng đợi offline.
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

from . import anh, boc_tach, config, hang_cho, idempotency, keu_cuu, quet_ma_doc, so_cai, so_cai_csdl, thong_bao
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

    async def them(self, conn: asyncpg.Connection | None = None, **d: Any) -> dict[str, Any]:
        # Kết quả quét mã độc (#111, migration 0016): scanned_at do CSDL đặt khi đã quét
        row = await (conn or self._pool).fetchrow(
            """INSERT INTO cuu_tro.incident_media
                 (id, incident_id, object_key, content_type, size_bytes, sha256, uploaded_by, uploader_role,
                  scan_status, scan_engine, scanned_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, CASE WHEN $9 = 'chua_quet' THEN NULL ELSE now() END)
               RETURNING uploaded_at, scan_status, scanned_at""",
            uuid.UUID(d["id"]), uuid.UUID(d["incident_id"]), d["object_key"], d["content_type"],
            d["size_bytes"], d["sha256"], d["uploaded_by"], d["uploader_role"],
            d.get("scan_status", "chua_quet"), d.get("scan_engine"),
        )
        return {"uploaded_at": row["uploaded_at"].isoformat(), "scan_status": row["scan_status"],
                "scanned_at": row["scanned_at"].isoformat() if row["scanned_at"] else None}


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

    async def them(self, tin: keu_cuu.TinKeuCuu, created_by: str, conn: asyncpg.Connection | None = None) -> dict[str, Any]:
        # conn: chạy trong transaction giữ khóa idempotency (#106)
        row = await (conn or self._pool).fetchrow(keu_cuu.SQL_THEM_TIN, *keu_cuu.tham_so_them_tin(tin, created_by))
        return dict(row)

    async def tim_trung(self, sdt: str, lon: float, lat: float) -> dict[str, Any] | None:
        """Tin còn mở mà trigger chặn trùng sẽ chặn (migration 0013), không tạo tin; None nếu không trùng."""
        row = await self._pool.fetchrow(
            "SELECT * FROM cuu_tro.incident_find_duplicate($1, $2, $3)", sdt, lon, lat)
        if row is None:
            return None
        return {"incident_id": str(row["incident_id"]), "khoang_cach_m": round(row["distance_m"]),
                "ban_kinh_m": round(row["radius_m"]), "trong_vong_phut": row["window_minutes"]}


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
        if not hasattr(st, "so_khoan"):
            st.so_khoan = so_cai_csdl.SoKhoanTien(pool)
        if not hasattr(st, "so_cai_cong_khai"):
            st.so_cai_cong_khai = so_cai_csdl.SoCaiCongKhai(pool)
        if not hasattr(st, "so_hang_cho"):
            st.so_hang_cho = hang_cho.SoHangCho(pool)
        if not hasattr(st, "so_idem"):
            st.so_idem = idempotency.SoIdempotency(pool)
            try:
                log.info("đã xóa %d khóa idempotency hết hạn", await st.so_idem.don())
            except asyncpg.PostgresError as e:  # bảng chưa có (migration chưa chạy) không chặn khởi động
                log.warning("không dọn được khóa idempotency: %s", type(e).__name__)
    try:
        async with httpx.AsyncClient(base_url=cfg.gateway_url, timeout=10) as http, \
                httpx.AsyncClient(timeout=30) as http_s3, \
                httpx.AsyncClient(base_url=cfg.ledger_url, timeout=20) as http_ledger, \
                httpx.AsyncClient(timeout=cfg.llm_timeout_giay) as http_llm:
            st.http = http
            if not hasattr(st, "boc_tach"):
                st.boc_tach = boc_tach.tao(cfg, http_llm)
            if not hasattr(st, "so_cai"):
                st.so_cai = so_cai.SoCai(http_ledger, cfg.ledger_write_token, cfg.ledger_verifier_key)
            if not hasattr(st, "may_quet"):
                st.may_quet = quet_ma_doc.MayQuet(cfg.clamav_host, cfg.clamav_port, cfg.clamav_timeout_giay)
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
    version="0.3.0",
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


@app.get("/ngsi-ld/context.jsonld")
async def ngsi_ld_context(request: Request) -> Response:
    try:
        with open(request.app.state.cfg.ngsi_ld_context_file, "rb") as f:
            noi_dung = f.read()
    except FileNotFoundError:
        raise HTTPException(404, "Chưa mount @context NGSI-LD (NGSI_LD_CONTEXT_FILE)") from None
    return Response(noi_dung, media_type="application/ld+json", headers={"Cache-Control": "public, max-age=300"})


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
    # App hiện trường gửi lại từ hàng đợi offline với cùng Idempotency-Key (#106): không tạo tin thứ hai
    khoa, sha = _khoa_idem(request), idempotency.bam("POST /keu-cuu", raw)
    if (cu := await _da_xong(st, nd, khoa, "POST /keu-cuu", sha)) is not None:
        return _tra(response, cu)

    async def xu_ly(conn: asyncpg.Connection | None) -> tuple[int, dict[str, Any], dict[str, Any]]:
        dong = await (st.so_tin.them(kq, nd.sub, conn=conn) if conn else st.so_tin.them(kq, nd.sub))
        body = {
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
        # Không có SĐT/tên trong phản hồi nên lưu nguyên để phát lại
        return 201, body, body

    try:
        ket_qua = await _chay_idem(st, nd, khoa, "POST /keu-cuu", sha, xu_ly)
    except asyncpg.UniqueViolationError as e:
        raise _loi_tin_trung(e) from None
    except (asyncpg.CheckViolationError, asyncpg.NotNullViolationError) as e:
        # API đã kiểm trước; tới đây là lệch giữa API và ràng buộc CSDL. Không ghi thông điệp (có thể chứa giá trị)
        log.error("CSDL từ chối tin kêu cứu: %s %s", type(e).__name__, e.constraint_name)
        loi = keu_cuu.LoiTruong("body", "Dữ liệu không qua được ràng buộc của CSDL.")
        raise HTTPException(422, keu_cuu.loi_422([loi])) from None
    return _tra(response, ket_qua)


@app.post("/ai/boc-tach")
async def ai_boc_tach(request: Request, nd: NguoiDungDep, response: Response) -> dict[str, Any]:
    """Bóc tách tin kêu cứu viết tự do (#102). Body {"van_ban": "...", "nguon": "sms|zalo|…"}. Trả đề xuất
    (tên trường như /keu-cuu), body sẵn để gửi /keu-cuu sau khi người duyệt sửa, kết quả Poka-yoke (lỗi theo
    trường, tin trùng đang mở) và thông tin mô hình. Không ghi văn bản tin hay SĐT ra log."""
    can_vai_tro(nd, VAI_TRO_DIEU_PHOI, VAI_TRO_TINH_NGUYEN)
    st = request.app.state
    if not st.boc_tach.bat:
        raise HTTPException(503, "Tính năng AI bóc tách đang tắt (LLM_PROVIDER=tat)")
    raw = await doc_body_gioi_han(request, boc_tach.BODY_TOI_DA, "Nội dung gửi lên")
    try:
        d = json.loads(raw)
    except ValueError:
        d = None
    vao = boc_tach.kiem_dau_vao(d) if d is not None else [
        keu_cuu.LoiTruong("body", "Nội dung gửi lên không phải JSON hợp lệ.")]
    if isinstance(vao, list):
        raise HTTPException(422, {**keu_cuu.loi_422(vao), "thong_bao": "Chưa bóc tách được: kiểm tra lại các trường."})
    # Idempotency-Key chỉ có nghĩa khi ghi (đưa vào hàng chờ, #106): app chuyển tin từ hàng đợi offline
    khoa = _khoa_idem(request) if vao.vao_hang_cho else None
    sha = idempotency.bam("POST /ai/boc-tach", raw)
    if (cu := await _da_xong(st, nd, khoa, "POST /ai/boc-tach", sha)) is not None:
        return _tra(response, cu)
    kq = await st.boc_tach.boc_tach(vao.van_ban)
    body = kq.de_xuat.body_keu_cuu(boc_tach.NGUON_TIN[vao.nguon])
    pk = keu_cuu.kiem_tra(body, st.cfg.keu_cuu_vung)
    loi = pk if isinstance(pk, list) else []
    trung = None
    if not loi:
        assert isinstance(pk, keu_cuu.TinKeuCuu)
        trung = await st.so_tin.tim_trung(pk.reporter_phone, pk.lon, pk.lat)
    canh_bao = list(kq.canh_bao)
    if kq.de_xuat.people_count is None:
        canh_bao.append("Tin không nói rõ số người: tạm tính 1, cần hỏi lại.")
    response.headers["Cache-Control"] = "no-store"
    ket_qua = {
        "de_xuat": asdict(kq.de_xuat),
        "tin_keu_cuu": body,
        "poka_yoke": {
            "hop_le": not loi and trung is None,
            "loi": [{"truong": x.truong, "thong_bao": x.thong_bao} for x in loi],
            "tin_trung": {**trung, "thong_bao": keu_cuu.loi_409(trung)["thong_bao"]} if trung else None,
        },
        "ai": {"nha_cung_cap": kq.nha_cung_cap, "mo_hinh": kq.mo_hinh, "thoi_gian_ms": kq.thoi_gian_ms,
               "du_phong": kq.du_phong},
        "canh_bao": canh_bao,
    }
    if not vao.vao_hang_cho:
        return ket_qua

    async def xu_ly(conn: asyncpg.Connection | None) -> tuple[int, dict[str, Any], dict[str, Any]]:
        # HITL (#104): lưu nguyên văn bản + đề xuất do chính API vừa tạo; điều phối duyệt mới thành tin thật
        tham_so: dict[str, Any] = {
            "van_ban": vao.van_ban, "nguon": vao.nguon, "ket_qua": ket_qua, "nguoi_gui": nd.sub,
            "ten_nguoi_gui": nd.ten_dang_nhap,
            "vai_tro": VAI_TRO_DIEU_PHOI if nd.co(VAI_TRO_DIEU_PHOI) else VAI_TRO_TINH_NGUYEN,
        }
        hc = await (st.so_hang_cho.them(**tham_so, conn=conn) if conn else st.so_hang_cho.them(**tham_so))
        # Phát lại chỉ trả phần không có dữ liệu cá nhân (đề xuất có SĐT, tên): mã hàng chờ, kết luận Poka-yoke
        luu = {"hang_cho": hc, "ai": ket_qua["ai"], "poka_yoke": {"hop_le": ket_qua["poka_yoke"]["hop_le"]},
               "phat_lai_rut_gon": True}
        return 200, {**ket_qua, "hang_cho": hc}, luu

    kq_hc = await _chay_idem(st, nd, khoa, "POST /ai/boc-tach", sha, xu_ly)
    if not kq_hc.phat_lai:
        log.info("đã đưa tin vào hàng chờ duyệt %s", kq_hc.body["hang_cho"]["id"])
    return _tra(response, kq_hc)


# ---------------- Idempotency-Key (#106) ----------------

def _khoa_idem(request: Request) -> str | None:
    try:
        return idempotency.doc_khoa(request.headers.get(idempotency.HEADER))
    except idempotency.KhoaSai:
        raise HTTPException(422, idempotency.loi_422("sai")) from None


async def _da_xong(st: Any, nd: NguoiDung, khoa: str | None, endpoint: str, sha: bytes) -> idempotency.KetQua | None:
    """Khóa đã xử lý xong trước đó → phản hồi cũ để phát lại; không có khóa / chưa có → None."""
    if khoa is None:
        return None
    try:
        return await st.so_idem.tim(nd.sub, khoa, endpoint, sha)
    except idempotency.KhoaDungLai:
        raise HTTPException(422, idempotency.loi_422("dung_lai")) from None


async def _chay_idem(st: Any, nd: NguoiDung, khoa: str | None, endpoint: str, sha: bytes,
                     xu_ly: idempotency.XuLy) -> idempotency.KetQua:
    """Chạy nghiệp vụ; có khóa thì trong transaction giữ khóa (yêu cầu đồng thời cùng khóa phát lại kết quả)."""
    if khoa is None:
        status, body, _ = await xu_ly(None)
        return idempotency.KetQua(status, body, False)
    try:
        return await st.so_idem.chay(nd.sub, khoa, endpoint, sha, xu_ly)
    except idempotency.KhoaDungLai:
        raise HTTPException(422, idempotency.loi_422("dung_lai")) from None


def _tra(response: Response, kq: idempotency.KetQua) -> dict[str, Any]:
    response.status_code = kq.status
    response.headers["Cache-Control"] = "no-store"
    if kq.phat_lai:
        response.headers[idempotency.HEADER_PHAT_LAI] = "true"
    return kq.body


def _loi_tin_trung(e: asyncpg.UniqueViolationError) -> HTTPException:
    """Lỗi trùng của trigger incidents_no_duplicate → 409 kèm mã tin đang mở; lỗi khác đi tiếp (500)."""
    trung = keu_cuu.tin_trung_tu_detail(e.detail) if e.constraint_name == "incidents_no_duplicate" else None
    if trung is None:
        raise e
    # Chỉ ghi mã tin đang mở; không ghi SĐT
    log.info("tin kêu cứu trùng tin đang mở %s, không tạo mới", trung["incident_id"])
    return HTTPException(409, keu_cuu.loi_409(trung))


# ---------------- Hàng chờ duyệt tin do AI bóc tách (#104, HITL) ----------------
# Khai báo trước GET /{workflow_id}; mọi path dưới đều có nhiều đoạn. Đọc hàng chờ: /graphql (Hasura).

def _json_body(raw: bytes) -> Any:
    """Body rỗng = {} (duyệt nguyên đề xuất / hủy không lý do); không phải JSON → 422."""
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except ValueError:
        raise HTTPException(422, keu_cuu.loi_422(
            [keu_cuu.LoiTruong("body", "Nội dung gửi lên không phải JSON hợp lệ.")])) from None


@app.post("/hang-cho/{ma}/duyet", status_code=201)
async def duyet_hang_cho(request: Request, ma: uuid.UUID, nd: NguoiDungDep, response: Response) -> dict[str, Any]:
    """Điều phối duyệt (có thể đã sửa) đề xuất của AI → tạo tin kêu cứu thật, lưu vết người duyệt + trường sửa."""
    can_vai_tro(nd, VAI_TRO_DIEU_PHOI)
    st = request.app.state
    d = _json_body(await doc_body_gioi_han(request, hang_cho.BODY_TOI_DA, "Nội dung duyệt"))
    muc = (await hoi_hasura(request, nd, VAI_TRO_DIEU_PHOI, hang_cho.Q_MUC, {"id": str(ma)}))["ai_intake_reviews_by_pk"]
    if muc is None:
        raise HTTPException(404, {"ma": "khong_co", "thong_bao": "Không có tin này trong hàng chờ."})
    if muc["status"] != "cho_duyet":
        raise HTTPException(409, hang_cho.loi_da_xu_ly(muc))
    ai_body = (muc.get("ai_result") or {}).get("tin_keu_cuu") or {}
    body = hang_cho.kiem_duyet(d, ai_body)
    if isinstance(body, list):
        raise HTTPException(422, keu_cuu.loi_422(body))
    tin = keu_cuu.kiem_tra(body, st.cfg.keu_cuu_vung)
    if isinstance(tin, list):
        raise HTTPException(422, keu_cuu.loi_422(tin))
    sua = hang_cho.truong_da_sua(ai_body, hang_cho.body_cuoi(tin))
    try:
        kq = await st.so_hang_cho.duyet(str(ma), tin, sua=sua, nguoi_duyet=nd.sub, ten_nguoi_duyet=nd.ten_dang_nhap)
    except hang_cho.KhongCo:
        raise HTTPException(404, {"ma": "khong_co", "thong_bao": "Không có tin này trong hàng chờ."}) from None
    except hang_cho.DaXuLy as e:
        # Người khác vừa duyệt/hủy giữa lúc đọc và lúc khóa dòng
        raise HTTPException(409, hang_cho.loi_da_xu_ly(e.dong)) from None
    except asyncpg.UniqueViolationError as e:
        raise _loi_tin_trung(e) from None
    except (asyncpg.CheckViolationError, asyncpg.NotNullViolationError) as e:
        log.error("CSDL từ chối tin duyệt từ hàng chờ: %s %s", type(e).__name__, e.constraint_name)
        raise HTTPException(422, keu_cuu.loi_422(
            [keu_cuu.LoiTruong("body", "Dữ liệu không qua được ràng buộc của CSDL.")])) from None
    t = kq["tin"]
    log.info("đã duyệt tin trong hàng chờ %s → tin kêu cứu %s", ma, t["id"])
    response.headers["Cache-Control"] = "no-store"
    return {
        "id": str(ma),
        "trang_thai": "da_duyet",
        "reviewed_at": kq["reviewed_at"].isoformat(),
        "truong_da_sua": sorted(sua),
        "incident_id": str(t["id"]),
        "tin": {"id": str(t["id"]), "status": t["status"], "urgency": t["urgency"], "people_count": t["people_count"],
                "lat": tin.lat, "lon": tin.lon, "created_at": t["created_at"].isoformat()},
        "phan_cong": "tu_dong",
    }


@app.post("/hang-cho/{ma}/huy")
async def huy_hang_cho(request: Request, ma: uuid.UUID, nd: NguoiDungDep, response: Response) -> dict[str, Any]:
    """Điều phối hủy một tin trong hàng chờ (tin rác, trùng, không đủ thông tin): không tạo tin kêu cứu."""
    can_vai_tro(nd, VAI_TRO_DIEU_PHOI)
    st = request.app.state
    ly_do = hang_cho.kiem_huy(_json_body(await doc_body_gioi_han(request, keu_cuu.BODY_TOI_DA, "Nội dung hủy")))
    if isinstance(ly_do, list):
        raise HTTPException(422, {**keu_cuu.loi_422(ly_do), "thong_bao": "Chưa hủy được: kiểm tra lại các trường."})
    try:
        luc = await st.so_hang_cho.huy(str(ma), ly_do, nguoi_duyet=nd.sub, ten_nguoi_duyet=nd.ten_dang_nhap)
    except hang_cho.KhongCo:
        raise HTTPException(404, {"ma": "khong_co", "thong_bao": "Không có tin này trong hàng chờ."}) from None
    except hang_cho.DaXuLy as e:
        raise HTTPException(409, hang_cho.loi_da_xu_ly(e.dong)) from None
    log.info("đã hủy tin trong hàng chờ %s", ma)
    response.headers["Cache-Control"] = "no-store"
    return {"id": str(ma), "trang_thai": "da_huy", "reviewed_at": luc.isoformat(), "ly_do": ly_do}


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
    # App gửi lại ảnh từ hàng đợi offline (#106): cùng khóa đã xong thì phát lại NGAY, trước khi kiểm quyền theo
    # trạng thái tin (tin có thể đã sang phan_cong sau lần gửi đầu); khóa chỉ của chính người gửi
    khoa = _khoa_idem(request)
    endpoint = f"POST /tai-len/su-co/{incident_id}/anh"
    du_lieu = b""
    if khoa is not None:
        du_lieu = await doc_body_gioi_han(request, cfg.anh_max_bytes)
        if (cu := await _da_xong(st, nd, khoa, endpoint, idempotency.bam(endpoint, du_lieu))) is not None:
            return _tra(response, _them_link(request, cu))
    tin = (await hoi_hasura(request, nd, vai_tro, Q_TIN_ANH, {"id": str(incident_id)}))["incidents_by_pk"]
    _tu_choi(anh.quyen_tai_len(vai_tro, tin))

    if khoa is None:
        du_lieu = await doc_body_gioi_han(request, cfg.anh_max_bytes)
    if not du_lieu:
        raise HTTPException(400, "Body rỗng: gửi nội dung ảnh trong body request")
    # Quét mã độc TRƯỚC mọi bước lưu (#111): tệp nhiễm bị từ chối dù đội lốt ảnh hay không, không chạm S3/CSDL
    quet = await _quet_anh(st, str(incident_id), du_lieu)
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
               "size_bytes": len(du_lieu), "sha256": sha, "uploaded_by": nd.sub, "uploader_role": vai_tro, **quet}

    async def xu_ly(conn: asyncpg.Connection | None) -> tuple[int, dict[str, Any], dict[str, Any]]:
        them = await (st.so_anh.them(conn=conn, **ban_ghi) if conn else st.so_anh.them(**ban_ghi))
        # Lưu không kèm link (link presigned hết hạn sau vài phút; phát lại thì ký link mới)
        return 201, {**ban_ghi, **them}, {**ban_ghi, **them}

    async def xoa_mo_coi() -> None:
        try:
            await st.kho_anh.xoa(key)
        except (LoiS3, httpx.HTTPError) as e2:
            log.error("xóa object mồ côi %s lỗi: %s", key, e2)

    try:
        kq = await _chay_idem(st, nd, khoa, endpoint, idempotency.bam(endpoint, du_lieu), xu_ly)
    except HTTPException:
        await xoa_mo_coi()
        raise
    except Exception as e:
        # Không để object mồ côi trên S3 khi không ghi được siêu dữ liệu
        log.error("ghi incident_media lỗi: %s", e)
        await xoa_mo_coi()
        raise HTTPException(500, "Không ghi được thông tin ảnh") from e
    if kq.phat_lai:
        # Yêu cầu cùng khóa chạy song song đã ghi trước: object vừa ghi của yêu cầu này thừa
        await xoa_mo_coi()
    return _tra(response, _them_link(request, kq))


async def _quet_anh(st: Any, incident_id: str, du_lieu: bytes) -> dict[str, Any]:
    """Quét bằng clamd (#111) → {scan_status, scan_engine}. Nhiễm → 422. Không quét được → chua_quet (mặc định,
    ảnh cứu nạn không mất vì máy quét tắt) hoặc 503 khi ANH_QUET_BAT_BUOC=1."""
    may = getattr(st, "may_quet", None)
    try:
        if may is None:
            raise quet_ma_doc.LoiQuet("chưa cấu hình máy quét")
        kq = await may.quet(du_lieu)
    except quet_ma_doc.LoiQuet as e:
        if st.cfg.anh_quet_bat_buoc:
            log.error("không quét được ảnh, từ chối (ANH_QUET_BAT_BUOC): %s", e)
            raise HTTPException(503, {"ma": "chua_quet_duoc",
                                      "thong_bao": "Máy quét mã độc đang không hoạt động, chưa nhận ảnh. Thử lại sau."}) from None
        if may is not None and may.bat:
            log.warning("không quét được ảnh, nhận với scan_status chua_quet: %s", e)
        return {"scan_status": "chua_quet", "scan_engine": None}
    if not kq.sach:
        # Chỉ ghi mã tin và tên chữ ký, không ghi nội dung
        log.warning("ảnh tải lên cho tin %s có mã độc (%s), đã từ chối", incident_id, kq.chu_ky)
        raise HTTPException(422, {"ma": "anh_nhiem_ma_doc", "chu_ky": kq.chu_ky,
                                  "thong_bao": f"Tệp có mã độc ({kq.chu_ky}), không lưu."})
    return {"scan_status": "sach", "scan_engine": kq.dong_co}


def _them_link(request: Request, kq: idempotency.KetQua) -> idempotency.KetQua:
    """Phản hồi ảnh + link xem presigned mới (link trong lần trả trước có thể đã hết hạn)."""
    link = _link(request, kq.body["object_key"], request.app.state.cfg.anh_link_han_giay)
    return idempotency.KetQua(kq.status, {**kq.body, "link": link}, kq.phat_lai)


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


def _uuid_hoac_404(ma: str, ten: str) -> str:
    try:
        return str(uuid.UUID(ma))
    except ValueError as e:
        raise HTTPException(404, f"Mã {ten} không hợp lệ") from e


def _so_cai_ra(dong: dict[str, Any], kq: dict[str, Any]) -> dict[str, Any]:
    return {
        "index": dong["ledger_index"],
        "leaf_hash": bytes(dong["ledger_leaf_hash"]).hex() if dong["ledger_leaf_hash"] is not None else None,
        "logged_at": dong["ledger_logged_at"].isoformat() if dong["ledger_logged_at"] else None,
        "checkpoint": kq.get("checkpoint"),
        "la": kq.get("la"),
    }


TU_KIEM_CHUNG = ("go run ./core/ledger/cmd/ledger-verify -log <gateway>/ledger/ -verifier <khóa công khai> "
                 "-index <so_cai.index> -record <file lưu phản hồi này>")


async def _minh_bach(st: Any, loai: so_cai_csdl.LoaiSoCai, ma: str, dong: dict[str, Any],
                     hien_thi: dict[str, Any]) -> dict[str, Any]:
    ban_ghi = loai.ban_ghi(dong)
    kq = await so_cai.xac_minh(st.so_cai, ban_ghi, dong["ledger_index"],
                               bytes(dong["ledger_leaf_hash"]) if dong["ledger_leaf_hash"] is not None else None,
                               loai.loai_la)
    return {
        "loai": loai.ten,
        "ma": ma,
        "trang_thai": kq["trang_thai"],
        "chi_tiet": kq["chi_tiet"],
        "ban_ghi_chuan_hoa": ban_ghi,
        "sha256": kq["sha256_ban_ghi"],
        # Thông tin hiển thị kèm, KHÔNG nằm trong bản ghi đã băm (tên hàng/kho có thể đổi về sau)
        "hien_thi": hien_thi,
        "so_cai": _so_cai_ra(dong, kq),
        # Đủ để tự kiểm lại phía client: lá, leaf hash, inclusion proof, checkpoint đã ký nguyên văn (#89)
        "bang_chung": kq.get("bang_chung"),
        "tu_kiem_chung": TU_KIEM_CHUNG,
    }


def _hien_thi_phieu(dong: dict[str, Any]) -> dict[str, Any]:
    return {"mat_hang": dong["item_name"], "don_vi": dong["unit"], "kho": dong["storage_name"],
            "diem_nhan": dong["shelter_name"]}


def _hien_thi_khoan(dong: dict[str, Any]) -> dict[str, Any]:
    return {"hang_muc": dong["category"], "don_vi": dong["currency"], "diem_nhan": dong["shelter_name"]}


@app.get("/minh-bach/phieu/{ma}")
async def minh_bach_phieu(request: Request, ma: str, response: Response) -> dict[str, Any]:
    """Trang "Minh bạch cứu trợ": ai cũng tra được bằng mã phiếu, không cần đăng nhập."""
    ma = _uuid_hoac_404(ma, "phiếu")
    st = request.app.state
    dong = await st.so_phieu.doc(ma)
    if dong is None:
        raise HTTPException(404, "Không có phiếu này")
    response.headers["Cache-Control"] = "no-store"
    return await _minh_bach(st, so_cai_csdl.LOAI[so_cai_csdl.PHIEU_KHO], ma, dong, _hien_thi_phieu(dong))


@app.get("/minh-bach/khoan-tien/{ma}")
async def minh_bach_khoan_tien(request: Request, ma: str, response: Response) -> dict[str, Any]:
    """Bút toán tiền cứu trợ: công khai, không cần đăng nhập (#89)."""
    ma = _uuid_hoac_404(ma, "bút toán")
    st = request.app.state
    dong = await st.so_khoan.doc(ma)
    if dong is None:
        raise HTTPException(404, "Không có bút toán này")
    response.headers["Cache-Control"] = "no-store"
    return await _minh_bach(st, so_cai_csdl.LOAI[so_cai_csdl.KHOAN_TIEN], ma, dong, _hien_thi_khoan(dong))


@app.get("/minh-bach/xac-minh/{ma}")
async def minh_bach_xac_minh(request: Request, ma: str, response: Response) -> dict[str, Any]:
    """Một ô tra cứu cho cả hai loại: mã phiếu kho hoặc mã bút toán tiền → hợp lệ hay không (#89)."""
    ma = _uuid_hoac_404(ma, "tra cứu")
    st = request.app.state
    response.headers["Cache-Control"] = "no-store"
    dong = await st.so_phieu.doc(ma)
    if dong is not None:
        kq = await _minh_bach(st, so_cai_csdl.LOAI[so_cai_csdl.PHIEU_KHO], ma, dong, _hien_thi_phieu(dong))
    else:
        dong = await st.so_khoan.doc(ma)
        if dong is None:
            raise HTTPException(404, "Không có phiếu hay bút toán nào mang mã này")
        kq = await _minh_bach(st, so_cai_csdl.LOAI[so_cai_csdl.KHOAN_TIEN], ma, dong, _hien_thi_khoan(dong))
    return {"hop_le": kq["trang_thai"] == so_cai.DA_XAC_MINH, **kq}


@app.get("/minh-bach/so-cai")
async def minh_bach_so_cai(request: Request, response: Response,
                           loai: Literal["phieu_kho", "khoan_tien"] | None = None,
                           truoc: Annotated[int | None, Query(ge=0)] = None,
                           gioi_han: Annotated[int, Query(ge=1, le=100)] = 20) -> dict[str, Any]:
    """Phiếu/bút toán đã niêm phong, mới nhất trước (theo chỉ số lá). Trang sau: ?truoc=<ledger_index nhỏ nhất>."""
    ds = await request.app.state.so_cai_cong_khai.danh_sach(truoc, loai, gioi_han)
    response.headers["Cache-Control"] = "no-store"
    return {"muc": ds, "truoc_tiep": ds[-1]["ledger_index"] if len(ds) == gioi_han else None}


@app.get("/minh-bach/quy")
async def minh_bach_quy(request: Request, response: Response) -> dict[str, Any]:
    """Tổng hợp quỹ tiền cứu trợ (#89): tổng thu, tổng chi, số dư; số mục chờ niêm phong."""
    response.headers["Cache-Control"] = "no-store"
    return await request.app.state.so_cai_cong_khai.tong_hop()


class KhoanTienVao(BaseModel):
    direction: Literal["thu", "chi"]
    amount: int = Field(gt=0, le=10**15, description="Số tiền, đồng")
    category: Literal["ung_ho", "ngan_sach", "mua_hang", "ho_tro_ho_dan", "van_chuyen", "khac"]
    # Hiện trên trang công khai: KHÔNG ghi tên, SĐT, CCCD, số tài khoản
    purpose: str | None = Field(None, max_length=200)
    shelter_id: uuid.UUID | None = None
    supply_movement_id: uuid.UUID | None = None


HANG_MUC_THEO_CHIEU = {"thu": {"ung_ho", "ngan_sach", "khac"}, "chi": {"mua_hang", "ho_tro_ho_dan", "van_chuyen", "khac"}}


async def ghi_so_khoan(st: Any, dong: dict[str, Any]) -> dict[str, Any]:
    ban_ghi = so_cai.ban_ghi_khoan_tien(dong)
    try:
        kq = await st.so_cai.ghi(so_cai.la_cho_khoan_tien(ban_ghi))
    except so_cai.LoiSoCai as e:
        log.error("ghi sổ cái bút toán %s lỗi: %s", ban_ghi["id"], e)
        return {"trang_thai": so_cai.CHUA_GHI_SO, "loi": str(e)}
    luc = await st.so_khoan.ghi_so(ban_ghi["id"], kq["index"], bytes.fromhex(kq["leaf_hash"]))
    return {"trang_thai": "da_ghi", "index": kq["index"], "leaf_hash": kq["leaf_hash"],
            "tree_size": kq.get("tree_size"), "trung": bool(kq.get("duplicate")),
            "logged_at": luc.isoformat() if luc else None}


def _khoan_ra(dong: dict[str, Any]) -> dict[str, Any]:
    ban_ghi = so_cai.ban_ghi_khoan_tien(dong)
    return {"ban_ghi_chuan_hoa": ban_ghi, "sha256": so_cai.sha256_ban_ghi(ban_ghi)}


@app.post("/quy/khoan", status_code=201)
async def lap_khoan(request: Request, vao: KhoanTienVao, nd: NguoiDungDep, response: Response) -> dict[str, Any]:
    can_vai_tro(nd, VAI_TRO_DIEU_PHOI)
    if vao.category not in HANG_MUC_THEO_CHIEU[vao.direction]:
        raise HTTPException(422, f"Hạng mục {vao.category} không dùng cho khoản {vao.direction}")
    if so_cai.co_so_dinh_danh(vao.purpose):
        raise HTTPException(422, "Nội dung hiện công khai: không ghi SĐT, CCCD, số tài khoản (dãy số bắt đầu bằng 0)")
    st = request.app.state
    try:
        dong = await st.so_khoan.them(
            direction=vao.direction, amount=Decimal(vao.amount), category=vao.category, purpose=vao.purpose or None,
            shelter_id=str(vao.shelter_id) if vao.shelter_id else None,
            supply_movement_id=str(vao.supply_movement_id) if vao.supply_movement_id else None,
            created_by=nd.ten_dang_nhap or nd.sub,
        )
    except asyncpg.CheckViolationError as e:
        raise HTTPException(409, "Khoản chi vượt số dư quỹ") from e
    except asyncpg.ForeignKeyViolationError as e:
        raise HTTPException(404, "Không có điểm nhận hoặc phiếu kho này") from e
    ghi = await ghi_so_khoan(st, dong)
    if ghi["trang_thai"] != "da_ghi":
        # Bút toán đã lập nhưng chưa lên sổ cái: worker tự ghi bù, hoặc gọi POST /quy/khoan/{id}/ghi-so
        response.status_code = 202
    return {**_khoan_ra(dong), "so_cai": ghi}


@app.post("/quy/khoan/{ma}/ghi-so")
async def ghi_lai_so_khoan(request: Request, ma: uuid.UUID, nd: NguoiDungDep, response: Response) -> dict[str, Any]:
    can_vai_tro(nd, VAI_TRO_DIEU_PHOI)
    st = request.app.state
    dong = await st.so_khoan.doc(str(ma))
    if dong is None:
        raise HTTPException(404, f"Không có bút toán {ma}")
    if dong["ledger_index"] is not None:
        return {**_khoan_ra(dong), "so_cai": {"trang_thai": "da_ghi", "index": dong["ledger_index"],
                                               "leaf_hash": bytes(dong["ledger_leaf_hash"]).hex()}}
    ghi = await ghi_so_khoan(st, dong)
    if ghi["trang_thai"] != "da_ghi":
        response.status_code = 503
    return {**_khoan_ra(dong), "so_cai": ghi}


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
