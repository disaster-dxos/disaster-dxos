// SPDX-License-Identifier: Apache-2.0
// Gắn một lần ở App: theo dõi mạng (NetInfo), và kích hoạt gửi hàng đợi khi có mạng trở lại, khi app trở lại
// foreground, khi đăng nhập xong, và đúng lúc bản ghi tới hạn thử lại.
import NetInfo from '@react-native-community/netinfo';
import { useEffect } from 'react';
import { AppState } from 'react-native';
import { useAuthStore } from '@/stores/authStore';
import { useHangDoiStore } from '@/stores/hangDoiStore';
import { coMangTu, useMangStore } from '@/stores/mangStore';
import { hanKeTiep } from '@/utils/hangDoi';
import { boQua } from '@/utils/boQua';

export function useDongBoHangDoi(): void {
  const daDangNhap = useAuthStore(s => s.trangThai === 'da_dang_nhap');
  const coMang = useMangStore(s => s.coMang);
  const ds = useHangDoiStore(s => s.ds);
  const daNap = useHangDoiStore(s => s.daNap);

  useEffect(() => {
    boQua(useHangDoiStore.getState().nap());
    const huy = NetInfo.addEventListener(s => useMangStore.getState().datTrangThai(coMangTu(s)));
    const sub = AppState.addEventListener('change', s => {
      if (s === 'active') {
        boQua(useHangDoiStore.getState().xuLy());
      }
    });
    return () => {
      huy();
      sub.remove();
    };
  }, []);

  useEffect(() => {
    if (daNap && coMang && daDangNhap) {
      boQua(useHangDoiStore.getState().xuLy());
    }
  }, [daNap, coMang, daDangNhap]);

  // Đăng nhập lại: bản ghi đang lùi vì hết phiên được gửi ngay, không chờ hết thời gian lùi
  useEffect(() => {
    if (daNap && daDangNhap) {
      boQua(useHangDoiStore.getState().sauDangNhap());
    }
  }, [daNap, daDangNhap]);

  // Hẹn giờ đúng lúc bản ghi lỗi tạm tới hạn thử lại
  const han = hanKeTiep(ds);
  useEffect(() => {
    if (han === null || !coMang || !daDangNhap) {
      return;
    }
    const cho = Math.max(1_000, han - Date.now());
    const h = setTimeout(() => boQua(useHangDoiStore.getState().xuLy()), cho);
    return () => clearTimeout(h);
  }, [han, coMang, daDangNhap]);
}
