# SPDX-License-Identifier: Apache-2.0
"""Bản sao số trạm đo NGSI-LD (#85): ánh xạ bản tin → thực thể, chọn ghi theo observedAt, phân loại
lỗi Scorpio, consumer ban-sao-so với Scorpio giả (httpx.MockTransport), endpoint @context."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from cuu_tro_workflow import cam_bien as cb
from cuu_tro_workflow import config, ngsi_ld
from cuu_tro_workflow.api import app
from cuu_tro_workflow.ban_sao_so import BanSaoSo
from cuu_tro_workflow.cam_bien_consumer import doc_khai_bao

BAY_GIO = datetime.now(timezone.utc).replace(microsecond=0)
CONTEXT = Path(__file__).resolve().parents[2] / "ngsi-ld" / "context.jsonld"
STREAMS_JSON = Path(__file__).resolve().parents[2] / "nats" / "streams.json"
CTX = ngsi_ld.doc_context(str(CONTEXT))
TRAM = ngsi_ld.Tram("QN-AN-01", "Mực nước sông Vu Gia tại Ái Nghĩa (giả lập)", "muc_nuoc", "cm", 108.115, 15.886,
                    Decimal("900"), Decimal("1000"), True, "urn:ngsi-ld:WaterLevelStation:QN-AN-01")
ID = TRAM.ngsi_ld_id


def ban_tin(gia_tri=950.0, thoi_diem=BAY_GIO, ma="QN-AN-01", don_vi="cm", dai_luong="muc-nuoc") -> tuple[str, bytes]:
    return (f"cuu-tro.cam-bien.{ma}.{dai_luong}",
            json.dumps({"ma_tram": ma, "gia_tri": gia_tri, "don_vi": don_vi, "thoi_diem": thoi_diem.isoformat()}).encode())


def bt(**kw) -> cb.BanTin:
    return cb.phan_tich(*ban_tin(**kw), BAY_GIO)


# ---------- Ánh xạ ----------
def test_context_trong_repo_khai_bao_moi_term_dung_trong_thuc_the():
    tt = ngsi_ld.thuc_the(TRAM, bt(), CTX)
    term = set(tt) - {"id", "type", "location", "@context"}
    assert term <= set(CTX) and tt["type"] in CTX
    assert all(ngsi_ld.iri(CTX, k).startswith("https://") for k in term | {tt["type"]})
    assert all(ngsi_ld.LOAI[k][0] in CTX and ngsi_ld.LOAI[k][1] in CTX for k in ngsi_ld.LOAI)


def test_thuc_the_muc_nuoc():
    tt = ngsi_ld.thuc_the(TRAM, bt(gia_tri=950.0), CTX)
    assert tt["id"] == ID and tt["type"] == "WaterLevelStation"
    luc = BAY_GIO.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    assert tt["waterLevel"] == {"type": "Property", "value": 950.0, "unitCode": "CMT", "observedAt": luc}
    assert tt["alertLevel"] == {"type": "Property", "value": "canh_bao", "observedAt": luc}
    assert tt["warningThreshold"]["value"] == 900.0 and tt["dangerThreshold"]["value"] == 1000.0
    assert tt["location"] == {"type": "GeoProperty", "value": {"type": "Point", "coordinates": [108.115, 15.886]}}
    assert tt["name"]["value"] == TRAM.ten and tt["stationCode"]["value"] == "QN-AN-01"
    assert tt["@context"] == [CTX]
    json.dumps(tt)


@pytest.mark.parametrize("gia_tri,muc", [(899.99, "binh_thuong"), (900, "canh_bao"), (1000, "nguy_hiem")])
def test_alert_level_theo_nguong(gia_tri, muc):
    assert ngsi_ld.thuc_the(TRAM, bt(gia_tri=gia_tri), CTX)["alertLevel"]["value"] == muc


def test_thuc_the_luong_mua_khong_nguong_va_id_mac_dinh():
    tram = ngsi_ld.Tram("QN-LM-01", "Mưa", "luong_mua", "mm", 108.086, 15.878, None, None, True, None)
    tt = ngsi_ld.thuc_the(tram, bt(ma="QN-LM-01", don_vi="mm", dai_luong="luong-mua", gia_tri=40), CTX)
    assert tt["id"] == "urn:ngsi-ld:RainGauge:QN-LM-01" and tt["type"] == "RainGauge"
    assert tt["precipitation"]["unitCode"] == "MMT" and "waterLevel" not in tt
    assert "warningThreshold" not in tt and "dangerThreshold" not in tt
    assert tt["alertLevel"]["value"] == "binh_thuong"


def test_thoi_diem_quy_ve_utc():
    t7 = BAY_GIO.astimezone(timezone(timedelta(hours=7)))
    tt = ngsi_ld.thuc_the(TRAM, bt(thoi_diem=t7), CTX)
    assert tt["waterLevel"]["observedAt"].endswith("Z")
    assert datetime.fromisoformat(tt["waterLevel"]["observedAt"].replace("Z", "+00:00")) == BAY_GIO


def test_thuc_the_sai_tram():
    with pytest.raises(ValueError):
        ngsi_ld.thuc_the(TRAM, bt(ma="AL-MN-01"), CTX)


def test_iri_mo_rong_tien_to():
    assert ngsi_ld.iri(CTX, "waterLevel") == CTX["dxos"] + "waterLevel"
    assert ngsi_ld.iri(CTX, "name") == "https://schema.org/name"


def thuc_the_scorpio(observed_at: str, mo_rong: bool = True) -> dict:
    khoa = ngsi_ld.iri(CTX, "waterLevel") if mo_rong else "waterLevel"
    return {"id": ID, khoa: {"type": "Property", "value": 1.0, "observedAt": observed_at}}


def test_thoi_diem_hien_tai_va_can_ghi():
    assert ngsi_ld.thoi_diem_hien_tai(None, "muc_nuoc", CTX) is None
    assert ngsi_ld.thoi_diem_hien_tai({"id": ID}, "muc_nuoc", CTX) is None
    for mo_rong in (True, False):
        ht = ngsi_ld.thoi_diem_hien_tai(thuc_the_scorpio("2026-10-24T01:00:00.000Z", mo_rong), "muc_nuoc", CTX)
        assert ht == datetime(2026, 10, 24, 1, tzinfo=timezone.utc)
    moi = cb.BanTin("QN-AN-01", "muc_nuoc", Decimal(1), "cm", datetime(2026, 10, 24, 1, tzinfo=timezone.utc))
    assert ngsi_ld.can_ghi(moi, None)
    assert ngsi_ld.can_ghi(moi, moi.thoi_diem)  # bằng: ghi lại, kết quả như cũ
    assert ngsi_ld.can_ghi(moi, moi.thoi_diem - timedelta(seconds=1))
    assert not ngsi_ld.can_ghi(moi, moi.thoi_diem + timedelta(milliseconds=1))  # bản tin cũ hơn


LOI_CSDL = json.dumps({"type": "https://uri.etsi.org/ngsi-ld/errors/InvalidRequest", "title": "Invalid request.",
                       "detail": "too many connections for role \"scorpio\"", "status": 400})
LOI_DU_LIEU = json.dumps({"type": "https://uri.etsi.org/ngsi-ld/errors/BadRequestData", "status": 400})


@pytest.mark.parametrize("ma,than,tam_thoi", [
    (500, "", True), (503, "", True), (429, "", True), (408, "", True), (404, "", True),
    (400, LOI_CSDL, True),       # Scorpio hết kết nối PostgreSQL: lỗi phía Scorpio, thử lại (đo được ở smoke)
    (400, "khong-phai-json", True),
    (400, LOI_DU_LIEU, False), (422, "", False), (413, "", False), (415, "", False),
])
def test_phan_loai_loi(ma, than, tam_thoi):
    assert ngsi_ld.phan_loai_loi(ma, than).tam_thoi is tam_thoi


def test_kiem_ket_qua_upsert():
    for ma in (201, 204):
        ngsi_ld.kiem_ket_qua_upsert(ma, "")
    ngsi_ld.kiem_ket_qua_upsert(207, json.dumps({"success": [ID], "errors": []}))
    # Dạng 207 Scorpio 6.0.2 trả thật cho tọa độ sai: {"errors": [{"entityId", "error": ProblemDetails}]}
    with pytest.raises(ngsi_ld.LoiScorpio) as e:
        ngsi_ld.kiem_ket_qua_upsert(207, json.dumps({"errors": [{"entityId": ID, "error": json.loads(LOI_DU_LIEU)}]}))
    assert not e.value.tam_thoi
    with pytest.raises(ngsi_ld.LoiScorpio) as e:
        ngsi_ld.kiem_ket_qua_upsert(207, json.dumps({"errors": [{"entityId": ID, "error": {"status": 500}}]}))
    assert e.value.tam_thoi
    with pytest.raises(ngsi_ld.LoiScorpio) as e:
        ngsi_ld.kiem_ket_qua_upsert(207, json.dumps({"errors": [{"entityId": ID, "error": json.loads(LOI_CSDL)}]}))
    assert e.value.tam_thoi
    with pytest.raises(ngsi_ld.LoiScorpio) as e:
        ngsi_ld.kiem_ket_qua_upsert(400, LOI_DU_LIEU)
    assert not e.value.tam_thoi
    with pytest.raises(ngsi_ld.LoiScorpio) as e:
        ngsi_ld.kiem_ket_qua_upsert(400, LOI_CSDL)
    assert e.value.tam_thoi


def test_tre_thu_lai_tang_dan_co_tran():
    assert [ngsi_ld.tre_thu_lai(n) for n in (1, 2, 3, 5, 6, 20)] == [2, 4, 8, 32, 60, 60]


def test_khai_bao_consumer_ban_sao_so():
    _, consumers = doc_khai_bao(str(STREAMS_JSON))
    (stream, cc), = [(s, c) for s, c in consumers if c.durable_name == "ban-sao-so"]
    assert stream == "CUU_TRO_CAM_BIEN" and cc.filter_subject == "cuu-tro.cam-bien.>"
    assert cc.max_deliver >= 10  # đủ lần giao lại khi Scorpio khởi động chậm
    assert {c.durable_name for s, c in consumers if s == "CUU_TRO_CAM_BIEN"} == {"ghi-csdl", "ban-sao-so"}


# ---------- Consumer với Scorpio giả ----------
class MsgGia:
    def __init__(self, subject: str, data: bytes, lan_giao: int = 1):
        self.subject, self.data = subject, data
        self.metadata = SimpleNamespace(num_delivered=lan_giao)
        self.ket_qua: list = []

    async def ack(self):
        self.ket_qua.append("ack")

    async def nak(self, delay=None):
        self.ket_qua.append(("nak", delay))

    async def term(self):
        self.ket_qua.append("term")


class ScorpioGia:
    """Giữ thực thể như Scorpio (upsert thay cả thực thể); GET trả dạng mở rộng (không gửi context)."""

    def __init__(self, loi_get: int | None = None, loi_upsert: int | None = None, loi_mang: bool = False,
                 than_loi: str = "loi"):
        self.kho: dict[str, dict] = {}
        self.goi: list[httpx.Request] = []
        self.loi_get, self.loi_upsert, self.loi_mang, self.than_loi = loi_get, loi_upsert, loi_mang, than_loi

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.goi.append(req)
        if self.loi_mang:
            raise httpx.ConnectError("không kết nối được", request=req)
        if req.method == "GET":
            if self.loi_get:
                return httpx.Response(self.loi_get)
            id_tt = req.url.path.rsplit("/", 1)[-1]
            if id_tt not in self.kho:
                return httpx.Response(404, json={"type": "https://uri.etsi.org/ngsi-ld/errors/ResourceNotFound"})
            tt = self.kho[id_tt]
            return httpx.Response(200, json={(ngsi_ld.iri(CTX, k) if k in CTX else k): v
                                             for k, v in tt.items() if k != "@context"})
        assert req.url.path == "/ngsi-ld/v1/entityOperations/upsert"
        assert req.headers["Content-Type"] == "application/ld+json"
        if self.loi_upsert:
            return httpx.Response(self.loi_upsert, text=self.than_loi)
        (tt,) = json.loads(req.content)
        moi = tt["id"] not in self.kho
        self.kho[tt["id"]] = tt
        return httpx.Response(201 if moi else 204, json=[tt["id"]] if moi else None)


def chay(scorpio: ScorpioGia, *msgs: MsgGia, tram=TRAM) -> list[str]:
    async def doc_tram(ma):
        if isinstance(tram, Exception):
            raise tram
        return tram if tram and ma == tram.ma else None

    async def _main():
        async with httpx.AsyncClient(base_url="http://scorpio:9090", transport=httpx.MockTransport(scorpio)) as h:
            x = BanSaoSo(doc_tram, h, CTX)
            return [await x.mot_ban_tin(m) for m in msgs]

    return asyncio.run(_main())


def test_ghi_moi_roi_cap_nhat_roi_bo_ban_tin_cu():
    sc = ScorpioGia()
    m1 = MsgGia(*ban_tin(950, BAY_GIO - timedelta(minutes=10)))
    m2 = MsgGia(*ban_tin(1010, BAY_GIO))
    m_cu = MsgGia(*ban_tin(800, BAY_GIO - timedelta(minutes=5)))  # gửi bù, cũ hơn lần đo đang có
    assert chay(sc, m1, m2, m_cu) == ["ghi", "ghi", "cu"]
    assert [m.ket_qua for m in (m1, m2, m_cu)] == [["ack"], ["ack"], ["ack"]]
    tt = sc.kho[ID]
    assert tt["waterLevel"]["value"] == 1010.0 and tt["alertLevel"]["value"] == "nguy_hiem"
    assert sum(r.method == "POST" for r in sc.goi) == 2  # bản tin cũ không gửi upsert


def test_giao_lai_cung_ban_tin_ket_qua_nhu_cu():
    sc = ScorpioGia()
    m = ban_tin(950, BAY_GIO)
    chay(sc, MsgGia(*m))
    truoc = json.dumps(sc.kho, sort_keys=True)
    assert chay(sc, MsgGia(*m, lan_giao=2)) == ["ghi"]
    assert json.dumps(sc.kho, sort_keys=True) == truoc and len(sc.kho) == 1


@pytest.mark.parametrize("subject,du_lieu", [
    ("cuu-tro.cam-bien.QN-AN-01.muc-nuoc", b"{hong"),
    ban_tin(don_vi="m"),
    ban_tin(ma="KHONG-CO"),
])
def test_ban_tin_sai_hoac_tram_khong_co_bi_bo(subject, du_lieu):
    sc = ScorpioGia()
    m = MsgGia(subject, du_lieu)
    assert chay(sc, m) == ["bo"] and m.ket_qua == ["term"] and not sc.goi


def test_tram_dang_tat_bi_bo():
    sc = ScorpioGia()
    m = MsgGia(*ban_tin())
    assert chay(sc, m, tram=TRAM.__class__(**{**TRAM.__dict__, "active": False})) == ["bo"] and not sc.goi


@pytest.mark.parametrize("sc", [ScorpioGia(loi_mang=True), ScorpioGia(loi_get=503), ScorpioGia(loi_upsert=500),
                                ScorpioGia(loi_upsert=429)], ids=["mang", "get-503", "upsert-500", "upsert-429"])
def test_scorpio_loi_tam_thoi_thi_giao_lai_co_hen_gio(sc):
    m = MsgGia(*ban_tin(), lan_giao=3)
    assert chay(sc, m) == ["loi"] and m.ket_qua == [("nak", 8.0)]


def test_scorpio_tu_choi_du_lieu_thi_bo():
    m = MsgGia(*ban_tin())
    assert chay(ScorpioGia(loi_upsert=422), m) == ["bo"] and m.ket_qua == ["term"]


def test_scorpio_het_ket_noi_csdl_400_van_giao_lai():
    m = MsgGia(*ban_tin(), lan_giao=1)
    assert chay(ScorpioGia(loi_upsert=400, than_loi=LOI_CSDL), m) == ["loi"] and m.ket_qua == [("nak", 2.0)]


def test_csdl_loi_thi_giao_lai():
    m = MsgGia(*ban_tin())
    assert chay(ScorpioGia(), m, tram=OSError("mất kết nối CSDL")) == ["loi"] and m.ket_qua == [("nak", 5)]


# ---------- Endpoint @context ----------
@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("NGSI_LD_CONTEXT_FILE", str(CONTEXT))
    app.state.cfg = config.load()
    yield TestClient(app)
    delattr(app.state, "cfg")


def test_endpoint_context_khong_can_dang_nhap(api):
    r = api.get("/ngsi-ld/context.jsonld")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/ld+json")
    assert r.json() == json.loads(CONTEXT.read_text(encoding="utf-8"))


def test_endpoint_context_chua_mount(api, tmp_path):
    import dataclasses
    app.state.cfg = dataclasses.replace(app.state.cfg, ngsi_ld_context_file=str(tmp_path / "khong-co.jsonld"))
    assert api.get("/ngsi-ld/context.jsonld").status_code == 404
