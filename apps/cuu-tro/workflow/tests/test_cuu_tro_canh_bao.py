# SPDX-License-Identifier: Apache-2.0
"""Thông báo cảnh báo vượt ngưỡng (#87): sự kiện đợt từ cam_bien, logic thuần (quyết định báo, nội dung
tiếng Việt, lỗi Telegram), workflow CanhBaoVuotNguong trên máy chủ test của temporalio (activity giả),
bộ khởi chạy (signal-with-start, đợt đã xong), activity gui_canh_bao với CSDL/NATS giả và Telegram giả
(httpx.MockTransport), cầu nối web."""

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest
from temporalio import activity
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment, WorkflowEnvironment
from temporalio.worker import Worker

from cuu_tro_workflow import cam_bien as cb
from cuu_tro_workflow import canh_bao, config
from cuu_tro_workflow import thong_bao as tb
from cuu_tro_workflow.canh_bao import SuKien, ThamSoCanhBao, TrangThaiCanhBao, YeuCauGui
from cuu_tro_workflow.canh_bao_gui import CauHinhGui, GuiCanhBao
from cuu_tro_workflow.canh_bao_khoi_chay import BoKhoiChayCanhBao, khoi_chay_mot
from cuu_tro_workflow.workflows import QUERY_TRANG_THAI, CanhBaoVuotNguong

TQ = "test-canh-bao"
DOT = "2026-10-24T01:00:00.000Z"
BAY_GIO = datetime(2026, 10, 24, 1, 30, tzinfo=timezone.utc)


def su_kien(loai="vuot_nguong", muc="canh_bao", muc_truoc="binh_thuong", gia_tri=320.0, nguong=300.0,
            ma="QN-CL-01", dot=DOT, thoi_diem="2026-10-24T01:00:00+00:00") -> dict:
    return {"loai": loai, "ma_tram": ma, "ten_tram": "Mực nước sông Thu Bồn tại Câu Lâu, Duy Xuyên (giả lập)",
            "dai_luong": "muc_nuoc", "muc": muc, "muc_truoc": muc_truoc, "gia_tri": gia_tri, "nguong": nguong,
            "don_vi": "cm", "thoi_diem": thoi_diem, "dot": dot}


def sk(**kw) -> SuKien:
    d = su_kien(**kw)
    return canh_bao.doc_su_kien(f"cuu-tro.canh-bao.cam-bien.{d['ma_tram']}", d)


# ---------- Sự kiện từ consumer ghi-csdl (cam_bien) ----------
def test_cam_bien_su_kien_co_ma_dot_va_ve_duoi_nguong():
    bt = cb.phan_tich("cuu-tro.cam-bien.QN-CL-01.muc-nuoc", json.dumps(
        {"ma_tram": "QN-CL-01", "gia_tri": 280, "don_vi": "cm", "thoi_diem": "2026-10-24T08:30:00+07:00"}).encode(), BAY_GIO)
    dot = datetime(2026, 10, 24, 1, 0, tzinfo=timezone.utc)
    vuot = cb.su_kien_canh_bao(bt, "Câu Lâu", None, "canh_bao", Decimal(300), Decimal(400), dot)
    assert vuot["dot"] == DOT and vuot["loai"] == "vuot_nguong"
    ve = cb.su_kien_ve_duoi_nguong(bt, "Câu Lâu", "nguy_hiem", Decimal(300), dot)
    assert ve == {**ve, "loai": "ve_duoi_nguong", "muc": "binh_thuong", "muc_truoc": "nguy_hiem", "nguong": 300.0,
                  "dot": DOT}
    # Không có dot (bản tin đầu tiên của đợt): mã đợt = thời điểm của chính bản tin
    assert cb.su_kien_canh_bao(bt, "Câu Lâu", None, "canh_bao", None, None)["dot"] == "2026-10-24T01:30:00.000Z"
    for e in (vuot, ve):
        assert canh_bao.doc_su_kien("cuu-tro.canh-bao.cam-bien.QN-CL-01", e).dot == DOT


@pytest.mark.parametrize("truoc,moi,moi_nhat,mong_doi", [
    ("canh_bao", "binh_thuong", True, True), ("nguy_hiem", "binh_thuong", True, True),
    ("binh_thuong", "binh_thuong", True, False), (None, "binh_thuong", True, False),
    ("nguy_hiem", "canh_bao", True, False),      # hạ cấp nhưng chưa về dưới ngưỡng: không phải kết thúc đợt
    ("canh_bao", "binh_thuong", False, False),   # bản tin gửi bù cũ hơn lần đo cuối
])
def test_can_phat_ve_duoi_nguong(truoc, moi, moi_nhat, mong_doi):
    assert cb.can_phat_ve_duoi_nguong(truoc, moi, moi_nhat) is mong_doi


# ---------- Logic thuần ----------
@pytest.mark.parametrize("subject,d", [
    ("cuu-tro.canh-bao.cam-bien.QN-CL-01", {**su_kien(), "loai": "khac"}),
    ("cuu-tro.canh-bao.cam-bien.QN-CL-01", {**su_kien(), "muc": "binh_thuong"}),   # vượt ngưỡng mà mức bình thường
    ("cuu-tro.canh-bao.cam-bien.QN-CL-01", su_kien(loai="ve_duoi_nguong", muc="canh_bao")),
    ("cuu-tro.canh-bao.cam-bien.KHAC-01", su_kien()),                              # mã trạm khác subject
    ("cuu-tro.canh-bao.cam-bien.QN-CL-01", {**su_kien(), "dot": "hom-qua"}),
    ("cuu-tro.canh-bao.cam-bien.QN-CL-01", {**su_kien(), "dot": "2026-10-24T01:00:00"}),  # thiếu múi giờ
    ("cuu-tro.canh-bao.cam-bien.QN-CL-01", {**su_kien(), "gia_tri": "cao"}),
    ("cuu-tro.cam-bien.QN-CL-01.muc-nuoc", su_kien()),
    ("cuu-tro.canh-bao.cam-bien.QN-CL-01", [1]),
])
def test_doc_su_kien_sai(subject, d):
    with pytest.raises(canh_bao.SuKienKhongHopLe):
        canh_bao.doc_su_kien(subject, d)


def test_doc_su_kien_quy_dot_ve_utc():
    s = sk(dot="2026-10-24T08:00:00+07:00")
    assert s.dot == DOT and canh_bao.workflow_id(s.ma_tram, s.dot) == f"canh-bao-QN-CL-01-{DOT}"


@pytest.mark.parametrize("loai,muc,da_bao,mong_doi", [
    ("vuot_nguong", "canh_bao", [], "canh_bao"),
    ("vuot_nguong", "nguy_hiem", [], "nguy_hiem"),               # nhảy thẳng lên nguy hiểm
    ("vuot_nguong", "canh_bao", ["canh_bao"], None),             # đo lại vẫn cảnh báo / sự kiện giao lại
    ("vuot_nguong", "nguy_hiem", ["canh_bao"], "nguy_hiem"),     # lên cấp
    ("vuot_nguong", "nguy_hiem", ["canh_bao", "nguy_hiem"], None),
    ("vuot_nguong", "canh_bao", ["canh_bao", "nguy_hiem"], None),  # xuống từ nguy hiểm về cảnh báo
    ("vuot_nguong", "nguy_hiem", ["nguy_hiem"], None),
    ("ve_duoi_nguong", "binh_thuong", ["canh_bao"], "ve_duoi_nguong"),
    ("ve_duoi_nguong", "binh_thuong", [], None),                 # chưa báo gì thì không báo kết thúc
    ("ve_duoi_nguong", "binh_thuong", ["canh_bao", "ve_duoi_nguong"], None),
    ("vuot_nguong", "nguy_hiem", ["canh_bao", "ve_duoi_nguong"], None),  # đợt đã kết thúc
])
def test_quyet_dinh(loai, muc, da_bao, mong_doi):
    assert canh_bao.quyet_dinh(sk(loai=loai, muc=muc), da_bao) == mong_doi


def test_noi_dung_tieng_viet_vuot_nguong():
    yc = YeuCauGui(buoc="nguy_hiem", su_kien=sk(muc="nguy_hiem", muc_truoc="canh_bao", gia_tri=412.5, nguong=400.0,
                                              thoi_diem="2026-10-24T01:52:02.069+00:00"), da_bao=["canh_bao"])
    t = canh_bao.noi_dung(yc, 108.278, 15.866, "http://localhost:9080")
    assert t.splitlines() == [
        "🔴 NGUY HIỂM: Mực nước sông Thu Bồn tại Câu Lâu, Duy Xuyên (giả lập) (QN-CL-01)",
        "Mực nước: 412,5 cm (ngưỡng nguy hiểm 400 cm)",
        "Cấp báo động: Nguy hiểm (trước: Cảnh báo)",
        "Thời điểm đo: 08:52 24/10/2026 (giờ Việt Nam)",
        "Bản đồ: https://www.openstreetmap.org/?mlat=15.86600&mlon=108.27800#map=14/15.86600/108.27800",
        "Web điều phối: http://localhost:9080/",
    ]
    canh = canh_bao.noi_dung(YeuCauGui(buoc="canh_bao", su_kien=sk()), None, None, "")
    assert canh.splitlines()[0].startswith("🟠 CẢNH BÁO:") and "Cấp báo động: Cảnh báo" in canh
    assert "Bản đồ" not in canh and "Web điều phối" not in canh


def test_noi_dung_ve_duoi_nguong():
    yc = YeuCauGui(buoc="ve_duoi_nguong", su_kien=sk(loai="ve_duoi_nguong", muc="binh_thuong", muc_truoc="canh_bao",
                                                   gia_tri=280.0, nguong=300.0), da_bao=["canh_bao", "nguy_hiem"])
    t = canh_bao.noi_dung(yc, 108.278, 15.866, "http://gw")
    assert t.splitlines()[:3] == [
        "🟢 ĐÃ VỀ DƯỚI NGƯỠNG: Mực nước sông Thu Bồn tại Câu Lâu, Duy Xuyên (giả lập) (QN-CL-01)",
        "Mực nước: 280 cm (dưới ngưỡng cảnh báo 300 cm)",
        "Cấp báo động: Bình thường (cao nhất trong đợt: Nguy hiểm)",
    ]


@pytest.mark.parametrize("ma,than,mong_doi", [
    (429, {"ok": False, "parameters": {"retry_after": 7}}, (True, 7.0)),
    (429, None, (True, None)),
    (500, None, (True, None)), (502, {"ok": False}, (True, None)),
    (400, {"ok": False, "description": "Bad Request: chat not found"}, (False, None)),
    (401, None, (False, None)), (403, None, (False, None)), (404, None, (False, None)),
])
def test_loi_telegram(ma, than, mong_doi):
    assert canh_bao.loi_telegram(ma, than) == mong_doi


def test_cau_noi_dua_thong_bao_da_gui_len_web():
    s = sk(muc="nguy_hiem", muc_truoc="canh_bao")
    t = tb.chuyen_su_kien(f"{canh_bao.TIEN_TO_WEB}QN-CL-01", json.dumps(canh_bao.su_kien_web(s, "nguy_hiem")).encode(),
                          canh_bao.ma_tin_web(s, "nguy_hiem"), "CUU_TRO_DIEU_PHOI", 9)
    assert t.kenh == "dieu-phoi" and t.du_lieu["loai"] == "canh_bao" and t.du_lieu["buoc"] == "nguy_hiem"
    assert t.du_lieu["ma_tram"] == "QN-CL-01" and t.du_lieu["dot"] == DOT
    assert t.khoa == f"CUU_TRO_DIEU_PHOI:canh-bao:QN-CL-01:{DOT}:nguy_hiem"


# ---------- Workflow trên máy chủ test ----------
class GuiGia:
    """Activity gui_canh_bao giả: ghi lại các bước đã gửi; loi_lan_dau = số lần đầu báo lỗi."""

    def __init__(self, loi: int = 0, hong_vinh_vien: bool = False) -> None:
        self.da_gui: list[tuple[str, str, str]] = []
        self.lan_goi = 0
        self.loi, self.hong = loi, hong_vinh_vien

    @activity.defn(name="gui_canh_bao")
    async def gui_canh_bao(self, yc: YeuCauGui) -> str:
        self.lan_goi += 1
        if self.hong:
            raise ApplicationError("Telegram 401", non_retryable=True)
        if self.loi:
            self.loi -= 1
            raise ApplicationError("mạng chập chờn")
        self.da_gui.append((yc.su_kien.ma_tram, yc.su_kien.dot, yc.buoc))
        return "da_gui"


def chay(kich_ban, gui: GuiGia | None = None):
    gui = gui or GuiGia()

    async def _main():
        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(env.client, task_queue=TQ, workflows=[CanhBaoVuotNguong], activities=[gui.gui_canh_bao]):
                return await kich_ban(env, gui)

    return asyncio.run(_main())


async def gui_su_kien(env, *ds: dict) -> list[str]:
    return [await khoi_chay_mot(env.client, TQ, canh_bao.doc_su_kien(f"cuu-tro.canh-bao.cam-bien.{d['ma_tram']}", d),
                                7 * 24 * 3600) for d in ds]


def test_moi_buoc_cua_dot_bao_dung_mot_lan():
    async def kb(env, gui):
        kq = await gui_su_kien(
            env,
            su_kien(muc="canh_bao"),                                    # vượt ngưỡng cảnh báo
            su_kien(muc="canh_bao"),                                    # sự kiện giao lại
            su_kien(muc="nguy_hiem", muc_truoc="canh_bao", gia_tri=410, nguong=400),  # lên cấp
            su_kien(muc="nguy_hiem", muc_truoc="canh_bao", gia_tri=405, nguong=400),  # xuống rồi lên lại
            su_kien(muc="canh_bao", muc_truoc="binh_thuong"),           # gửi bù cũ
            su_kien(loai="ve_duoi_nguong", muc="binh_thuong", muc_truoc="canh_bao", gia_tri=280),
        )
        h = env.client.get_workflow_handle_for(CanhBaoVuotNguong.run, canh_bao.workflow_id("QN-CL-01", DOT))
        tt = await h.result()
        # Đợt đã kết thúc: sự kiện muộn của đúng đợt đó không tạo đợt mới, không gửi thêm
        muon = await gui_su_kien(env, su_kien(loai="ve_duoi_nguong", muc="binh_thuong", muc_truoc="canh_bao"),
                                 su_kien(muc="nguy_hiem"))
        return kq, tt, muon

    gui = GuiGia()
    kq, tt, muon = chay(kb, gui)
    assert kq[0] == "gui" and muon == ["da_xong", "da_xong"]
    assert gui.da_gui == [("QN-CL-01", DOT, "canh_bao"), ("QN-CL-01", DOT, "nguy_hiem"), ("QN-CL-01", DOT, "ve_duoi_nguong")]
    assert tt.da_bao == ["canh_bao", "nguy_hiem", "ve_duoi_nguong"] and tt.ket_thuc == "ve_duoi_nguong"


def test_hai_dot_khac_nhau_hai_workflow_rieng():
    dot2 = "2026-10-24T05:00:00.000Z"

    async def kb(env, gui):
        await gui_su_kien(env, su_kien(muc="canh_bao"),
                          su_kien(loai="ve_duoi_nguong", muc="binh_thuong", muc_truoc="canh_bao"),
                          su_kien(muc="canh_bao", dot=dot2), su_kien(muc="canh_bao", ma="QN-AN-01"))
        h2 = env.client.get_workflow_handle(canh_bao.workflow_id("QN-CL-01", dot2))
        for _ in range(100):
            if len(gui.da_gui) >= 4:
                break
            await asyncio.sleep(0.05)
        return await h2.query(QUERY_TRANG_THAI, result_type=TrangThaiCanhBao)

    gui = GuiGia()
    tt2 = chay(kb, gui)
    assert sorted(gui.da_gui) == sorted([("QN-CL-01", DOT, "canh_bao"), ("QN-CL-01", DOT, "ve_duoi_nguong"),
                                         ("QN-CL-01", "2026-10-24T05:00:00.000Z", "canh_bao"),
                                         ("QN-AN-01", DOT, "canh_bao")])
    assert tt2.da_bao == ["canh_bao"] and tt2.ket_thuc is None  # đợt 2 còn mở


def test_ve_duoi_nguong_khi_chua_bao_gi_thi_dong_ngay_khong_gui():
    async def kb(env, gui):
        await gui_su_kien(env, su_kien(loai="ve_duoi_nguong", muc="binh_thuong", muc_truoc="canh_bao"))
        return await env.client.get_workflow_handle_for(CanhBaoVuotNguong.run, canh_bao.workflow_id("QN-CL-01", DOT)).result()

    gui = GuiGia()
    tt = chay(kb, gui)
    assert gui.da_gui == [] and tt.ket_thuc == "khong_bao" and tt.da_bao == []


def test_dot_khong_ve_duoi_nguong_thi_het_han():
    async def kb(env, gui):
        await gui_su_kien(env, su_kien(muc="canh_bao"))
        h = env.client.get_workflow_handle_for(CanhBaoVuotNguong.run, canh_bao.workflow_id("QN-CL-01", DOT))
        await env.sleep(timedelta(days=8))  # tua thời gian: trạm mất tín hiệu, hết hạn đợt (7 ngày)
        return await h.result()

    gui = GuiGia()
    tt = chay(kb, gui)
    assert [b for _, _, b in gui.da_gui] == ["canh_bao"] and tt.ket_thuc == "het_han"


def test_gui_loi_tam_thoi_thi_thu_lai():
    async def kb(env, gui):
        await gui_su_kien(env, su_kien(muc="nguy_hiem", nguong=400, gia_tri=420),
                          su_kien(loai="ve_duoi_nguong", muc="binh_thuong", muc_truoc="nguy_hiem"))
        return await env.client.get_workflow_handle_for(CanhBaoVuotNguong.run, canh_bao.workflow_id("QN-CL-01", DOT)).result()

    gui = GuiGia(loi=3)
    tt = chay(kb, gui)
    assert gui.lan_goi == 5 and [b for _, _, b in gui.da_gui] == ["nguy_hiem", "ve_duoi_nguong"]
    assert tt.ket_thuc == "ve_duoi_nguong"


def test_gui_hong_vinh_vien_dot_van_tiep_tuc():
    async def kb(env, gui):
        await gui_su_kien(env, su_kien(muc="canh_bao"),
                          su_kien(loai="ve_duoi_nguong", muc="binh_thuong", muc_truoc="canh_bao"))
        return await env.client.get_workflow_handle_for(CanhBaoVuotNguong.run, canh_bao.workflow_id("QN-CL-01", DOT)).result()

    gui = GuiGia(hong_vinh_vien=True)
    tt = chay(kb, gui)
    assert gui.lan_goi == 2 and tt.ket_thuc == "ve_duoi_nguong"  # mỗi bước một lần, không thử lại lỗi vĩnh viễn


# ---------- Bộ khởi chạy ----------
class MsgGia:
    def __init__(self, subject: str, data: bytes):
        self.subject, self.data = subject, data
        self.ket_qua: list = []

    async def ack(self):
        self.ket_qua.append("ack")

    async def nak(self, delay=None):
        self.ket_qua.append(("nak", delay))

    async def term(self):
        self.ket_qua.append("term")


@pytest.mark.parametrize("subject,data", [
    ("cuu-tro.canh-bao.cam-bien.QN-CL-01", b"{hong"),
    ("cuu-tro.canh-bao.cam-bien.QN-CL-01", json.dumps({**su_kien(), "loai": "la"}).encode()),
    ("cuu-tro.canh-bao.cam-bien.QN-CL-01", b"\xff"),
])
def test_bo_khoi_chay_bo_su_kien_sai(subject, data):
    m = MsgGia(subject, data)
    assert asyncio.run(BoKhoiChayCanhBao(None, config.load()).mot_ban_tin(m)) == "bo" and m.ket_qua == ["term"]


def test_bo_khoi_chay_temporal_loi_thi_giao_lai():
    class ClientHong:
        async def start_workflow(self, *a, **kw):
            raise RuntimeError("Temporal chưa sẵn sàng")

    m = MsgGia("cuu-tro.canh-bao.cam-bien.QN-CL-01", json.dumps(su_kien()).encode())
    assert asyncio.run(BoKhoiChayCanhBao(ClientHong(), config.load()).mot_ban_tin(m)) == "loi"
    assert m.ket_qua == [("nak", 5)]


def test_bo_khoi_chay_dung_signal_with_start():
    goi = {}

    class ClientGhi:
        async def start_workflow(self, fn, arg, **kw):
            goi.update(kw, arg=arg)

    m = MsgGia("cuu-tro.canh-bao.cam-bien.QN-CL-01", json.dumps(su_kien()).encode())
    assert asyncio.run(BoKhoiChayCanhBao(ClientGhi(), config.load()).mot_ban_tin(m)) == "gui" and m.ket_qua == ["ack"]
    assert goi["id"] == f"canh-bao-QN-CL-01-{DOT}" and goi["start_signal"] == "su_kien"
    assert goi["id_reuse_policy"].name == "REJECT_DUPLICATE" and goi["arg"] == ThamSoCanhBao("QN-CL-01", DOT, 604800)


# ---------- Activity gui_canh_bao ----------
class PoolGia:
    """Bảng sensor_alert_notifications trong bộ nhớ, đủ cho 3 câu SQL của canh_bao_gui."""

    def __init__(self):
        self.dong: dict[tuple, dict] = {}

    async def fetchrow(self, sql, *a):
        if "FROM cuu_tro.sensors" in sql:
            return {"kinh_do": 108.278, "vi_do": 15.866}
        khoa = (a[0], a[1], a[2])
        if khoa in self.dong:
            self.dong[khoa]["attempts"] += 1
        else:
            self.dong[khoa] = {"id": len(self.dong) + 1, "status": "dang_gui", "attempts": 1, "message": a[8],
                               "channel": a[9], "detail": None, "episode_at": a[1]}
        d = self.dong[khoa]
        return {"id": d["id"], "status": d["status"]}

    async def execute(self, sql, id_, status, detail):
        for d in self.dong.values():
            if d["id"] == id_:
                d["status"], d["detail"] = status, detail


class JsGia:
    def __init__(self):
        self.tin: list[tuple[str, dict, dict]] = []

    async def publish(self, subject, data, headers=None):
        self.tin.append((subject, json.loads(data), headers))


def gui_activity(gui: GuiCanhBao, yc: YeuCauGui):
    return asyncio.run(ActivityEnvironment().run(gui.gui_canh_bao, yc))


def telegram_gia(tra_loi):
    goi: list[httpx.Request] = []

    def xu_ly(req):
        goi.append(req)
        return tra_loi(req)

    return httpx.AsyncClient(transport=httpx.MockTransport(xu_ly)), goi


def yc(buoc="canh_bao") -> YeuCauGui:
    return YeuCauGui(buoc=buoc, su_kien=sk())


def test_gia_lap_ghi_hop_thu_va_day_web_dung_mot_lan():
    pool, js = PoolGia(), JsGia()
    g = GuiCanhBao(pool, js, CauHinhGui(web_url="http://localhost:9080"))
    assert gui_activity(g, yc()) == "da_gui"
    assert gui_activity(g, yc()) == "da_gui_truoc"  # activity chạy lại
    (d,) = pool.dong.values()
    assert d["status"] == "da_gui" and d["attempts"] == 2 and d["channel"] == "gia-lap"
    assert d["episode_at"] == datetime(2026, 10, 24, 1, tzinfo=timezone.utc)
    assert "CẢNH BÁO" in d["message"] and "Web điều phối: http://localhost:9080/" in d["message"]
    (subject, payload, headers), = js.tin
    assert subject == "cuu-tro.dieu-phoi.canh-bao.QN-CL-01" and payload["buoc"] == "canh_bao"
    assert headers == {"Nats-Msg-Id": f"canh-bao:QN-CL-01:{DOT}:canh_bao"}


def test_telegram_gui_dung_chat_va_noi_dung():
    http, goi = telegram_gia(lambda r: httpx.Response(200, json={"ok": True, "result": {"message_id": 42}}))
    pool, js = PoolGia(), JsGia()
    g = GuiCanhBao(pool, js, CauHinhGui(kenh="telegram", telegram_api_url="http://tg.test", telegram_bot_token="123:ABC",
                                        telegram_chat_id="-1001"), http)
    assert gui_activity(g, yc("nguy_hiem")) == "da_gui"
    (req,) = goi
    assert str(req.url) == "http://tg.test/bot123:ABC/sendMessage"
    body = json.loads(req.content)
    assert body["chat_id"] == "-1001" and body["text"].startswith("🔴 NGUY HIỂM:")
    (d,) = pool.dong.values()
    assert d["status"] == "da_gui" and d["detail"] == "telegram message_id 42" and d["channel"] == "telegram"
    assert len(js.tin) == 1


def test_telegram_429_thu_lai_theo_retry_after():
    http, _ = telegram_gia(lambda r: httpx.Response(429, json={"ok": False, "parameters": {"retry_after": 9}}))
    g = GuiCanhBao(PoolGia(), JsGia(), CauHinhGui(kenh="telegram", telegram_bot_token="t", telegram_chat_id="c"), http)
    with pytest.raises(ApplicationError) as e:
        gui_activity(g, yc())
    assert not e.value.non_retryable and e.value.next_retry_delay == timedelta(seconds=9)


def test_telegram_mang_loi_thu_lai_khong_lo_token():
    def mat_mang(r):
        raise httpx.ConnectError("không kết nối được tới http://tg/botBI-MAT/sendMessage", request=r)

    http, _ = telegram_gia(mat_mang)
    g = GuiCanhBao(PoolGia(), JsGia(), CauHinhGui(kenh="telegram", telegram_bot_token="BI-MAT", telegram_chat_id="c"), http)
    with pytest.raises(ApplicationError) as e:
        gui_activity(g, yc())
    assert not e.value.non_retryable and "BI-MAT" not in str(e.value)


@pytest.mark.parametrize("ma", [400, 401, 403])
def test_telegram_tu_choi_thi_khong_thu_lai_va_ghi_loi(ma):
    http, _ = telegram_gia(lambda r: httpx.Response(ma, json={"ok": False, "description": "Unauthorized"}))
    pool, js = PoolGia(), JsGia()
    g = GuiCanhBao(pool, js, CauHinhGui(kenh="telegram", telegram_bot_token="t", telegram_chat_id="c"), http)
    with pytest.raises(ApplicationError) as e:
        gui_activity(g, yc())
    assert e.value.non_retryable and not js.tin
    (d,) = pool.dong.values()
    assert d["status"] == "loi" and f"HTTP {ma}" in d["detail"]


def test_telegram_chua_cau_hinh_token():
    pool = PoolGia()
    g = GuiCanhBao(pool, JsGia(), CauHinhGui(kenh="telegram"))
    with pytest.raises(ApplicationError) as e:
        gui_activity(g, yc())
    assert e.value.non_retryable and next(iter(pool.dong.values()))["status"] == "loi"


def test_kenh_sai_bao_loi_ngay():
    with pytest.raises(ValueError):
        GuiCanhBao(PoolGia(), JsGia(), CauHinhGui(kenh="sms"))


def test_cau_hinh_doc_bien_moi_truong(monkeypatch):
    monkeypatch.setenv("CANH_BAO_KENH", " Telegram ")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", " t ")
    monkeypatch.setenv("CANH_BAO_HAN_DOT_GIAY", "5")
    c = config.load()
    assert c.canh_bao_kenh == "telegram" and c.telegram_bot_token == "t" and c.canh_bao_han_dot_giay == 60


def test_khai_bao_consumer():
    from pathlib import Path

    from cuu_tro_workflow.cam_bien_consumer import doc_khai_bao
    _, consumers = doc_khai_bao(str(Path(__file__).resolve().parents[2] / "nats" / "streams.json"))
    assert {c.durable_name for s, c in consumers if s == "CUU_TRO_CANH_BAO"} == {"canh-bao-temporal"}
    assert SimpleNamespace  # dùng cho kiểu MsgGia ở các test khác
