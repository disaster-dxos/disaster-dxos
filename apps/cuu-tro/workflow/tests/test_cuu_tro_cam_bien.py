# SPDX-License-Identifier: Apache-2.0
"""Logic thuần luồng cảm biến (#30): subject, phân tích payload, mức ngưỡng, quyết định cảnh báo,
bộ giả lập và file khai báo stream."""

import json
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from cuu_tro_workflow import cam_bien as cb
from cuu_tro_workflow import gia_lap

BAY_GIO = datetime(2026, 10, 20, 1, 0, tzinfo=timezone.utc)
SUBJ = "cuu-tro.cam-bien.AL-MN-01.muc-nuoc"
STREAMS_JSON = Path(__file__).resolve().parents[2] / "nats" / "streams.json"


def payload(**ghi_de) -> bytes:
    p = {"ma_tram": "AL-MN-01", "gia_tri": 382.456, "don_vi": "cm", "thoi_diem": "2026-10-20T08:00:00+07:00"}
    p.update(ghi_de)
    return json.dumps({k: v for k, v in p.items() if v is not ...}).encode()


def test_phan_tich_hop_le():
    bt = cb.phan_tich(SUBJ, payload(), BAY_GIO)
    assert bt.ma_tram == "AL-MN-01" and bt.kind == "muc_nuoc" and bt.don_vi == "cm"
    assert bt.gia_tri == Decimal("382.46")  # làm tròn 2 chữ số như numeric(10, 2)
    assert bt.thoi_diem == BAY_GIO


def test_thoi_diem_z_va_so_nguyen():
    bt = cb.phan_tich(SUBJ, payload(gia_tri=400, thoi_diem="2026-10-20T01:00:00Z"), BAY_GIO)
    assert bt.gia_tri == Decimal("400.00") and bt.thoi_diem == BAY_GIO


def test_luong_mua_va_gio():
    bt = cb.phan_tich("cuu-tro.cam-bien.AL-LM-01.luong-mua",
                      payload(ma_tram="AL-LM-01", don_vi="mm", gia_tri=12.5), BAY_GIO)
    assert (bt.kind, bt.don_vi) == ("luong_mua", "mm")
    bt = cb.phan_tich("cuu-tro.cam-bien.G-01.gio", payload(ma_tram="G-01", don_vi="m/s", gia_tri=17), BAY_GIO)
    assert bt.kind == "gio"


@pytest.mark.parametrize("subject", [
    "khac.cam-bien.AL-MN-01.muc-nuoc",
    "cuu-tro.cam-bien.AL-MN-01",
    "cuu-tro.cam-bien.AL-MN-01.muc-nuoc.thua",
    "cuu-tro.cam-bien.al-mn-01.muc-nuoc",      # mã trạm viết thường: sai quy ước sensors.code
    "cuu-tro.cam-bien.AL-MN-01.nhiet-do",
])
def test_subject_sai(subject):
    with pytest.raises(cb.BanTinKhongHopLe):
        cb.phan_tich(subject, payload(), BAY_GIO)


@pytest.mark.parametrize("du_lieu", [
    b"khong phai json",
    b"\xff\xfe",
    b"[1, 2]",
    payload(ma_tram="AL-MN-02"),               # khác mã trạm trên topic
    payload(don_vi="m"),                       # sai đơn vị của đại lượng
    payload(don_vi=...),
    payload(gia_tri="382"),                    # chuỗi, không phải số
    payload(gia_tri=True),
    payload(gia_tri=None),
    payload(gia_tri=1e9),                      # ngoài khoảng
    payload(gia_tri=-5000),
    payload(thoi_diem="20/10/2026 08:00"),
    payload(thoi_diem="2026-10-20T08:00:00"),  # thiếu múi giờ
    payload(thoi_diem=1760918400),
    payload(thoi_diem="2026-10-20T08:10:00+07:00"),  # tương lai > 5 phút
    payload(thoi_diem="2026-10-01T08:00:00+07:00"),  # quá 7 ngày
    json.dumps({"ma_tram": "AL-MN-01", "x": "a" * 5000}).encode(),
])
def test_payload_sai(du_lieu):
    with pytest.raises(cb.BanTinKhongHopLe):
        cb.phan_tich(SUBJ, du_lieu, BAY_GIO)


def test_nan_khong_hop_le():
    with pytest.raises(cb.BanTinKhongHopLe):
        cb.phan_tich(SUBJ, b'{"ma_tram":"AL-MN-01","gia_tri":NaN,"don_vi":"cm","thoi_diem":"2026-10-20T01:00:00Z"}',
                     BAY_GIO)


def test_lech_dong_ho_nho_van_nhan():
    t = (BAY_GIO + timedelta(minutes=4)).isoformat()
    assert cb.phan_tich(SUBJ, payload(thoi_diem=t), BAY_GIO).thoi_diem > BAY_GIO


def test_kiem_tra_khop_tram():
    bt = cb.phan_tich(SUBJ, payload(), BAY_GIO)
    cb.kiem_tra_khop_tram(bt, "muc_nuoc", "cm", True)
    with pytest.raises(cb.BanTinKhongHopLe):
        cb.kiem_tra_khop_tram(bt, "luong_mua", "mm", True)
    with pytest.raises(cb.BanTinKhongHopLe):
        cb.kiem_tra_khop_tram(bt, "muc_nuoc", "cm", False)


@pytest.mark.parametrize("gia_tri,mong_doi", [
    ("349.99", "binh_thuong"), ("350", "canh_bao"), ("449.99", "canh_bao"), ("450", "nguy_hiem"), ("900", "nguy_hiem"),
])
def test_muc_canh_bao(gia_tri, mong_doi):
    assert cb.muc_canh_bao(Decimal(gia_tri), Decimal(350), Decimal(450)) == mong_doi


def test_muc_canh_bao_nguong_null():
    assert cb.muc_canh_bao(Decimal(999), None, None) == "binh_thuong"
    assert cb.muc_canh_bao(Decimal(999), Decimal(100), None) == "canh_bao"
    assert cb.muc_canh_bao(Decimal(999), None, Decimal(500)) == "nguy_hiem"


@pytest.mark.parametrize("truoc,moi,moi_nhat,mong_doi", [
    ("binh_thuong", "canh_bao", True, True),
    ("binh_thuong", "nguy_hiem", True, True),
    ("canh_bao", "nguy_hiem", True, True),
    (None, "canh_bao", True, True),           # trạm chưa có lần đo nào
    ("canh_bao", "canh_bao", True, False),    # vẫn trên ngưỡng: không dội cảnh báo
    ("nguy_hiem", "canh_bao", True, False),   # nước rút
    ("canh_bao", "binh_thuong", True, False),
    ("binh_thuong", "nguy_hiem", False, False),  # bản tin gửi bù cũ hơn lần đo cuối
])
def test_can_phat_canh_bao(truoc, moi, moi_nhat, mong_doi):
    assert cb.can_phat_canh_bao(truoc, moi, moi_nhat) is mong_doi


def test_su_kien_canh_bao():
    bt = cb.phan_tich(SUBJ, payload(gia_tri=470), BAY_GIO)
    sk = cb.su_kien_canh_bao(bt, "Cầu An Lạc", None, "nguy_hiem", Decimal(350), Decimal(450))
    assert sk["muc"] == "nguy_hiem" and sk["muc_truoc"] == "binh_thuong"
    assert sk["nguong"] == 450.0 and sk["gia_tri"] == 470.0 and sk["don_vi"] == "cm"
    json.dumps(sk)  # tuần tự hóa được
    assert cb.subject_canh_bao("AL-MN-01") == "cuu-tro.canh-bao.cam-bien.AL-MN-01"
    assert cb.ma_su_kien(bt, "nguy_hiem") == "AL-MN-01:2026-10-20T01:00:00+00:00:nguy_hiem"


def test_topic_mqtt_khop_subject():
    topic = cb.topic_mqtt("AL-MN-01", "muc_nuoc")
    assert topic == "cuu-tro/cam-bien/AL-MN-01/muc-nuoc"
    assert cb.tach_subject(topic.replace("/", ".")) == ("AL-MN-01", "muc_nuoc")


# ---------- Bộ giả lập ----------
@pytest.mark.parametrize("tram", gia_lap.TRAM_MAU, ids=lambda t: t.ma)
def test_gia_lap_binh_thuong_duoi_nguong(tram):
    rng = random.Random(1)
    for b in range(50):
        v = gia_lap.gia_tri_kich_ban(tram, "binh-thuong", b, 6, rng)
        assert 0 <= v < tram.nguong_canh_bao


@pytest.mark.parametrize("tram", gia_lap.TRAM_MAU, ids=lambda t: t.ma)
def test_gia_lap_vuot_nguong_tang_dan_roi_giu(tram):
    rng = random.Random(1)
    day = [gia_lap.gia_tri_kich_ban(tram, "vuot-nguong", b, 6, rng) for b in range(8)]
    assert day == sorted(day)
    assert day[0] == tram.muc_nen and day[-1] > tram.nguong_nguy_hiem and day[5] == day[7]


def test_gia_lap_ban_tin_qua_duoc_kiem_tra():
    rng = random.Random(1)
    for tram in gia_lap.TRAM_MAU:
        topic, p = gia_lap.ban_tin(tram, gia_lap.gia_tri_kich_ban(tram, "vuot-nguong", 6, 6, rng), BAY_GIO)
        bt = cb.phan_tich(topic.replace("/", "."), p, BAY_GIO)
        assert bt.ma_tram == tram.ma and bt.kind == tram.kind
        assert cb.muc_canh_bao(bt.gia_tri, Decimal(tram.nguong_canh_bao), Decimal(tram.nguong_nguy_hiem)) == "nguy_hiem"


def test_gia_lap_kich_ban_sai():
    with pytest.raises(ValueError):
        gia_lap.gia_tri_kich_ban(gia_lap.TRAM_MAU[0], "khong-co", 0, 6, random.Random())


# ---------- Khai báo stream ----------
def test_khai_bao_stream():
    from cuu_tro_workflow.cam_bien_consumer import doc_khai_bao

    streams, consumers = doc_khai_bao(str(STREAMS_JSON))
    ten = {s.name: s for s in streams}
    assert ten["CUU_TRO_CAM_BIEN"].subjects == [cb.TIEN_TO_CAM_BIEN + ".>"]
    assert ten["CUU_TRO_CANH_BAO"].subjects == ["cuu-tro.canh-bao.>"]
    assert cb.subject_canh_bao("X1").startswith("cuu-tro.canh-bao.")
    assert sum(s.max_bytes for s in streams) < 1024**3  # nhỏ hơn NATS_JS_MAX_FILE mặc định (1GB)
    assert all(s.duplicate_window > 0 for s in streams)  # cần cho Nats-Msg-Id chống trùng
    stream, cc = consumers[0]
    assert stream == "CUU_TRO_CAM_BIEN" and cc.durable_name == "ghi-csdl"
