// SPDX-License-Identifier: Apache-2.0
import type { TFunction } from 'i18next';

/** "vừa xong", "5 phút trước"… theo ngôn ngữ đang dùng */
export function thoiGianTruoc(ms: number, now: number, t: TFunction): string {
  const phut = Math.max(0, Math.floor((now - ms) / 60_000));
  if (phut < 1) {
    return t('thoiGian.vuaXong');
  }
  if (phut < 60) {
    return t('thoiGian.phut', { count: phut });
  }
  const gio = Math.floor(phut / 60);
  if (gio < 24) {
    return t('thoiGian.gio', { count: gio });
  }
  return t('thoiGian.ngay', { count: Math.floor(gio / 24) });
}

/** Mã ngắn để đọc qua điện thoại: 8 ký tự đầu của UUID (giống web điều phối) */
export function maNgan(id: string): string {
  return id.slice(0, 8);
}
