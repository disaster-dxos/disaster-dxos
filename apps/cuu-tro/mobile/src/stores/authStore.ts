// SPDX-License-Identifier: Apache-2.0
// Phiên đăng nhập. Token chỉ nằm trong Keychain (iOS) / Keystore (Android) qua react-native-keychain, không
// ghi AsyncStorage, không ghi log. Access token tự làm mới trước khi hết hạn; làm mới thất bại (refresh token hết
// hạn, bị thu hồi) thì về màn đăng nhập, hàng đợi offline vẫn giữ nguyên và gửi tiếp sau khi đăng nhập lại.
import * as Keychain from 'react-native-keychain';
import { create } from 'zustand';
import * as xacThuc from '@/services/xacThuc';
import type { Token } from '@/services/xacThuc';
import { nguoiDungTuToken, type NguoiDung } from '@/utils/jwt';
import { useCaiDatStore } from './caiDatStore';

const DICH_VU = 'org.disasterdxos.cuutro.phien';
/** Làm mới khi còn dưới 60 giây */
const LAM_MOI_TRUOC_MS = 60_000;

type TrangThai = 'dang_nap' | 'chua_dang_nhap' | 'da_dang_nhap';

interface AuthState {
  trangThai: TrangThai;
  token: Token | null;
  nguoiDung: NguoiDung | null;
  loi: string | null;
  khoiPhuc: () => Promise<void>;
  dangNhap: () => Promise<void>;
  /** Access token còn hạn (tự làm mới); null nếu chưa đăng nhập / làm mới thất bại */
  layToken: (batBuocLamMoi?: boolean) => Promise<string | null>;
  dangXuat: () => Promise<void>;
}

async function ghiToken(t: Token | null): Promise<void> {
  if (t) {
    await Keychain.setGenericPassword('token', JSON.stringify(t), {
      service: DICH_VU,
      accessible: Keychain.ACCESSIBLE.AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY,
    });
  } else {
    await Keychain.resetGenericPassword({ service: DICH_VU });
  }
}

let dangLamMoi: Promise<string | null> | null = null;

export const useAuthStore = create<AuthState>((set, get) => {
  const datToken = async (t: Token) => {
    await ghiToken(t);
    set({ token: t, nguoiDung: nguoiDungTuToken(t.accessToken), trangThai: 'da_dang_nhap', loi: null });
  };
  return {
    trangThai: 'dang_nap',
    token: null,
    nguoiDung: null,
    loi: null,
    khoiPhuc: async () => {
      try {
        const c = await Keychain.getGenericPassword({ service: DICH_VU });
        if (c) {
          const t = JSON.parse(c.password) as Token;
          set({ token: t, nguoiDung: nguoiDungTuToken(t.accessToken), trangThai: 'da_dang_nhap' });
          return;
        }
      } catch {
        // Dữ liệu hỏng: coi như chưa đăng nhập
      }
      set({ trangThai: 'chua_dang_nhap' });
    },
    dangNhap: async () => {
      try {
        await datToken(await xacThuc.dangNhap(useCaiDatStore.getState().keycloakUrl));
      } catch (e) {
        // Người dùng đóng trình duyệt cũng vào đây; chỉ giữ thông điệp, không ghi log
        set({ loi: e instanceof Error ? e.message : String(e) });
      }
    },
    layToken: async (batBuocLamMoi = false) => {
      const t = get().token;
      if (!t) {
        return null;
      }
      if (!batBuocLamMoi && t.hetHan - Date.now() > LAM_MOI_TRUOC_MS) {
        return t.accessToken;
      }
      // Nhiều yêu cầu cùng lúc chỉ làm mới một lần
      dangLamMoi ??= (async () => {
        try {
          const moi = await xacThuc.lamMoi(useCaiDatStore.getState().keycloakUrl, t);
          await datToken(moi);
          return moi.accessToken;
        } catch (e) {
          const chuaToiMayChu = e instanceof Error && /network|timeout|connect|offline/i.test(e.message);
          if (chuaToiMayChu) {
            // Mất mạng: giữ phiên, hàng đợi thử lại sau
            return null;
          }
          await ghiToken(null);
          set({ token: null, nguoiDung: null, trangThai: 'chua_dang_nhap' });
          return null;
        } finally {
          dangLamMoi = null;
        }
      })();
      return dangLamMoi;
    },
    dangXuat: async () => {
      const t = get().token;
      if (t) {
        try {
          await xacThuc.dangXuat(useCaiDatStore.getState().keycloakUrl, t);
        } catch {
          // Mất mạng: vẫn xóa phiên trên máy
        }
      }
      await ghiToken(null);
      set({ token: null, nguoiDung: null, trangThai: 'chua_dang_nhap' });
    },
  };
});
