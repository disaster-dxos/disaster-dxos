// SPDX-License-Identifier: Apache-2.0
import {
  apKetQua,
  demTheoTrangThai,
  donDaGui,
  GIU_DA_GUI_MS,
  guiLai,
  hanKeTiep,
  khoiPhuc,
  luiMs,
  LUI_TOI_DA_MS,
  taoBanGhi,
  viecTiep,
  type BanGhi,
  type DuLieu,
} from '@/utils/hangDoi';
import { khoaHopLe } from '@/utils/khoaIdempotency';

const TIN: DuLieu = {
  loai: 'keu_cuu',
  tin: { lat: 15.95, lon: 108.25, reporter_phone: '0935111222', description: 'Ngập', urgency: 'cao', people_count: 3 },
};
const T0 = 1_000_000;

describe('tạo bản ghi', () => {
  it('mỗi bản ghi một khóa idempotency hợp lệ, khác nhau, chờ gửi ngay', () => {
    const a = taoBanGhi(TIN, T0);
    const b = taoBanGhi(TIN, T0);
    expect(khoaHopLe(a.khoa)).toBe(true);
    expect(a.khoa).not.toBe(b.khoa);
    expect(a.id).not.toBe(a.khoa);
    expect(a).toMatchObject({ trangThai: 'cho_gui', soLan: 0, taoLuc: T0, lanThuTiep: T0 });
  });
});

describe('thứ tự gửi', () => {
  it('FIFO theo lúc tạo, bỏ qua bản ghi chưa tới hạn thử lại và đã gửi/lỗi', () => {
    const a = { ...taoBanGhi(TIN, T0 + 2), lanThuTiep: T0 + 99 };
    const b = taoBanGhi(TIN, T0 + 3);
    const c = { ...taoBanGhi(TIN, T0 + 1), trangThai: 'loi' as const };
    expect(viecTiep([a, b, c], T0 + 10)).toEqual({ loai: 'gui', banGhi: b, incidentId: undefined });
    expect(viecTiep([a, b, c], T0 + 100)?.banGhi).toBe(a);
    expect(viecTiep([c], T0)).toBeNull();
  });

  it('ảnh gắn tin còn trong hàng đợi: chờ tin gửi xong rồi dùng mã tin thật', () => {
    const tin = taoBanGhi(TIN, T0);
    const anh = taoBanGhi({ loai: 'anh', tuBanGhi: tin.id, duongDan: '/a.jpg', contentType: 'image/jpeg' }, T0 + 1);
    // Tin chưa tới hạn (đang lùi) → ảnh cũng chưa gửi được
    expect(viecTiep([{ ...tin, lanThuTiep: T0 + 50 }, anh], T0 + 2)).toBeNull();
    const daGui: BanGhi = { ...tin, trangThai: 'da_gui', ketQua: { phatLai: false, maTin: 'inc-1' } };
    expect(viecTiep([daGui, anh], T0 + 2)).toEqual({ loai: 'gui', banGhi: anh, incidentId: 'inc-1' });
    expect(viecTiep([{ ...tin, trangThai: 'loi' }, anh], T0 + 2)).toEqual({ loai: 'loi_phu_thuoc', banGhi: anh });
    expect(viecTiep([anh], T0 + 2)).toEqual({ loai: 'loi_phu_thuoc', banGhi: anh });
  });

  it('ảnh của tin đã có trên máy chủ gửi thẳng', () => {
    const anh = taoBanGhi({ loai: 'anh', incidentId: 'inc-9', duongDan: '/a.jpg', contentType: 'image/jpeg' }, T0);
    expect(viecTiep([anh], T0)).toEqual({ loai: 'gui', banGhi: anh, incidentId: 'inc-9' });
  });
});

describe('áp kết quả gửi', () => {
  const b = taoBanGhi(TIN, T0);

  it('thành công: đã gửi, lưu mã tin, phát lại', () => {
    const x = apKetQua(b, { ok: true, phatLai: true, maTin: 'inc-1' }, T0 + 5);
    expect(x).toMatchObject({ trangThai: 'da_gui', guiLuc: T0 + 5, ketQua: { phatLai: true, maTin: 'inc-1' } });
    expect(x.khoa).toBe(b.khoa);
  });

  it('lỗi tạm: chờ gửi lại, lùi dần 5 s, 10 s, 20 s … tối đa 10 phút, GIỮ khóa', () => {
    const tam = { ok: false as const, loai: 'tam' as const, status: 0, khoa: 'loi.mang' };
    const x1 = apKetQua(b, tam, T0);
    const x2 = apKetQua(x1, tam, T0);
    expect([x1.lanThuTiep - T0, x2.lanThuTiep - T0]).toEqual([5_000, 10_000]);
    expect(x2).toMatchObject({ trangThai: 'cho_gui', soLan: 2, khoa: b.khoa, loi: { khoa: 'loi.mang' } });
    expect(luiMs(30)).toBe(LUI_TOI_DA_MS);
  });

  it('hết phiên: chờ đăng nhập, không tính lần lỗi', () => {
    const x = apKetQua(b, { ok: false, loai: 'can_dang_nhap', status: 401, khoa: 'loi.hetPhien' }, T0);
    expect(x).toMatchObject({ trangThai: 'cho_gui', soLan: 0, lanThuTiep: T0 });
  });

  it('lỗi vĩnh viễn (409 tin trùng): dừng, giữ mã tin đang mở để báo', () => {
    const x = apKetQua(
      b,
      { ok: false, loai: 'vinh_vien', status: 409, khoa: 'loi.tinTrung', maTinTrung: 'inc-cu' },
      T0,
    );
    expect(x).toMatchObject({ trangThai: 'loi', loi: { maTinTrung: 'inc-cu' } });
    expect(viecTiep([x], T0 + 1e9)).toBeNull();
  });
});

describe('khôi phục, gửi lại, dọn', () => {
  it('app bị tắt lúc đang gửi: về chờ gửi, gửi lại ngay với cùng khóa', () => {
    const b = { ...taoBanGhi(TIN, T0), trangThai: 'dang_gui' as const, lanThuTiep: T0 + 999 };
    const [x] = khoiPhuc([b], T0 + 5);
    expect(x).toMatchObject({ trangThai: 'cho_gui', lanThuTiep: T0 + 5, khoa: b.khoa });
  });

  it('gửi lại bản ghi lỗi giữ nguyên khóa, xóa lỗi; bản ghi đã gửi không đổi', () => {
    const loi = { ...taoBanGhi(TIN, T0), trangThai: 'loi' as const, loi: { loai: 'vinh_vien' as const, status: 422, khoa: 'x' } };
    const x = guiLai(loi, T0 + 7);
    expect(x).toMatchObject({ trangThai: 'cho_gui', lanThuTiep: T0 + 7, khoa: loi.khoa, loi: undefined });
    const da = { ...loi, trangThai: 'da_gui' as const };
    expect(guiLai(da, T0)).toBe(da);
  });

  it('bản ghi đã gửi quá 7 ngày tự xóa; chưa gửi thì giữ', () => {
    const cu = { ...taoBanGhi(TIN, T0), trangThai: 'da_gui' as const, guiLuc: T0 };
    const cho = taoBanGhi(TIN, T0);
    expect(donDaGui([cu, cho], T0 + GIU_DA_GUI_MS + 1)).toEqual([cho]);
    expect(demTheoTrangThai([cu, cho])).toEqual({ cho_gui: 1, dang_gui: 0, da_gui: 1, loi: 0 });
    expect(hanKeTiep([cu, { ...cho, lanThuTiep: T0 + 3 }])).toBe(T0 + 3);
    expect(hanKeTiep([cu])).toBeNull();
  });
});
