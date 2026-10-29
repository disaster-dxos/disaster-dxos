// SPDX-License-Identifier: Apache-2.0
// Hàng đợi offline (logic: utils/hangDoi.ts). Lưu MÃ HÓA trong Keychain/Keystore (react-native-keychain): bản ghi
// có SĐT, tên người cần cứu, vị trí; không ghi AsyncStorage dạng rõ. Ảnh nằm ở thư mục riêng của app, hàng đợi
// chỉ giữ đường dẫn. Bộ xử lý gửi lần lượt từng bản ghi khi có mạng và đã đăng nhập; App gọi `xuLy()` khi có
// mạng trở lại, khi app trở lại foreground, và theo hẹn giờ thử lại (hooks/useDongBoHangDoi.ts).
import * as Keychain from 'react-native-keychain';
import { create, type StoreApi, type UseBoundStore } from 'zustand';
import * as anh from '@/services/anhCucBo';
import { guiBanGhi } from '@/services/guiBanGhi';
import {
  apKetQua,
  donDaGui,
  guiLai as guiLaiBanGhi,
  khoiPhuc,
  sauDangNhap as ganLaiSauDangNhap,
  taoBanGhi,
  viecTiep,
  type BanGhi,
  type DuLieu,
  type KetQuaGui,
} from '@/utils/hangDoi';
import { useMangStore } from './mangStore';
import { boQua } from '@/utils/boQua';

const DICH_VU = 'org.disasterdxos.cuutro.hang-doi';

export interface LuuTru {
  doc: () => Promise<BanGhi[]>;
  ghi: (ds: BanGhi[]) => Promise<void>;
}

export interface PhuThuocHangDoi {
  luuTru: LuuTru;
  gui: (b: BanGhi, incidentId: string | undefined) => Promise<KetQuaGui>;
  coMang: () => boolean;
  xoaTep: (duongDan: string) => Promise<void>;
  now: () => number;
}

export interface HangDoiState {
  ds: BanGhi[];
  daNap: boolean;
  dangXuLy: boolean;
  nap: () => Promise<void>;
  /** Thêm bản ghi (sinh khóa idempotency) và gửi ngay nếu có mạng; trả bản ghi đã thêm */
  them: (duLieu: DuLieu) => Promise<BanGhi>;
  guiLai: (id: string) => Promise<void>;
  /** Vừa đăng nhập: bản ghi chờ vì hết phiên được gửi ngay */
  sauDangNhap: () => Promise<void>;
  xoa: (id: string) => Promise<void>;
  /** Gửi lần lượt mọi bản ghi tới hạn; dừng khi mất mạng / chưa đăng nhập / hết việc */
  xuLy: () => Promise<void>;
}

export const luuTruKeychain: LuuTru = {
  doc: async () => {
    const c = await Keychain.getGenericPassword({ service: DICH_VU });
    if (!c) {
      return [];
    }
    const d = JSON.parse(c.password) as unknown;
    return Array.isArray(d) ? (d as BanGhi[]) : [];
  },
  ghi: async ds => {
    await Keychain.setGenericPassword('hang-doi', JSON.stringify(ds), {
      service: DICH_VU,
      accessible: Keychain.ACCESSIBLE.AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY,
    });
  },
};

export function taoHangDoiStore(pt: PhuThuocHangDoi): UseBoundStore<StoreApi<HangDoiState>> {
  // Ghi tuần tự: hai thao tác gần nhau không ghi đè lẫn nhau
  let hangGhi: Promise<void> = Promise.resolve();
  return create<HangDoiState>((set, get) => {
    const capNhat = (f: (ds: BanGhi[]) => BanGhi[]) => {
      set({ ds: f(get().ds) });
      const banChup = get().ds;
      hangGhi = hangGhi.then(() => pt.luuTru.ghi(banChup)).catch(() => undefined);
      return hangGhi;
    };
    const thay = (b: BanGhi) => capNhat(ds => ds.map(x => (x.id === b.id ? b : x)));

    return {
      ds: [],
      daNap: false,
      dangXuLy: false,
      nap: async () => {
        let ds: BanGhi[] = [];
        try {
          ds = await pt.luuTru.doc();
        } catch {
          // Không đọc được (máy đổi khóa bảo mật): bắt đầu hàng đợi trống
        }
        set({ ds: donDaGui(khoiPhuc(ds, pt.now()), pt.now()), daNap: true });
      },
      them: async duLieu => {
        const b = taoBanGhi(duLieu, pt.now());
        await capNhat(ds => [...ds, b]);
        boQua(get().xuLy());
        return b;
      },
      guiLai: async id => {
        const b = get().ds.find(x => x.id === id);
        if (b) {
          await thay(guiLaiBanGhi(b, pt.now()));
          boQua(get().xuLy());
        }
      },
      sauDangNhap: async () => {
        await capNhat(ds => ganLaiSauDangNhap(ds, pt.now()));
        boQua(get().xuLy());
      },
      xoa: async id => {
        const b = get().ds.find(x => x.id === id);
        if (!b || b.trangThai === 'dang_gui') {
          return;
        }
        if (b.duLieu.loai === 'anh') {
          await pt.xoaTep(b.duLieu.duongDan);
        }
        await capNhat(ds => ds.filter(x => x.id !== id));
      },
      xuLy: async () => {
        if (get().dangXuLy || !get().daNap) {
          return;
        }
        set({ dangXuLy: true });
        try {
          while (pt.coMang()) {
            const viec = viecTiep(get().ds, pt.now());
            if (!viec) {
              break;
            }
            if (viec.loai === 'loi_phu_thuoc') {
              await thay(apKetQua(viec.banGhi, { ok: false, loai: 'vinh_vien', status: 0, khoa: 'loi.tinGocLoi' }, pt.now()));
              continue;
            }
            await thay({ ...viec.banGhi, trangThai: 'dang_gui' });
            const kq = await pt.gui(viec.banGhi, viec.incidentId);
            await thay(apKetQua({ ...viec.banGhi, trangThai: 'dang_gui' }, kq, pt.now()));
            if (!kq.ok && kq.loai !== 'vinh_vien') {
              // Mất mạng / máy chủ lỗi / hết phiên: dừng, chờ lần kích hoạt sau
              break;
            }
          }
        } finally {
          set({ dangXuLy: false });
        }
      },
    };
  });
}

export const useHangDoiStore = taoHangDoiStore({
  luuTru: luuTruKeychain,
  gui: (b, incidentId) => guiBanGhi(b, incidentId),
  coMang: () => useMangStore.getState().coMang,
  xoaTep: anh.xoaTep,
  now: () => Date.now(),
});
