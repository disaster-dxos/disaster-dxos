# SPDX-License-Identifier: Apache-2.0
"""Quét mã độc ảnh hiện trường (#111): client clamd (INSTREAM, VERSION) với máy chủ clamd giả chạy thật trên
socket TCP, đọc kết quả, và endpoint POST /tai-len/su-co/{id}/anh: tệp nhiễm bị từ chối trước mọi bước lưu (kể
cả tệp không phải ảnh: 422 chứ không 415), tệp sạch lưu scan_status sach + phiên bản bộ chữ ký, máy quét lỗi thì nhận với chua_quet
hoặc từ chối 503 khi ANH_QUET_BAT_BUOC=1. Kiểm thật với ClamAV: scripts/smoke-clamav.sh."""

import asyncio
import logging

import httpx
import pytest
from fastapi.testclient import TestClient

from cuu_tro_workflow import config, quet_ma_doc
from cuu_tro_workflow.api import app
from tests.test_cuu_tro_anh import INC_TN, HeThongGia, KhoGia, SoGia, token, xt

EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 60
DP = token("dp", "dieu-phoi")


# ---------------- Máy chủ clamd giả (giao thức thật qua TCP) ----------------
class ClamdGia:
    def __init__(self, tra_loi_loi: str | None = None, cham: float = 0.0):
        self.nhan: list[bytes] = []
        self.tra_loi_loi = tra_loi_loi
        self.cham = cham

    async def xu_ly(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        lenh = await reader.readuntil(b"\x00")
        if lenh == b"zVERSION\x00":
            writer.write(b"ClamAV 1.5.4/28165/Mon Oct 26 08:38:01 2026\x00")
        elif lenh == b"zINSTREAM\x00":
            du_lieu = b""
            while True:
                n = int.from_bytes(await reader.readexactly(4), "big")
                if n == 0:
                    break
                du_lieu += await reader.readexactly(n)
            self.nhan.append(du_lieu)
            await asyncio.sleep(self.cham)
            if self.tra_loi_loi:
                writer.write(self.tra_loi_loi.encode() + b"\x00")
            elif du_lieu.startswith(EICAR):  # như ClamAV thật: chuỗi thử EICAR chỉ có hiệu lực ở đầu tệp
                writer.write(b"stream: Eicar-Test-Signature FOUND\x00")
            else:
                writer.write(b"stream: OK\x00")
        await writer.drain()
        writer.close()


async def _voi_clamd(gia: ClamdGia, ham):
    server = await asyncio.start_server(gia.xu_ly, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        return await ham(quet_ma_doc.MayQuet("127.0.0.1", port, timeout=2))
    finally:
        server.close()
        await server.wait_closed()


def test_quet_sach_nhiem_va_phien_ban():
    gia = ClamdGia()
    du_lieu_lon = b"a" * (quet_ma_doc.KHUC * 3 + 17)

    async def ham(m):
        return await m.quet(JPEG), await m.quet(EICAR), await m.quet(du_lieu_lon)

    sach, nhiem, lon = asyncio.run(_voi_clamd(gia, ham))
    assert sach == quet_ma_doc.KetQuaQuet(True, None, "ClamAV 1.5.4/28165")
    assert nhiem == quet_ma_doc.KetQuaQuet(False, "Eicar-Test-Signature", "ClamAV 1.5.4/28165")
    assert lon.sach and gia.nhan == [JPEG, EICAR, du_lieu_lon]  # gửi nhiều khúc, ghép lại đúng nội dung


def test_clamd_bao_loi_het_gio_khong_ket_noi():
    async def ham(m):
        return await m.quet(JPEG)

    with pytest.raises(quet_ma_doc.LoiQuet, match="báo lỗi"):
        asyncio.run(_voi_clamd(ClamdGia("INSTREAM size limit exceeded. ERROR"), ham))
    with pytest.raises(quet_ma_doc.LoiQuet, match="không trả lời"):
        asyncio.run(_voi_clamd(ClamdGia(cham=5), ham))
    with pytest.raises(quet_ma_doc.LoiQuet, match="không kết nối"):
        asyncio.run(quet_ma_doc.MayQuet("127.0.0.1", 1, timeout=2).quet(JPEG))
    with pytest.raises(quet_ma_doc.LoiQuet, match="tắt"):
        asyncio.run(quet_ma_doc.MayQuet("", 3310).quet(JPEG))


@pytest.mark.parametrize("tra_loi, sach, chu_ky", [
    ("stream: OK", True, None),
    ("stream: Win.Test.EICAR_HDB-1 FOUND", False, "Win.Test.EICAR_HDB-1"),
])
def test_doc_ket_qua(tra_loi, sach, chu_ky):
    kq = quet_ma_doc.doc_ket_qua(tra_loi)
    assert (kq.sach, kq.chu_ky) == (sach, chu_ky)


def test_rut_gon_phien_ban():
    assert quet_ma_doc.rut_gon_phien_ban("ClamAV 1.5.4/28165/Mon Oct 26 08:38:01 2026") == "ClamAV 1.5.4/28165"
    assert quet_ma_doc.rut_gon_phien_ban(None) is None


# ---------------- Endpoint tải ảnh ----------------
class MayQuetGia:
    def __init__(self, loi: bool = False):
        self.loi = loi
        self.bat = True
        self.da_quet: list[bytes] = []

    async def quet(self, du_lieu):
        self.da_quet.append(du_lieu)
        if self.loi:
            raise quet_ma_doc.LoiQuet("không kết nối được clamd clamav:3310")
        if du_lieu.startswith(EICAR):
            return quet_ma_doc.KetQuaQuet(False, "Eicar-Test-Signature", "ClamAV 1.5.4/28165")
        return quet_ma_doc.KetQuaQuet(True, None, "ClamAV 1.5.4/28165")


@pytest.fixture
def ht(monkeypatch):
    monkeypatch.setenv("ANH_MAX_BYTES", "1024")
    monkeypatch.delenv("ANH_QUET_BAT_BUOC", raising=False)
    h = HeThongGia()
    st = app.state
    st.xac_thuc = xt
    st.cfg = config.load()
    st.http = httpx.AsyncClient(base_url="http://apisix:9080", transport=httpx.MockTransport(h.graphql))
    st.kho_anh, st.so_anh = KhoGia(h), SoGia(h)
    st.may_quet = MayQuetGia()
    yield h
    for k in ("http", "kho_anh", "so_anh", "cfg", "may_quet"):
        delattr(st, k)


def tai(du_lieu, ct="image/jpeg"):
    return TestClient(app).post(f"/tai-len/su-co/{INC_TN}/anh", content=du_lieu,
                                headers={"Authorization": DP, "Content-Type": ct})


def test_anh_sach_luu_ket_qua_quet(ht):
    r = tai(JPEG)
    assert r.status_code == 201
    d = r.json()
    assert (d["scan_status"], d["scan_engine"]) == ("sach", "ClamAV 1.5.4/28165") and d["scanned_at"]
    assert app.state.may_quet.da_quet == [JPEG] and len(ht.s3) == 1


def test_tep_nhiem_bi_tu_choi_truoc_moi_buoc_luu(ht, caplog):
    with caplog.at_level(logging.INFO):
        r = tai(EICAR)
    # 422 chứ không phải 415: quét chạy TRƯỚC bước kiểm magic bytes (EICAR không phải ảnh)
    assert r.status_code == 422
    assert r.json()["detail"]["ma"] == "anh_nhiem_ma_doc" and r.json()["detail"]["chu_ky"] == "Eicar-Test-Signature"
    # Không chạm S3, không có dòng CSDL; log chỉ có tên chữ ký, không có nội dung tệp
    assert ht.s3 == {} and ht.anh == {}
    assert "Eicar-Test-Signature" in caplog.text and "EICAR-STANDARD" not in caplog.text


def test_may_quet_loi_mac_dinh_van_nhan_anh_chua_quet(ht):
    app.state.may_quet = MayQuetGia(loi=True)
    r = tai(JPEG)
    assert r.status_code == 201 and r.json()["scan_status"] == "chua_quet" and r.json()["scanned_at"] is None


def test_may_quet_loi_bat_buoc_thi_503(ht, monkeypatch):
    monkeypatch.setenv("ANH_QUET_BAT_BUOC", "1")
    app.state.cfg = config.load()
    app.state.may_quet = MayQuetGia(loi=True)
    r = tai(JPEG)
    assert r.status_code == 503 and r.json()["detail"]["ma"] == "chua_quet_duoc"
    assert ht.s3 == {} and ht.anh == {}


def test_tep_khong_phai_anh_van_bi_415_sau_khi_quet_sach(ht):
    r = tai(b"<html>khong phai anh</html>", "image/jpeg")
    assert r.status_code == 415 and ht.s3 == {}


def test_cau_hinh_mac_dinh(monkeypatch):
    for k in ("CLAMAV_HOST", "CLAMAV_PORT", "ANH_QUET_BAT_BUOC", "CLAMAV_TIMEOUT_GIAY"):
        monkeypatch.delenv(k, raising=False)
    c = config.load()
    assert (c.clamav_host, c.clamav_port, c.anh_quet_bat_buoc, c.clamav_timeout_giay) == ("clamav", 3310, False, 30.0)
