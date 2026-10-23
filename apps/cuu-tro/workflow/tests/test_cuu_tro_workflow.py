# SPDX-License-Identifier: Apache-2.0
"""Workflow PhanCongCuuHo và Hello trên môi trường test của temporalio (máy chủ test tự tua thời gian).

Activity được thay bằng bản giả cùng tên, giữ "CSDL" trong bộ nhớ: kiểm luồng điều phối (gán đội gần
nhất, chờ nhận có hạn theo urgency, phân công lại khi từ chối/quá hạn, nhường đội cho tin khẩn hơn,
hết lần giao thì báo điều phối, tự khởi chạy không trùng) mà không cần PostgreSQL. Luật SQL thật
(outbox, urgency_rank, team_reserved_for_more_urgent) kiểm ở db/tests/0007. Lần chạy đầu temporalio
tải máy chủ test (một tệp nhị phân) về thư mục tạm.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from temporalio import activity
from temporalio.client import WorkflowHandle
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from cuu_tro_workflow import config, khoi_chay
from cuu_tro_workflow.activities import chao
from cuu_tro_workflow.logic import (
    BAO_HET_LAN_GIAO,
    BAO_KHONG_CO_DOI,
    BAO_QUA_HAN_XAC_NHAN,
    GAN_BI_GIANH,
    GAN_DA_GAN,
    GAN_NHUONG,
    GAN_TIN_DA_DOI,
    GIAO_DA_NHAN,
    GIAO_HUY,
    GIAO_QUA_HAN,
    GIAO_TU_CHOI,
    KQ_BO_QUA,
    KQ_DA_DONG,
    KQ_DA_HUY,
    KQ_HET_LAN_GIAO,
    KQ_KHONG_CO_DOI,
    KQ_QUA_HAN,
    URGENCY_RANK,
    BaoDieuPhoi,
    DoiUngVien,
    KetQuaGiao,
    PhanHoi,
    ThamSoPhanCong,
    TinKeuCuu,
    TrangThaiPhanCong,
    XacNhan,
    YeuCauGan,
    YeuCauHuy,
)
from cuu_tro_workflow.workflows import (
    QUERY_TRANG_THAI,
    SIGNAL_HUY,
    SIGNAL_NHAN,
    SIGNAL_TU_CHOI,
    SIGNAL_XAC_NHAN,
    Hello,
    PhanCongCuuHo,
)

TQ = "test-cuu-tro"
INC = "b0000000-0000-4000-8000-000000000004"
INC_KHAN = "b0000000-0000-4000-8000-000000000001"


@dataclass
class CsdlGia:
    tin: dict[str, dict] = field(default_factory=lambda: {INC: {"status": "tiep_nhan", "urgency": "cao", "doi": None}})
    doi: dict[str, tuple[str, float | None]] = field(default_factory=lambda: {
        "doi-1": ("san_sang", 430.0),
        "doi-2": ("san_sang", 2400.0),
        "doi-3": ("dang_lam_nhiem_vu", 120.0),
        "doi-4": ("san_sang", 5100.0),
    })
    # Đội bị "đội khác giành" đúng lúc gán (gan_doi trả bi_gianh một lần)
    bi_gianh: set[str] = field(default_factory=set)
    # Tin đang được workflow tìm đội (assignment_queue.seeking_at)
    dang_tim: set[str] = field(default_factory=set)
    # Lịch sử giao: (incident, lần) → dict (incident_assignments)
    giao: dict[tuple[str, int], dict] = field(default_factory=dict)
    bao: list[BaoDieuPhoi] = field(default_factory=list)
    bao_loi: bool = False

    def _doi_trang_thai(self, doi_id: str, trang_thai: str) -> None:
        self.doi[doi_id] = (trang_thai, self.doi[doi_id][1])

    def lich_su(self, incident_id: str = INC) -> list[tuple[str, str]]:
        return [(g["doi"], g["ket_qua"]) for (i, _), g in sorted(self.giao.items()) if i == incident_id]

    def activities(self):
        @activity.defn(name="doc_tin")
        async def doc_tin(incident_id: str) -> TinKeuCuu | None:
            t = self.tin.get(incident_id)
            if t is None:
                return None
            return TinKeuCuu(id=incident_id, trang_thai=t["status"], doi_id=t["doi"], urgency=t["urgency"])

        @activity.defn(name="tim_doi_ung_vien")
        async def tim_doi_ung_vien(incident_id: str, ban_kinh_m: int) -> list[DoiUngVien]:
            self.dang_tim.add(incident_id)
            return [DoiUngVien(id=k, ten=k, trang_thai=s, khoang_cach_m=d) for k, (s, d) in self.doi.items()]

        @activity.defn(name="gan_doi")
        async def gan_doi(yc: YeuCauGan) -> str:
            t = self.tin.get(yc.incident_id)
            if t is None or t["status"] != "tiep_nhan":
                return GAN_TIN_DA_DOI
            # Luật nhường đội (bản gọn của team_reserved_for_more_urgent, không xét bán kính)
            if any(i != yc.incident_id and o["status"] == "tiep_nhan"
                   and URGENCY_RANK[o["urgency"]] < URGENCY_RANK[t["urgency"]]
                   for i, o in self.tin.items() if i in self.dang_tim):
                return GAN_NHUONG
            if yc.doi_id in self.bi_gianh:
                self.bi_gianh.discard(yc.doi_id)
                self._doi_trang_thai(yc.doi_id, "dang_lam_nhiem_vu")
                return GAN_BI_GIANH
            if self.doi[yc.doi_id][0] != "san_sang":
                return GAN_BI_GIANH
            t.update(status="phan_cong", doi=yc.doi_id)
            self._doi_trang_thai(yc.doi_id, "dang_lam_nhiem_vu")
            self.dang_tim.discard(yc.incident_id)
            self.giao[(yc.incident_id, yc.lan)] = {
                "doi": yc.doi_id, "ket_qua": "cho_nhan", "han": yc.han_nhan_giay, "nguoi": None,
                "luc": activity.info().scheduled_time,
            }
            return GAN_DA_GAN

        @activity.defn(name="nhan_nhiem_vu")
        async def nhan_nhiem_vu(kq: KetQuaGiao) -> str:
            self.tin[kq.incident_id]["status"] = "dang_cuu"
            self.giao[(kq.incident_id, kq.lan)].update(ket_qua=GIAO_DA_NHAN, nguoi=kq.nguoi)
            return "dang_cuu"

        @activity.defn(name="go_doi")
        async def go_doi(kq: KetQuaGiao) -> str:
            self.tin[kq.incident_id].update(status="tiep_nhan", doi=None)
            self._doi_trang_thai(kq.doi_id, "san_sang")
            self.giao[(kq.incident_id, kq.lan)].update(ket_qua=kq.ket_qua, nguoi=kq.nguoi)
            return "tiep_nhan"

        @activity.defn(name="dung_tim")
        async def dung_tim(incident_id: str) -> None:
            self.dang_tim.discard(incident_id)

        @activity.defn(name="bao_dieu_phoi")
        async def bao_dieu_phoi(bd: BaoDieuPhoi) -> None:
            if self.bao_loi:
                raise ApplicationError("NATS không với tới", non_retryable=True)
            self.bao.append(bd)

        @activity.defn(name="ket_thuc")
        async def ket_thuc(incident_id: str, doi_id: str) -> str:
            self.tin[incident_id]["status"] = "dong"
            self._doi_trang_thai(doi_id, "san_sang")
            return "dong"

        return [chao, doc_tin, tim_doi_ung_vien, gan_doi, nhan_nhiem_vu, go_doi, dung_tim, bao_dieu_phoi, ket_thuc]


def chay(kich_ban, csdl: CsdlGia | None = None):
    """Khởi động máy chủ test + worker với activity giả, chạy kịch bản async(env, csdl)."""
    csdl = csdl or CsdlGia()

    async def _main():
        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(env.client, task_queue=TQ, workflows=[Hello, PhanCongCuuHo],
                              activities=csdl.activities()):
                return await kich_ban(env, csdl)

    return asyncio.run(_main())


async def bat_dau(env, **kw) -> WorkflowHandle:
    return await env.client.start_workflow(
        PhanCongCuuHo.run, ThamSoPhanCong(incident_id=kw.pop("incident_id", INC), nguoi_khoi_chay="dieuphoi01", **kw),
        id=f"phan-cong-{uuid.uuid4()}", task_queue=TQ,
    )


async def trang_thai(handle: WorkflowHandle) -> TrangThaiPhanCong:
    return await handle.query(QUERY_TRANG_THAI, result_type=TrangThaiPhanCong)


async def cho_buoc(handle: WorkflowHandle, buoc: str, doi_id: str | None = None) -> TrangThaiPhanCong:
    for _ in range(200):
        tt = await trang_thai(handle)
        if tt.buoc == buoc and (doi_id is None or tt.doi_id == doi_id):
            return tt
        await asyncio.sleep(0.05)
    raise AssertionError(f"workflow không tới bước {buoc} ({doi_id}), đang ở {tt.buoc} ({tt.doi_id})")


def ph(nguoi="cuuho01", doi_id=None, ghi_chu="") -> PhanHoi:
    return PhanHoi(loai="", nguoi=nguoi, vai_tro="cuu-ho", doi_id=doi_id, ghi_chu=ghi_chu)


def test_hello():
    async def kb(env, _):
        return await env.client.execute_workflow(Hello.run, "điều phối", id=f"hello-{uuid.uuid4()}", task_queue=TQ)

    assert chay(kb) == "Xin chào điều phối, worker cuu-tro đã nhận việc"


def test_gan_doi_gan_nhat_nhan_roi_xac_nhan_dong():
    async def kb(env, csdl):
        h = await bat_dau(env)
        tt = await cho_buoc(h, "cho_nhan")
        # doi-3 gần hơn nhưng đang làm nhiệm vụ → chọn doi-1 (430 m)
        assert (tt.doi_id, tt.khoang_cach_m, tt.urgency) == ("doi-1", 430.0, "cao")
        assert csdl.tin[INC]["status"] == "phan_cong" and csdl.doi["doi-1"][0] == "dang_lam_nhiem_vu"
        await h.signal(SIGNAL_NHAN, ph(doi_id="doi-1"))
        await cho_buoc(h, "cho_xac_nhan")
        assert csdl.tin[INC]["status"] == "dang_cuu"
        await h.signal(SIGNAL_XAC_NHAN, XacNhan(nguoi="cuuho01", vai_tro="cuu-ho", doi_id="doi-1"))
        return await h.result(), csdl

    kq, csdl = chay(kb)
    assert kq.ket_qua == KQ_DA_DONG and kq.xac_nhan.nguoi == "cuuho01"
    assert [(g.doi_id, g.ket_qua, g.nguoi) for g in kq.giao] == [("doi-1", GIAO_DA_NHAN, "cuuho01")]
    assert csdl.tin[INC]["status"] == "dong" and csdl.doi["doi-1"][0] == "san_sang"
    assert csdl.lich_su() == [("doi-1", GIAO_DA_NHAN)] and not csdl.bao


def test_xac_nhan_da_cuu_khi_con_cho_nhan_thi_coi_nhu_da_nhan():
    async def kb(env, csdl):
        h = await bat_dau(env)
        await cho_buoc(h, "cho_nhan")
        await h.signal(SIGNAL_XAC_NHAN, XacNhan(nguoi="dieuphoi01", vai_tro="dieu-phoi"))
        return await h.result(), csdl

    kq, csdl = chay(kb)
    assert kq.ket_qua == KQ_DA_DONG and csdl.lich_su() == [("doi-1", GIAO_DA_NHAN)]


def test_qua_han_nhan_thi_phan_cong_lai_doi_ke_tiep():
    async def kb(env, csdl):
        h = await bat_dau(env, han_nhan_giay={"cao": 600, "trung_binh": 900})
        await cho_buoc(h, "cho_nhan", "doi-1")
        # Máy chủ test tua qua hạn nhận 600 giây
        await env.sleep(601)
        tt = await cho_buoc(h, "cho_nhan", "doi-2")
        await h.signal(SIGNAL_NHAN, ph(doi_id="doi-2"))
        await cho_buoc(h, "cho_xac_nhan")
        return tt, csdl

    tt, csdl = chay(kb)
    assert [(g.doi_id, g.ket_qua) for g in tt.giao] == [("doi-1", GIAO_QUA_HAN), ("doi-2", "cho_nhan")]
    assert csdl.lich_su() == [("doi-1", GIAO_QUA_HAN), ("doi-2", GIAO_DA_NHAN)]
    # Đội không nhận được trả về sẵn sàng; tin giao cho đội 2
    assert csdl.doi["doi-1"][0] == "san_sang" and csdl.tin[INC]["doi"] == "doi-2"
    lan1, lan2 = csdl.giao[(INC, 1)], csdl.giao[(INC, 2)]
    assert lan1["han"] == 600 and (lan2["luc"] - lan1["luc"]).total_seconds() >= 600


def test_han_nhan_theo_urgency():
    han = {"khan_cap": 120, "cao": 600, "trung_binh": 900, "thap": 3000}

    async def kb(env, csdl):
        h = await bat_dau(env, han_nhan_giay=han)
        await cho_buoc(h, "cho_nhan", "doi-1")
        await env.sleep(121)
        return await cho_buoc(h, "cho_nhan", "doi-2"), csdl

    tt, csdl = chay(kb, CsdlGia(tin={INC: {"status": "tiep_nhan", "urgency": "khan_cap", "doi": None}}))
    assert tt.han_nhan_giay == 120 and csdl.lich_su()[0] == ("doi-1", GIAO_QUA_HAN)

    async def kb_thap(env, csdl):
        h = await bat_dau(env, han_nhan_giay=han)
        await cho_buoc(h, "cho_nhan", "doi-1")
        await env.sleep(600)  # khẩn cấp đã bị phân công lại từ lâu, tin thấp còn trong hạn
        return await trang_thai(h)

    tt = chay(kb_thap, CsdlGia(tin={INC: {"status": "tiep_nhan", "urgency": "thap", "doi": None}}))
    assert (tt.han_nhan_giay, tt.buoc, tt.doi_id, len(tt.giao)) == (3000, "cho_nhan", "doi-1", 1)


def test_tu_choi_thi_giao_doi_ke_tiep_va_bo_phan_hoi_muon():
    async def kb(env, csdl):
        h = await bat_dau(env)
        await cho_buoc(h, "cho_nhan", "doi-1")
        await h.signal(SIGNAL_TU_CHOI, ph(doi_id="doi-1", ghi_chu="ca nô hỏng"))
        await cho_buoc(h, "cho_nhan", "doi-2")
        # Đội 1 bấm "nhận" muộn sau khi đã bị thay: bỏ qua, nhiệm vụ vẫn của đội 2
        await h.signal(SIGNAL_NHAN, ph(nguoi="cuuho-doi-1", doi_id="doi-1"))
        await asyncio.sleep(0.3)
        return await trang_thai(h), csdl

    tt, csdl = chay(kb)
    assert (tt.buoc, tt.doi_id) == ("cho_nhan", "doi-2")
    assert any("bỏ qua signal nhan từ cuuho-doi-1" in d for d in tt.lich_su)
    assert csdl.lich_su() == [("doi-1", GIAO_TU_CHOI), ("doi-2", "cho_nhan")]
    assert csdl.giao[(INC, 1)]["nguoi"] == "cuuho01"


def test_het_lan_giao_thi_bao_dieu_phoi():
    async def kb(env, csdl):
        return await (await bat_dau(env, so_lan_giao_toi_da=2)).result(), csdl

    kq, csdl = chay(kb)
    assert kq.ket_qua == KQ_HET_LAN_GIAO and kq.da_bao_dieu_phoi and kq.doi_id is None
    assert csdl.lich_su() == [("doi-1", GIAO_QUA_HAN), ("doi-2", GIAO_QUA_HAN)]
    assert [(b.ly_do, b.so_lan_giao, b.urgency) for b in csdl.bao] == [(BAO_HET_LAN_GIAO, 2, "cao")]
    # Tin quay về tiep_nhan, mọi đội đã thử trở lại sẵn sàng
    assert csdl.tin[INC]["status"] == "tiep_nhan" and csdl.doi["doi-1"][0] == csdl.doi["doi-2"][0] == "san_sang"


def test_uu_tien_tin_khan_cap_duoc_doi_truoc():
    # Chỉ một đội trong vùng, đang bận; tin thấp và tin khẩn cấp cùng chờ đội
    csdl = CsdlGia(
        tin={INC: {"status": "tiep_nhan", "urgency": "thap", "doi": None},
             INC_KHAN: {"status": "tiep_nhan", "urgency": "khan_cap", "doi": None}},
        doi={"doi-1": ("dang_lam_nhiem_vu", 430.0)},
    )

    async def kb(env, csdl):
        thap = await bat_dau(env, incident_id=INC, cho_tim_lai_giay=60)
        await cho_buoc(thap, "tim_doi")
        khan = await bat_dau(env, incident_id=INC_KHAN, cho_tim_lai_giay=60)
        await cho_buoc(khan, "tim_doi")
        while csdl.dang_tim != {INC, INC_KHAN}:
            await asyncio.sleep(0.05)
        csdl._doi_trang_thai("doi-1", "san_sang")  # đội xong việc cũ
        await env.sleep(61)
        return await cho_buoc(khan, "cho_nhan", "doi-1"), await trang_thai(thap)

    tt_khan, tt_thap = chay(kb, csdl)
    assert tt_khan.urgency == "khan_cap" and csdl.tin[INC_KHAN]["doi"] == "doi-1"
    # Tin thấp không giành được đội (nhường hoặc thấy đội đã bận) và vẫn đang chờ
    assert tt_thap.doi_id is None and tt_thap.buoc == "tim_doi" and csdl.tin[INC]["status"] == "tiep_nhan"


def test_nhuong_doi_cho_tin_khan_hon_dang_cho():
    # Tin khẩn cấp đang chờ đội (seeking) → tin cao không gán đội nào (bản giả nhường mọi đội, không xét
    # bán kính), tìm lại theo chu kỳ rồi báo điều phối; không có lần giao nào
    csdl = CsdlGia(tin={INC: {"status": "tiep_nhan", "urgency": "cao", "doi": None},
                        INC_KHAN: {"status": "tiep_nhan", "urgency": "khan_cap", "doi": None}},
                   dang_tim={INC_KHAN})

    async def kb(env, csdl):
        h = await bat_dau(env, so_lan_tim_doi=2, cho_tim_lai_giay=30)
        return await h.result(), csdl

    kq, csdl = chay(kb, csdl)
    assert kq.ket_qua == KQ_KHONG_CO_DOI and not kq.giao
    assert sum("nhường doi-1 cho tin khẩn hơn" in d for d in kq.lich_su) == 2
    assert [b.ly_do for b in csdl.bao] == [BAO_KHONG_CO_DOI] and INC not in csdl.dang_tim


def test_huy_khi_cho_nhan_thi_go_doi():
    async def kb(env, csdl):
        h = await bat_dau(env)
        await cho_buoc(h, "cho_nhan", "doi-1")
        await h.signal(SIGNAL_HUY, YeuCauHuy(nguoi="dieuphoi01", ly_do="đã có thuyền dân quân tới"))
        return await h.result(), csdl

    kq, csdl = chay(kb)
    assert kq.ket_qua == KQ_DA_HUY
    assert csdl.lich_su() == [("doi-1", GIAO_HUY)] and csdl.giao[(INC, 1)]["nguoi"] == "dieuphoi01"
    assert csdl.tin[INC] == {"status": "tiep_nhan", "urgency": "cao", "doi": None}
    assert csdl.doi["doi-1"][0] == "san_sang"


def test_huy_bi_bo_qua_khi_doi_da_nhan():
    async def kb(env, csdl):
        h = await bat_dau(env)
        await cho_buoc(h, "cho_nhan")
        await h.signal(SIGNAL_NHAN, ph())
        await cho_buoc(h, "cho_xac_nhan")
        await h.signal(SIGNAL_HUY, YeuCauHuy(nguoi="dieuphoi01"))
        await h.signal(SIGNAL_XAC_NHAN, XacNhan(nguoi="cuuho01", vai_tro="cuu-ho"))
        return await h.result()

    assert chay(kb).ket_qua == KQ_DA_DONG


def test_qua_han_xac_nhan_thi_bao_dieu_phoi():
    async def kb(env, csdl):
        h = await bat_dau(env, han_xac_nhan_giay=3600)
        await cho_buoc(h, "cho_nhan")
        await h.signal(SIGNAL_NHAN, ph())
        # Máy chủ test tua nhanh 1 giờ khi chờ kết quả
        return await h.result(), csdl

    kq, csdl = chay(kb)
    assert kq.ket_qua == KQ_QUA_HAN and kq.doi_id == "doi-1"
    # Đội đã nhận và đang ở hiện trường: không tự gỡ đội
    assert csdl.tin[INC]["status"] == "dang_cuu" and [b.ly_do for b in csdl.bao] == [BAO_QUA_HAN_XAC_NHAN]


def test_khong_co_doi_thi_tim_lai_roi_bao_dieu_phoi():
    csdl = CsdlGia(doi={"doi-xa": ("san_sang", 50_000.0), "doi-ban": ("nghi", 10.0)})

    async def kb(env, csdl):
        return await (await bat_dau(env, so_lan_tim_doi=3, cho_tim_lai_giay=120)).result()

    kq = chay(kb, csdl)
    assert kq.ket_qua == KQ_KHONG_CO_DOI and kq.so_lan_tim == 3 and kq.doi_id is None
    assert csdl.tin[INC]["status"] == "tiep_nhan" and [b.ly_do for b in csdl.bao] == [BAO_KHONG_CO_DOI]
    assert INC not in csdl.dang_tim  # đã bỏ giữ chỗ ưu tiên


def test_bao_dieu_phoi_loi_khong_lam_hong_workflow():
    csdl = CsdlGia(doi={}, bao_loi=True)

    async def kb(env, csdl):
        return await (await bat_dau(env, so_lan_tim_doi=1)).result()

    kq = chay(kb, csdl)
    assert kq.ket_qua == KQ_KHONG_CO_DOI and not kq.da_bao_dieu_phoi
    assert any("không gửi được sự kiện báo điều phối" in d for d in kq.lich_su)


def test_doi_bi_gianh_thi_chon_doi_ke_tiep():
    csdl = CsdlGia(bi_gianh={"doi-1"})

    async def kb(env, csdl):
        h = await bat_dau(env)
        return await cho_buoc(h, "cho_nhan")

    tt = chay(kb, csdl)
    assert tt.doi_id == "doi-2" and csdl.tin[INC]["doi"] == "doi-2"


def test_bo_qua_tin_khong_o_tiep_nhan_hoac_khong_co():
    async def kb(env, csdl):
        dang_cuu = await (await bat_dau(env)).result()
        khong_co = await (await bat_dau(env, incident_id="khong-co")).result()
        return dang_cuu, khong_co

    for kq in chay(kb, CsdlGia(tin={INC: {"status": "dang_cuu", "urgency": "cao", "doi": "doi-3"}})):
        assert kq.ket_qua == KQ_BO_QUA and kq.doi_id is None


def test_tin_duoc_xu_ly_tay_khi_dang_cho_tim_lai_thi_dung():
    csdl = CsdlGia(doi={})

    async def kb(env, csdl):
        h = await bat_dau(env, cho_tim_lai_giay=60)
        await cho_buoc(h, "tim_doi")
        csdl.tin[INC]["status"] = "dong"  # điều phối đóng tin (báo nhầm)
        return await h.result()

    kq = chay(kb, csdl)
    assert kq.ket_qua == KQ_BO_QUA and not csdl.bao


# ---------------- Tự khởi chạy (khoi_chay.py) ----------------

def _cfg(**kw) -> config.Config:
    cfg = config.load()
    return config.Config(**{**cfg.__dict__, "task_queue": TQ, **kw})


def test_tu_khoi_chay_id_tat_dinh_khong_chay_trung():
    async def kb(env, csdl):
        cfg = _cfg()
        h = env.client.get_workflow_handle(khoi_chay.workflow_id(INC))
        dau = await khoi_chay.khoi_chay_mot(env.client, cfg, INC, "cao")
        run1 = (await h.describe()).run_id
        # Bộ khởi chạy gọi lại (vd chết trước khi đánh dấu started_at): dùng lại lần đang chạy
        lai = await khoi_chay.khoi_chay_mot(env.client, cfg, INC, "cao")
        tt = await cho_buoc(h, "cho_nhan")
        runs = {run1, (await h.describe()).run_id}
        await h.signal(SIGNAL_XAC_NHAN, XacNhan(nguoi="cuuho01", vai_tro="cuu-ho"))
        await h.result()
        # Đã chạy xong: không khởi chạy lần hai cho cùng tin
        sau = await khoi_chay.khoi_chay_mot(env.client, cfg, INC, "cao")
        return dau, lai, sau, tt, len(runs), csdl

    dau, lai, sau, tt, so_run, csdl = chay(kb)
    assert (dau, lai, sau) == ("dang_chay", "dang_chay", "da_xong")
    assert tt.lich_su[0].endswith("khởi chạy bởi tu-dong") and so_run == 1
    assert csdl.tin[INC]["status"] == "dong" and len(csdl.giao) == 1


def test_tham_so_tu_cau_hinh(monkeypatch):
    monkeypatch.setenv("PHAN_CONG_HAN_NHAN_GIAY_KHAN_CAP", "90")
    monkeypatch.setenv("PHAN_CONG_SO_LAN_GIAO_TOI_DA", "5")
    monkeypatch.setenv("PHAN_CONG_TU_DONG", "0")
    cfg = config.load()
    ts = config.tham_so_phan_cong(cfg, INC, "tu-dong")
    assert ts.han_nhan_giay["khan_cap"] == 90 and ts.han_nhan_giay["thap"] == 1800
    assert ts.so_lan_giao_toi_da == 5 and not cfg.tu_dong
    monkeypatch.setenv("PHAN_CONG_HAN_NHAN_GIAY_CAO", "0")
    try:
        config.load()
        raise AssertionError("hạn 0 giây phải bị từ chối")
    except ValueError:
        pass


def test_moc_thoi_gian_lich_su_dung_dinh_dang():
    # Lịch sử workflow có dấu thời gian ISO (giây) ở đầu mỗi dòng
    async def kb(env, csdl):
        h = await bat_dau(env)
        return await cho_buoc(h, "cho_nhan")

    tt = chay(kb)
    for dong in tt.lich_su:
        datetime.fromisoformat(dong.split(" ", 1)[0])
