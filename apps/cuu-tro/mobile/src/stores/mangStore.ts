// SPDX-License-Identifier: Apache-2.0
// Trạng thái mạng theo NetInfo. `coMang` = có kết nối và không bị báo là không ra được Internet (captive portal,
// Wi-Fi không có mạng). App gắn bộ nghe một lần (hooks/useDongBoHangDoi.ts).
import { create } from 'zustand';

interface MangState {
  coMang: boolean;
  datTrangThai: (coMang: boolean) => void;
}

export const useMangStore = create<MangState>(set => ({
  coMang: true,
  datTrangThai: coMang => set({ coMang }),
}));

export function coMangTu(s: { isConnected: boolean | null; isInternetReachable?: boolean | null }): boolean {
  return s.isConnected === true && s.isInternetReachable !== false;
}
