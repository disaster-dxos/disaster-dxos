# SPDX-License-Identifier: Apache-2.0
"""Workflow PhanCongCuuHo và Hello trên môi trường test của temporalio (máy chủ test tự tua thời gian).

Activity được thay bằng bản giả cùng tên, giữ "CSDL" trong bộ nhớ: kiểm luồng điều phối (gán đội gần
nhất, chờ signal có hạn, đóng tin) mà không cần PostgreSQL. Lần chạy đầu temporalio tải máy chủ test
(một tệp nhị phân) về thư mục tạm.
"""

import asyncio
import uuid
from dataclasses import dataclass, field

from temporalio import activity
from temporalio.client import WorkflowHandle
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from cuu_tro_workflow.activities import chao
from cuu_tro_workflow.logic import (
    KQ_BO_QUA,
    KQ_DA_DONG,
    KQ_KHONG_CO_DOI,
    KQ_QUA_HAN,
    DoiUngVien,
    ThamSoPhanCong,
    TinKeuCuu,
    TrangThaiPhanCong,
    XacNhan,
)
from cuu_tro_workflow.workflows import QUERY_TRANG_THAI, SIGNAL_XAC_NHAN, Hello, PhanCongCuuHo

TQ = "test-cuu-tro"
INC = "b0000000-0000-4000-8000-000000000004"


@dataclass
class CsdlGia:
    tin: dict[str, str] = field(default_factory=lambda: {INC: "tiep_nhan"})
    doi_cua_tin: dict[str, str] = field(default_factory=dict)
    doi: dict[str, tuple[str, float | None]] = field(default_factory=lambda: {
        "doi-1": ("san_sang", 430.0),
        "doi-2": ("san_sang", 2400.0),
        "doi-3": ("dang_lam_nhiem_vu", 120.0),
    })
    # Đội bị "đội khác giành" đúng lúc gán (gan_doi trả False một lần)
    bi_gianh: set[str] = field(default_factory=set)

    def activities(self):
        @activity.defn(name="doc_tin")
        async def doc_tin(incident_id: str) -> TinKeuCuu | None:
            if incident_id not in self.tin:
                return None
            return TinKeuCuu(id=incident_id, trang_thai=self.tin[incident_id], doi_id=self.doi_cua_tin.get(incident_id))

        @activity.defn(name="tim_doi_ung_vien")
        async def tim_doi_ung_vien(incident_id: str, ban_kinh_m: int) -> list[DoiUngVien]:
            return [DoiUngVien(id=k, ten=k, trang_thai=s, khoang_cach_m=d) for k, (s, d) in self.doi.items()]

        @activity.defn(name="gan_doi")
        async def gan_doi(incident_id: str, doi_id: str) -> bool:
            if doi_id in self.bi_gianh:
                self.bi_gianh.discard(doi_id)
                self.doi[doi_id] = ("dang_lam_nhiem_vu", self.doi[doi_id][1])
                return False
            self.tin[incident_id] = "phan_cong"
            self.doi_cua_tin[incident_id] = doi_id
            self.doi[doi_id] = ("dang_lam_nhiem_vu", self.doi[doi_id][1])
            return True

        @activity.defn(name="ket_thuc")
        async def ket_thuc(incident_id: str, doi_id: str) -> str:
            self.tin[incident_id] = "dong"
            self.doi[doi_id] = ("san_sang", self.doi[doi_id][1])
            return "dong"

        return [chao, doc_tin, tim_doi_ung_vien, gan_doi, ket_thuc]


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


async def cho_buoc(handle: WorkflowHandle, buoc: str) -> TrangThaiPhanCong:
    for _ in range(200):
        tt = await handle.query(QUERY_TRANG_THAI, result_type=TrangThaiPhanCong)
        if tt.buoc == buoc:
            return tt
        await asyncio.sleep(0.05)
    raise AssertionError(f"workflow không tới bước {buoc}, đang ở {tt.buoc}")


def test_hello():
    async def kb(env, _):
        return await env.client.execute_workflow(Hello.run, "điều phối", id=f"hello-{uuid.uuid4()}", task_queue=TQ)

    assert chay(kb) == "Xin chào điều phối, worker cuu-tro đã nhận việc"


def test_gan_doi_gan_nhat_cho_xac_nhan_roi_dong():
    async def kb(env, csdl):
        h = await bat_dau(env)
        tt = await cho_buoc(h, "cho_xac_nhan")
        # doi-3 gần hơn nhưng đang làm nhiệm vụ → chọn doi-1 (430 m)
        assert (tt.doi_id, tt.khoang_cach_m) == ("doi-1", 430.0)
        assert csdl.tin[INC] == "phan_cong" and csdl.doi["doi-1"][0] == "dang_lam_nhiem_vu"
        await h.signal(SIGNAL_XAC_NHAN, XacNhan(nguoi="dieuphoi01", vai_tro="dieu-phoi"))
        return await h.result(), csdl

    kq, csdl = chay(kb)
    assert kq.ket_qua == KQ_DA_DONG and kq.xac_nhan.nguoi == "dieuphoi01"
    assert csdl.tin[INC] == "dong" and csdl.doi["doi-1"][0] == "san_sang"


def test_qua_han_xac_nhan():
    async def kb(env, csdl):
        h = await bat_dau(env, han_xac_nhan_giay=3600)
        # Máy chủ test tua nhanh 1 giờ khi chờ kết quả
        return await h.result(), csdl

    kq, csdl = chay(kb)
    assert kq.ket_qua == KQ_QUA_HAN and kq.doi_id == "doi-1"
    # Khung tuần 2: quá hạn không đổi CSDL (tin vẫn phân công cho đội)
    assert csdl.tin[INC] == "phan_cong"


def test_khong_co_doi_thi_tim_lai_roi_dung():
    csdl = CsdlGia(doi={"doi-xa": ("san_sang", 50_000.0), "doi-ban": ("nghi", 10.0)})

    async def kb(env, csdl):
        return await (await bat_dau(env, so_lan_tim_doi=3, cho_tim_lai_giay=120)).result()

    kq = chay(kb, csdl)
    assert kq.ket_qua == KQ_KHONG_CO_DOI and kq.so_lan_tim == 3 and kq.doi_id is None
    assert csdl.tin[INC] == "tiep_nhan"


def test_doi_bi_gianh_thi_chon_doi_ke_tiep():
    csdl = CsdlGia(bi_gianh={"doi-1"})

    async def kb(env, csdl):
        h = await bat_dau(env)
        return await cho_buoc(h, "cho_xac_nhan")

    tt = chay(kb, csdl)
    assert tt.doi_id == "doi-2" and csdl.doi_cua_tin[INC] == "doi-2"


def test_bo_qua_tin_khong_o_tiep_nhan_hoac_khong_co():
    async def kb(env, csdl):
        dang_cuu = await (await bat_dau(env)).result()
        khong_co = await (await bat_dau(env, incident_id="khong-co")).result()
        return dang_cuu, khong_co

    for kq in chay(kb, CsdlGia(tin={INC: "dang_cuu"})):
        assert kq.ket_qua == KQ_BO_QUA and kq.doi_id is None
