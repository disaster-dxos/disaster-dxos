// SPDX-License-Identifier: Apache-2.0
// Cài đặt của app: địa chỉ máy chủ và ngôn ngữ. Không có dữ liệu cá nhân nên lưu thẳng AsyncStorage.
import AsyncStorage from '@react-native-async-storage/async-storage';
import { create } from 'zustand';
import { MAC_DINH } from '@/config/env';
import { khoiTaoI18n, ngonNguMay, type NgonNgu } from '@/i18n';

const KHOA_LUU = 'cuu-tro.cai-dat.v1';

interface Luu {
  gatewayUrl: string;
  keycloakUrl: string;
  ngonNgu: NgonNgu;
}

interface CaiDatState extends Luu {
  daNap: boolean;
  nap: () => Promise<void>;
  luuMayChu: (gatewayUrl: string, keycloakUrl: string) => Promise<void>;
  doiNgonNgu: (n: NgonNgu) => Promise<void>;
}

/** Bỏ khoảng trắng và dấu / cuối; chỉ nhận http(s). Sai dạng → null. */
export function chuanHoaUrl(s: string): string | null {
  const t = s.trim().replace(/\/+$/, '');
  return /^https?:\/\/[^\s/?#]+(:\d+)?(\/[^\s?#]*)?$/.test(t) ? t : null;
}

export const useCaiDatStore = create<CaiDatState>((set, get) => {
  const ghi = async () => {
    const { gatewayUrl, keycloakUrl, ngonNgu } = get();
    await AsyncStorage.setItem(KHOA_LUU, JSON.stringify({ gatewayUrl, keycloakUrl, ngonNgu } satisfies Luu));
  };
  return {
    gatewayUrl: MAC_DINH.gatewayUrl,
    keycloakUrl: MAC_DINH.keycloakUrl,
    ngonNgu: ngonNguMay(),
    daNap: false,
    nap: async () => {
      try {
        const raw = await AsyncStorage.getItem(KHOA_LUU);
        const d = raw ? (JSON.parse(raw) as Partial<Luu>) : {};
        set({
          gatewayUrl: (d.gatewayUrl && chuanHoaUrl(d.gatewayUrl)) || MAC_DINH.gatewayUrl,
          keycloakUrl: (d.keycloakUrl && chuanHoaUrl(d.keycloakUrl)) || MAC_DINH.keycloakUrl,
          ngonNgu: d.ngonNgu === 'en' || d.ngonNgu === 'vi' ? d.ngonNgu : get().ngonNgu,
        });
      } catch {
        // Hỏng dữ liệu lưu: dùng mặc định
      }
      khoiTaoI18n(get().ngonNgu);
      set({ daNap: true });
    },
    luuMayChu: async (gatewayUrl, keycloakUrl) => {
      set({ gatewayUrl, keycloakUrl });
      await ghi();
    },
    doiNgonNgu: async ngonNgu => {
      set({ ngonNgu });
      khoiTaoI18n(ngonNgu);
      await ghi();
    },
  };
});
