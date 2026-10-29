// SPDX-License-Identifier: Apache-2.0
// Hàng đợi offline với lưu trữ, mạng và máy chủ giả: mất mạng thì giữ, có mạng thì gửi theo thứ tự, gửi lại
// dùng đúng khóa idempotency, lỗi vĩnh viễn dừng lại, ảnh chờ tin, dữ liệu sống sót khi app khởi động lại.
import { luuTruKeychain, taoHangDoiStore, type PhuThuocHangDoi } from '@/stores/hangDoiStore';
import type { BanGhi, DuLieu, KetQuaGui } from '@/utils/hangDoi';

const TIN: DuLieu = {
  loai: 'keu_cuu',
  tin: { lat: 15.95, lon: 108.25, reporter_phone: '0935111222', description: 'Ngập', people_count: 2 },
};

function heThong(kq: Array<KetQuaGui | ((b: BanGhi) => KetQuaGui)> = []) {
  let luu: BanGhi[] = [];
  const goi: Array<{ khoa: string; loai: string; incidentId?: string }> = [];
  const mang = { co: true };
  const pt: PhuThuocHangDoi = {
    luuTru: {
      doc: async () => luu,
      ghi: async ds => {
        luu = ds;
      },
    },
    gui: async (b, incidentId) => {
      goi.push({ khoa: b.khoa, loai: b.duLieu.loai, incidentId });
      const k = kq.shift() ?? { ok: true, phatLai: false, maTin: `inc-${goi.length}` };
      return typeof k === 'function' ? k(b) : k;
    },
    coMang: () => mang.co,
    xoaTep: jest.fn(async () => undefined),
    now: () => 1_000,
  };
  return { store: taoHangDoiStore(pt), goi, mang, luu: () => luu, pt };
}

const cho = () => new Promise<void>(r => setTimeout(r, 0));

describe('hàng đợi offline', () => {
  it('mất mạng: bản ghi giữ trên máy, không gửi; có mạng: gửi và lưu mã tin', async () => {
    const h = heThong();
    await h.store.getState().nap();
    h.mang.co = false;
    const b = await h.store.getState().them(TIN);
    await cho();
    expect(h.goi).toEqual([]);
    expect(h.luu()).toHaveLength(1);
    expect(h.luu()[0]).toMatchObject({ id: b.id, trangThai: 'cho_gui' });
    h.mang.co = true;
    await h.store.getState().xuLy();
    expect(h.goi).toEqual([{ khoa: b.khoa, loai: 'keu_cuu', incidentId: undefined }]);
    expect(h.store.getState().ds[0]).toMatchObject({ trangThai: 'da_gui', ketQua: { maTin: 'inc-1' } });
  });

  it('lỗi mạng giữa chừng: dừng, lần sau gửi lại ĐÚNG khóa cũ (máy chủ phát lại, không tạo trùng)', async () => {
    const h = heThong([
      { ok: false, loai: 'tam', status: 0, khoa: 'loi.mang' },
      { ok: true, phatLai: true, maTin: 'inc-7' },
    ]);
    await h.store.getState().nap();
    const b = await h.store.getState().them(TIN);
    await cho();
    expect(h.store.getState().ds[0]).toMatchObject({ trangThai: 'cho_gui', soLan: 1 });
    await h.store.getState().guiLai(b.id);
    await cho();
    expect(h.goi.map(g => g.khoa)).toEqual([b.khoa, b.khoa]);
    expect(h.store.getState().ds[0]).toMatchObject({ trangThai: 'da_gui', ketQua: { phatLai: true, maTin: 'inc-7' } });
  });

  it('lỗi vĩnh viễn không chặn bản ghi sau; ảnh chờ tin rồi dùng mã tin thật', async () => {
    const h = heThong([
      { ok: false, loai: 'vinh_vien', status: 422, khoa: 'loi.duLieuSai' },
      { ok: true, phatLai: false, maTin: 'inc-2' },
      { ok: true, phatLai: false, maAnh: 'anh-1' },
    ]);
    await h.store.getState().nap();
    h.mang.co = false;
    await h.store.getState().them(TIN);
    const tin2 = await h.store.getState().them(TIN);
    await h.store.getState().them({ loai: 'anh', tuBanGhi: tin2.id, duongDan: '/a.jpg', contentType: 'image/jpeg' });
    h.mang.co = true;
    await h.store.getState().xuLy();
    expect(h.goi.map(g => [g.loai, g.incidentId])).toEqual([
      ['keu_cuu', undefined],
      ['keu_cuu', undefined],
      ['anh', 'inc-2'],
    ]);
    expect(h.store.getState().ds.map(b => b.trangThai)).toEqual(['loi', 'da_gui', 'da_gui']);
  });

  it('ảnh của tin lỗi vĩnh viễn được đánh dấu lỗi, không gửi', async () => {
    const h = heThong([{ ok: false, loai: 'vinh_vien', status: 409, khoa: 'loi.tinTrung' }]);
    await h.store.getState().nap();
    h.mang.co = false;
    const tin = await h.store.getState().them(TIN);
    await h.store.getState().them({ loai: 'anh', tuBanGhi: tin.id, duongDan: '/a.jpg', contentType: 'image/jpeg' });
    h.mang.co = true;
    await h.store.getState().xuLy();
    expect(h.goi).toHaveLength(1);
    expect(h.store.getState().ds[1]).toMatchObject({ trangThai: 'loi', loi: { khoa: 'loi.tinGocLoi' } });
  });

  it('đăng nhập lại: bản ghi đang lùi vì hết phiên được gửi ngay (#108)', async () => {
    const h = heThong([{ ok: false, loai: 'can_dang_nhap', status: 401, khoa: 'loi.hetPhien' }]);
    await h.store.getState().nap();
    const b = await h.store.getState().them(TIN);
    await cho();
    expect(h.store.getState().ds[0]).toMatchObject({ trangThai: 'cho_gui', lanThuTiep: 1_000 + 5_000 });
    await h.store.getState().xuLy();
    expect(h.goi).toHaveLength(1);
    await h.store.getState().sauDangNhap();
    await cho();
    expect(h.goi.map(g => g.khoa)).toEqual([b.khoa, b.khoa]);
    expect(h.store.getState().ds[0]).toMatchObject({ trangThai: 'da_gui' });
  });

  it('hết phiên: dừng, giữ bản ghi chờ đăng nhập', async () => {
    const h = heThong([{ ok: false, loai: 'can_dang_nhap', status: 401, khoa: 'loi.hetPhien' }]);
    await h.store.getState().nap();
    await h.store.getState().them(TIN);
    await h.store.getState().them(TIN);
    await cho();
    expect(h.goi).toHaveLength(1);
    expect(h.store.getState().ds.map(b => b.trangThai)).toEqual(['cho_gui', 'cho_gui']);
  });

  it('khởi động lại app: bản ghi đang gửi dở về chờ gửi, khóa giữ nguyên', async () => {
    const h = heThong();
    await h.store.getState().nap();
    h.mang.co = false;
    const b = await h.store.getState().them(TIN);
    await h.pt.luuTru.ghi([{ ...h.luu()[0]!, trangThai: 'dang_gui' }]);
    const moi = taoHangDoiStore(h.pt);
    await moi.getState().nap();
    expect(moi.getState().ds[0]).toMatchObject({ id: b.id, khoa: b.khoa, trangThai: 'cho_gui' });
  });

  it('xóa ảnh khỏi hàng đợi thì xóa cả tệp ảnh', async () => {
    const h = heThong();
    await h.store.getState().nap();
    h.mang.co = false;
    const a = await h.store.getState().them({ loai: 'anh', incidentId: 'inc-1', duongDan: '/a.jpg', contentType: 'image/jpeg' });
    await h.store.getState().xoa(a.id);
    expect(h.pt.xoaTep).toHaveBeenCalledWith('/a.jpg');
    expect(h.store.getState().ds).toEqual([]);
  });

  it('lưu trữ thật dùng Keychain (mã hóa), không AsyncStorage', async () => {
    const Keychain = require('react-native-keychain');
    await luuTruKeychain.ghi([]);
    expect(Keychain.setGenericPassword).toHaveBeenCalledWith(
      'hang-doi',
      '[]',
      expect.objectContaining({ service: 'org.disasterdxos.cuutro.hang-doi' }),
    );
    expect(await luuTruKeychain.doc()).toEqual([]);
  });
});
