# SPDX-License-Identifier: Apache-2.0
"""Workflow Temporal của apps/cuu-tro.

PhanCongCuuHo: nhận incident_id → tìm đội sẵn sàng gần nhất (PostGIS) → gán đội, tin sang phan_cong
→ chờ signal "xac_nhan_da_cuu" (có hạn) → tin da_cuu → dong, đội trở lại san_sang.
Hello: kiểm thử đường đi API → Temporal → worker.
Sơ đồ: apps/cuu-tro/README.md mục "Workflow".
"""

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from .activities import HoatDong, chao
    from .logic import (
        KQ_BO_QUA,
        KQ_DA_DONG,
        KQ_KHONG_CO_DOI,
        KQ_QUA_HAN,
        ThamSoPhanCong,
        TrangThaiPhanCong,
        XacNhan,
        chon_doi_gan_nhat,
    )

SIGNAL_XAC_NHAN = "xac_nhan_da_cuu"
QUERY_TRANG_THAI = "trang_thai"

# Lỗi CSDL tạm thời: thử lại 5 lần, giãn cách tăng dần. Lỗi nghiệp vụ (non_retryable) dừng ngay.
_ACTIVITY = {
    "start_to_close_timeout": timedelta(seconds=30),
    "retry_policy": RetryPolicy(initial_interval=timedelta(seconds=1), maximum_attempts=5),
}


@workflow.defn(name="Hello")
class Hello:
    @workflow.run
    async def run(self, ten: str) -> str:
        return await workflow.execute_activity(chao, ten, **_ACTIVITY)


@workflow.defn(name="PhanCongCuuHo")
class PhanCongCuuHo:
    @workflow.init
    def __init__(self, ts: ThamSoPhanCong) -> None:
        self._tt = TrangThaiPhanCong(incident_id=ts.incident_id)

    def _ghi(self, buoc: str, mo_ta: str) -> None:
        self._tt.buoc = buoc
        self._tt.lich_su.append(f"{workflow.now().isoformat(timespec='seconds')} {mo_ta}")

    @workflow.run
    async def run(self, ts: ThamSoPhanCong) -> TrangThaiPhanCong:
        tt = self._tt
        self._ghi("doc_tin", f"khởi chạy bởi {ts.nguoi_khoi_chay or '?'}")
        tin = await workflow.execute_activity_method(HoatDong.doc_tin, ts.incident_id, **_ACTIVITY)
        if tin is None or tin.trang_thai != "tiep_nhan":
            tt.ket_qua = KQ_BO_QUA
            self._ghi("xong", f"bỏ qua: tin {'không có' if tin is None else 'đang ở ' + tin.trang_thai}")
            return tt

        bo_qua: set[str] = set()
        while True:
            tt.so_lan_tim += 1
            self._ghi("tim_doi", f"tìm đội lần {tt.so_lan_tim}")
            ung_vien = await workflow.execute_activity_method(
                HoatDong.tim_doi_ung_vien, args=[ts.incident_id, ts.ban_kinh_m], **_ACTIVITY
            )
            doi = chon_doi_gan_nhat(ung_vien, ts.ban_kinh_m, frozenset(bo_qua))
            if doi is None:
                if tt.so_lan_tim >= ts.so_lan_tim_doi:
                    tt.ket_qua = KQ_KHONG_CO_DOI
                    self._ghi("xong", f"không có đội sẵn sàng trong {ts.ban_kinh_m} m")
                    return tt
                await workflow.sleep(timedelta(seconds=ts.cho_tim_lai_giay))
                bo_qua.clear()
                continue
            if await workflow.execute_activity_method(
                HoatDong.gan_doi, args=[ts.incident_id, doi.id], **_ACTIVITY
            ):
                break
            bo_qua.add(doi.id)  # đội vừa bị gán cho tin khác

        tt.doi_id, tt.doi_ten, tt.khoang_cach_m = doi.id, doi.ten, doi.khoang_cach_m
        self._ghi("cho_xac_nhan", f"đã gán {doi.ten} cách {doi.khoang_cach_m} m, chờ xác nhận")
        try:
            await workflow.wait_condition(
                lambda: tt.xac_nhan is not None, timeout=timedelta(seconds=ts.han_xac_nhan_giay)
            )
        except asyncio.TimeoutError:
            # Khung tuần 2: chỉ ghi nhận quá hạn, tin vẫn ở phan_cong/dang_cuu với đội đã gán.
            # Tuần 3: báo điều phối (Telegram/Centrifugo) và cho phân công lại.
            tt.ket_qua = KQ_QUA_HAN
            self._ghi("xong", f"quá hạn {ts.han_xac_nhan_giay} giây chưa xác nhận")
            return tt

        await workflow.execute_activity_method(
            HoatDong.ket_thuc, args=[ts.incident_id, doi.id], **_ACTIVITY
        )
        tt.ket_qua = KQ_DA_DONG
        self._ghi("xong", "đã cứu, tin đã đóng, đội trở lại sẵn sàng")
        return tt

    @workflow.signal(name=SIGNAL_XAC_NHAN)
    def xac_nhan_da_cuu(self, xn: XacNhan) -> None:
        if self._tt.xac_nhan is None:
            self._tt.xac_nhan = xn
            self._tt.lich_su.append(
                f"{workflow.now().isoformat(timespec='seconds')} xác nhận đã cứu bởi {xn.vai_tro} {xn.nguoi}"
            )

    @workflow.query(name=QUERY_TRANG_THAI)
    def trang_thai(self) -> TrangThaiPhanCong:
        return self._tt
