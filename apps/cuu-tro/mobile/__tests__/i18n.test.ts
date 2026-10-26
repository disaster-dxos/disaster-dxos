// SPDX-License-Identifier: Apache-2.0
import i18n, { khoiTaoI18n, NGON_NGU_MAC_DINH } from '@/i18n';
import { en } from '@/i18n/locales/en';
import { vi } from '@/i18n/locales/vi';

/** Khóa phẳng, bỏ hậu tố số nhiều (_one, _other) để so hai ngôn ngữ */
function khoa(o: object, tien = ''): string[] {
  return Object.entries(o).flatMap(([k, v]) =>
    typeof v === 'object' ? khoa(v, `${tien}${k}.`) : [`${tien}${k.replace(/_(one|other)$/, '')}`],
  );
}

describe('i18n', () => {
  it('tiếng Việt mặc định', () => {
    expect(NGON_NGU_MAC_DINH).toBe('vi');
    khoiTaoI18n();
    expect(i18n.t('tab.keuCuu')).toBe('Kêu cứu');
  });

  it('tiếng Anh đủ mọi khóa của tiếng Việt và ngược lại', () => {
    expect([...new Set(khoa(en))].sort()).toEqual([...new Set(khoa(vi))].sort());
  });

  it('số nhiều đúng từng ngôn ngữ', () => {
    khoiTaoI18n('en');
    expect(i18n.t('hienTruong.soNguoi', { count: 1 })).toBe('1 person');
    expect(i18n.t('hienTruong.soNguoi', { count: 3 })).toBe('3 people');
    khoiTaoI18n('vi');
    expect(i18n.t('hienTruong.soNguoi', { count: 1 })).toBe('1 người');
  });
});
