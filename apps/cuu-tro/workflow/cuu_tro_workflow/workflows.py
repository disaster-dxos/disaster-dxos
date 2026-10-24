# SPDX-License-Identifier: Apache-2.0
"""Workflow Temporal của apps/cuu-tro.

PhanCongCuuHo (#29, mở rộng ở #67): nhận incident_id (bộ khởi chạy outbox tự gọi khi có tin mới,
hoặc điều phối gọi tay) → lặp tối đa so_lan_giao_toi_da lần:
  tìm đội sẵn sàng gần nhất (PostGIS), nhường đội cho tin khẩn hơn đang chờ → gán đội, tin phan_cong
  → chờ signal "nhan_nhiem_vu" / "tu_choi" trong hạn nhận theo urgency (timer của Temporal);
  từ chối hoặc quá hạn → gỡ đội, ghi lịch sử, giao đội gần nhất kế tiếp.
Đội nhận → tin dang_cuu → chờ "xac_nhan_da_cuu" (có hạn) → tin da_cuu → dong, đội trở lại san_sang.
Hết lần giao / không có đội / quá hạn xác nhận → báo điều phối (sự kiện NATS) rồi dừng.
Signal "huy" (điều phối) dừng luồng khi đội chưa nhận: gỡ đội nếu đang giao, tin về tiep_nhan.
CanhBaoVuotNguong (#87): một đợt vượt ngưỡng của một trạm (id canh-bao-<ma_tram>-<dot>), nhận sự kiện
qua signal "su_kien" (canh_bao_khoi_chay.py signal-with-start); báo đúng 1 lần cho mỗi bước canh_bao,
nguy_hiem, ve_duoi_nguong (canh_bao.quyet_dinh) bằng activity gui_canh_bao; về dưới ngưỡng thì kết thúc.
Hello: kiểm thử đường đi API → Temporal → worker.
Sơ đồ: apps/cuu-tro/README.md mục "Workflow", docs/architecture.md.
"""

import asyncio
from datetime import timedelta
from typing import Callable

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from . import canh_bao
    from .activities import HoatDong, chao
    from .canh_bao import SuKien, ThamSoCanhBao, TrangThaiCanhBao, YeuCauGui
    from .canh_bao_gui import GuiCanhBao
    from .logic import (
        BAO_HET_LAN_GIAO,
        BAO_KHONG_CO_DOI,
        BAO_QUA_HAN_XAC_NHAN,
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
        PH_NHAN,
        PH_TU_CHOI,
        BaoDieuPhoi,
        DoiUngVien,
        KetQuaGiao,
        LanGiao,
        PhanHoi,
        ThamSoPhanCong,
        TrangThaiPhanCong,
        XacNhan,
        YeuCauGan,
        YeuCauHuy,
        chon_doi_gan_nhat,
        han_nhan,
    )

SIGNAL_XAC_NHAN = "xac_nhan_da_cuu"
SIGNAL_NHAN = "nhan_nhiem_vu"
SIGNAL_TU_CHOI = "tu_choi"
SIGNAL_HUY = "huy"
QUERY_TRANG_THAI = "trang_thai"

# Bước của workflow (TrangThaiPhanCong.buoc), API dựa vào để nhận/từ chối/hủy đúng lúc
BUOC_TIM_DOI = "tim_doi"
BUOC_CHO_NHAN = "cho_nhan"
BUOC_CHO_XAC_NHAN = "cho_xac_nhan"
BUOC_XONG = "xong"

# Lỗi CSDL tạm thời: thử lại 5 lần, giãn cách tăng dần. Lỗi nghiệp vụ (non_retryable) dừng ngay.
_ACTIVITY = {
    "start_to_close_timeout": timedelta(seconds=30),
    "retry_policy": RetryPolicy(initial_interval=timedelta(seconds=1), maximum_attempts=5),
}


# Gửi thông báo (#87): Telegram/CSDL/NATS chập chờn thì thử lại giãn cách 2 s → 60 s, tối đa 10 lần
# (429 của Telegram: activity đặt next_retry_delay theo retry_after). Hết lần vẫn lỗi: ghi lịch sử, đợt
# vẫn tiếp tục (bước sau vẫn được báo).
_GUI = {
    "start_to_close_timeout": timedelta(seconds=30),
    "retry_policy": RetryPolicy(initial_interval=timedelta(seconds=2), backoff_coefficient=2.0,
                                maximum_interval=timedelta(seconds=60), maximum_attempts=10),
}


@workflow.defn(name="CanhBaoVuotNguong")
class CanhBaoVuotNguong:
    @workflow.init
    def __init__(self, ts: ThamSoCanhBao) -> None:
        self._tt = TrangThaiCanhBao(ma_tram=ts.ma_tram, dot=ts.dot, da_bao=[])
        self._hang: list[SuKien] = []

    @workflow.run
    async def run(self, ts: ThamSoCanhBao) -> TrangThaiCanhBao:
        tt = self._tt
        han = workflow.now() + timedelta(seconds=ts.han_giay)
        while True:
            con = (han - workflow.now()).total_seconds()
            try:
                await workflow.wait_condition(lambda: bool(self._hang), timeout=timedelta(seconds=max(con, 1)))
            except asyncio.TimeoutError:
                tt.ket_thuc = canh_bao.KET_THUC_HET_HAN
                return tt
            while self._hang:
                sk = self._hang.pop(0)
                buoc = canh_bao.quyet_dinh(sk, tt.da_bao)
                if buoc is None:
                    if sk.loai == canh_bao.LOAI_VE and not tt.da_bao:
                        # Đợt về dưới ngưỡng mà chưa báo bước nào (vd worker chạy sau khi đợt bắt đầu): đóng ngay
                        tt.ket_thuc = canh_bao.KET_THUC_KHONG_BAO
                        return tt
                    continue
                try:
                    await workflow.execute_activity_method(
                        GuiCanhBao.gui_canh_bao, YeuCauGui(buoc=buoc, su_kien=sk, da_bao=list(tt.da_bao)), **_GUI)
                except ActivityError as e:
                    workflow.logger.error("không gửi được thông báo %s %s: %s", tt.ma_tram, buoc, e)
                tt.da_bao.append(buoc)
                if buoc == canh_bao.BUOC_VE:
                    tt.ket_thuc = canh_bao.BUOC_VE
                    return tt

    @workflow.signal(name=canh_bao.SIGNAL_SU_KIEN)
    def su_kien(self, sk: SuKien) -> None:
        if sk.ma_tram == self._tt.ma_tram and sk.dot == self._tt.dot:
            self._hang.append(sk)

    @workflow.query(name=QUERY_TRANG_THAI)
    def trang_thai(self) -> TrangThaiCanhBao:
        return self._tt


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
        self._phan_hoi: PhanHoi | None = None
        self._huy: YeuCauHuy | None = None

    def _ghi(self, buoc: str | None, mo_ta: str) -> None:
        if buoc:
            self._tt.buoc = buoc
        self._tt.lich_su.append(f"{workflow.now().isoformat(timespec='seconds')} {mo_ta}")

    @staticmethod
    async def _cho(dieu_kien: Callable[[], bool], giay: int) -> bool:
        """Chờ điều kiện (do signal làm đúng) tối đa `giay` giây bằng timer bền của Temporal.

        True nếu điều kiện đúng, False nếu hết hạn. Không có vòng lặp sleep: worker không chạy gì
        trong lúc chờ, máy chủ test tua thời gian được.
        """
        try:
            await workflow.wait_condition(dieu_kien, timeout=timedelta(seconds=giay))
            return True
        except asyncio.TimeoutError:
            return False

    @workflow.run
    async def run(self, ts: ThamSoPhanCong) -> TrangThaiPhanCong:
        tt = self._tt
        self._ghi("doc_tin", f"khởi chạy bởi {ts.nguoi_khoi_chay or '?'}")
        tin = await workflow.execute_activity_method(HoatDong.doc_tin, ts.incident_id, **_ACTIVITY)
        if tin is None or tin.trang_thai != "tiep_nhan":
            return self._xong(KQ_BO_QUA, f"bỏ qua: tin {'không có' if tin is None else 'đang ở ' + tin.trang_thai}")
        tt.urgency = tin.urgency
        tt.han_nhan_giay = han_nhan(ts.han_nhan_giay, tin.urgency)

        # Đội đã được giao cho tin này mà từ chối/quá hạn: không giao lại trong cùng luồng
        da_giao: set[str] = set()
        while True:
            if len(tt.giao) >= ts.so_lan_giao_toi_da:
                await self._bao_dieu_phoi(ts, BAO_HET_LAN_GIAO, f"đã giao {len(tt.giao)} lần, không đội nào nhận")
                return self._xong(KQ_HET_LAN_GIAO, f"hết {ts.so_lan_giao_toi_da} lần giao, đã báo điều phối")
            doi = await self._tim_va_gan(ts, da_giao)
            if doi == KQ_KHONG_CO_DOI:
                await self._bao_dieu_phoi(ts, BAO_KHONG_CO_DOI, f"không có đội sẵn sàng trong {ts.ban_kinh_m} m")
                return self._xong(KQ_KHONG_CO_DOI, f"không có đội sẵn sàng trong {ts.ban_kinh_m} m, đã báo điều phối")
            if doi == KQ_DA_HUY:
                return self._xong(KQ_DA_HUY, f"điều phối {self._huy.nguoi} hủy khi đang tìm đội")
            if isinstance(doi, str):
                return self._xong(KQ_BO_QUA, "bỏ qua: tin không còn ở tiep_nhan (đã xử lý tay)")

            giao = tt.giao[-1]
            self._phan_hoi = None
            self._ghi(BUOC_CHO_NHAN, f"giao lần {giao.lan} cho {doi.ten} cách {doi.khoang_cach_m} m, "
                                     f"hạn nhận {giao.han_nhan_giay} giây")
            await self._cho(
                lambda: self._phan_hoi is not None or self._huy is not None or tt.xac_nhan is not None,
                giao.han_nhan_giay,
            )
            ph, huy = self._phan_hoi, self._huy
            if tt.xac_nhan is None and huy is not None and (ph is None or ph.loai != PH_NHAN):
                await self._go_doi(giao, GIAO_HUY, huy.nguoi, huy.ly_do)
                return self._xong(KQ_DA_HUY, f"điều phối {huy.nguoi} hủy, đã gỡ {giao.doi_ten}, tin về tiep_nhan")
            if tt.xac_nhan is not None or (ph is not None and ph.loai == PH_NHAN):
                nguoi = ph.nguoi if ph is not None else tt.xac_nhan.nguoi
                await workflow.execute_activity_method(
                    HoatDong.nhan_nhiem_vu,
                    self._kq_giao(giao, GIAO_DA_NHAN, nguoi, ph.ghi_chu if ph else ""),
                    **_ACTIVITY,
                )
                giao.ket_qua, giao.nguoi = GIAO_DA_NHAN, nguoi
                self._ghi(None, f"{giao.doi_ten} nhận nhiệm vụ ({nguoi}), tin dang_cuu")
                break
            if ph is not None:  # từ chối
                await self._go_doi(giao, GIAO_TU_CHOI, ph.nguoi, ph.ghi_chu)
                self._ghi("phan_cong_lai", f"{giao.doi_ten} từ chối ({ph.nguoi}), giao đội kế tiếp")
            else:
                await self._go_doi(giao, GIAO_QUA_HAN, None, "")
                self._ghi("phan_cong_lai", f"{giao.doi_ten} không nhận trong {giao.han_nhan_giay} giây, giao đội kế tiếp")
            da_giao.add(giao.doi_id)
            tt.doi_id = tt.doi_ten = tt.khoang_cach_m = None

        self._ghi(BUOC_CHO_XAC_NHAN, f"{tt.doi_ten} đang cứu, chờ xác nhận đã cứu")
        # Đội đã nhận và đang ở hiện trường: signal hủy không còn tác dụng, chỉ chờ xác nhận
        if not await self._cho(lambda: tt.xac_nhan is not None, ts.han_xac_nhan_giay):
            await self._bao_dieu_phoi(ts, BAO_QUA_HAN_XAC_NHAN, f"{tt.doi_ten} chưa xác nhận đã cứu sau {ts.han_xac_nhan_giay} giây")
            # Tin vẫn dang_cuu với đội đã nhận: điều phối liên lạc đội rồi xử lý tay
            return self._xong(KQ_QUA_HAN, f"quá hạn {ts.han_xac_nhan_giay} giây chưa xác nhận, đã báo điều phối")

        await workflow.execute_activity_method(
            HoatDong.ket_thuc, args=[ts.incident_id, tt.doi_id], **_ACTIVITY
        )
        return self._xong(KQ_DA_DONG, "đã cứu, tin đã đóng, đội trở lại sẵn sàng")

    async def _tim_va_gan(self, ts: ThamSoPhanCong, da_giao: set[str]) -> DoiUngVien | str:
        """Tìm và gán một đội cho lần giao kế tiếp. Trả đội đã gán, hoặc mã KQ_* khi dừng."""
        tt = self._tt
        lan = len(tt.giao) + 1
        han = tt.han_nhan_giay or han_nhan(ts.han_nhan_giay, tt.urgency)
        run_id = workflow.info().run_id
        # Tin khác đang tìm đội được coi là "đang chờ" trong 2 chu kỳ tìm lại (seeking_at làm mới mỗi vòng)
        cua_so = 2 * ts.cho_tim_lai_giay + 30
        so_vong = 0
        while True:
            if self._huy is not None:
                await self._dung_tim(ts)
                return KQ_DA_HUY
            so_vong += 1
            tt.so_lan_tim += 1
            self._ghi(BUOC_TIM_DOI, f"tìm đội cho lần giao {lan}, vòng {so_vong}")
            ung_vien = await workflow.execute_activity_method(
                HoatDong.tim_doi_ung_vien, args=[ts.incident_id, ts.ban_kinh_m], **_ACTIVITY
            )
            bo_qua: set[str] = set()
            while (doi := chon_doi_gan_nhat(ung_vien, ts.ban_kinh_m, frozenset(da_giao | bo_qua))) is not None:
                kq = await workflow.execute_activity_method(
                    HoatDong.gan_doi,
                    YeuCauGan(incident_id=ts.incident_id, doi_id=doi.id, ban_kinh_m=ts.ban_kinh_m,
                              cua_so_tim_giay=cua_so, workflow_run_id=run_id, lan=lan,
                              urgency=tt.urgency or "", khoang_cach_m=doi.khoang_cach_m, han_nhan_giay=han),
                    **_ACTIVITY,
                )
                if kq == GAN_DA_GAN:
                    tt.doi_id, tt.doi_ten, tt.khoang_cach_m = doi.id, doi.ten, doi.khoang_cach_m
                    tt.giao.append(LanGiao(lan=lan, doi_id=doi.id, doi_ten=doi.ten,
                                           khoang_cach_m=doi.khoang_cach_m, han_nhan_giay=han))
                    return doi
                if kq == GAN_TIN_DA_DOI:
                    await self._dung_tim(ts)
                    return KQ_BO_QUA
                if kq == GAN_NHUONG:
                    self._ghi(None, f"nhường {doi.ten} cho tin khẩn hơn đang chờ")
                bo_qua.add(doi.id)  # bị giành hoặc nhường: thử đội kế tiếp
            if so_vong >= ts.so_lan_tim_doi:
                await self._dung_tim(ts)
                return KQ_KHONG_CO_DOI
            # Timer bền chờ tìm lại; signal hủy cắt ngang
            if await self._cho(lambda: self._huy is not None, ts.cho_tim_lai_giay):
                continue  # vòng sau trả KQ_DA_HUY
            tin = await workflow.execute_activity_method(HoatDong.doc_tin, ts.incident_id, **_ACTIVITY)
            if tin is None or tin.trang_thai != "tiep_nhan":
                await self._dung_tim(ts)
                return KQ_BO_QUA

    def _kq_giao(self, giao: LanGiao, ket_qua: str, nguoi: str | None, ghi_chu: str) -> KetQuaGiao:
        return KetQuaGiao(incident_id=self._tt.incident_id, doi_id=giao.doi_id,
                          workflow_run_id=workflow.info().run_id, lan=giao.lan,
                          ket_qua=ket_qua, nguoi=nguoi, ghi_chu=ghi_chu[:500])

    async def _go_doi(self, giao: LanGiao, ket_qua: str, nguoi: str | None, ghi_chu: str) -> None:
        await workflow.execute_activity_method(
            HoatDong.go_doi, self._kq_giao(giao, ket_qua, nguoi, ghi_chu), **_ACTIVITY
        )
        giao.ket_qua, giao.nguoi = ket_qua, nguoi

    async def _dung_tim(self, ts: ThamSoPhanCong) -> None:
        await workflow.execute_activity_method(HoatDong.dung_tim, ts.incident_id, **_ACTIVITY)

    async def _bao_dieu_phoi(self, ts: ThamSoPhanCong, ly_do: str, mo_ta: str) -> None:
        """Phát sự kiện cho điều phối viên. Lỗi NATS kéo dài không làm hỏng kết quả của workflow."""
        tt = self._tt
        try:
            await workflow.execute_activity_method(
                HoatDong.bao_dieu_phoi,
                BaoDieuPhoi(incident_id=ts.incident_id, ly_do=ly_do, urgency=tt.urgency or "",
                            so_lan_giao=len(tt.giao), workflow_id=workflow.info().workflow_id, mo_ta=mo_ta),
                **_ACTIVITY,
            )
            tt.da_bao_dieu_phoi = True
            self._ghi(None, f"đã báo điều phối: {mo_ta}")
        except ActivityError as e:
            self._ghi(None, f"không gửi được sự kiện báo điều phối: {e.cause or e}")

    def _xong(self, ket_qua: str, mo_ta: str) -> TrangThaiPhanCong:
        self._tt.ket_qua = ket_qua
        self._ghi(BUOC_XONG, mo_ta)
        return self._tt

    # ---------- Signal ----------
    def _hop_le(self, doi_id: str | None, buoc: tuple[str, ...]) -> bool:
        tt = self._tt
        return tt.buoc in buoc and (doi_id is None or doi_id == tt.doi_id)

    def _phan_hoi_giao(self, ph: PhanHoi) -> None:
        if self._phan_hoi is None and self._hop_le(ph.doi_id, (BUOC_CHO_NHAN,)):
            self._phan_hoi = ph
            self._ghi(None, f"nhận signal {ph.loai} từ {ph.vai_tro} {ph.nguoi}")
        else:
            # Phản hồi muộn của đội cũ (đã phân công lại) hoặc gửi lặp: không đổi gì
            self._ghi(None, f"bỏ qua signal {ph.loai} từ {ph.nguoi} (bước {self._tt.buoc})")

    @workflow.signal(name=SIGNAL_NHAN)
    def nhan_nhiem_vu(self, ph: PhanHoi) -> None:
        ph.loai = PH_NHAN
        self._phan_hoi_giao(ph)

    @workflow.signal(name=SIGNAL_TU_CHOI)
    def tu_choi(self, ph: PhanHoi) -> None:
        ph.loai = PH_TU_CHOI
        self._phan_hoi_giao(ph)

    @workflow.signal(name=SIGNAL_HUY)
    def huy(self, yc: YeuCauHuy) -> None:
        if self._huy is None and self._tt.buoc not in (BUOC_CHO_XAC_NHAN, BUOC_XONG):
            self._huy = yc
            self._ghi(None, f"nhận yêu cầu hủy từ {yc.nguoi}")

    @workflow.signal(name=SIGNAL_XAC_NHAN)
    def xac_nhan_da_cuu(self, xn: XacNhan) -> None:
        if self._tt.xac_nhan is None and self._hop_le(xn.doi_id, (BUOC_CHO_NHAN, BUOC_CHO_XAC_NHAN)):
            self._tt.xac_nhan = xn
            self._ghi(None, f"xác nhận đã cứu bởi {xn.vai_tro} {xn.nguoi}")

    @workflow.query(name=QUERY_TRANG_THAI)
    def trang_thai(self) -> TrangThaiPhanCong:
        return self._tt
