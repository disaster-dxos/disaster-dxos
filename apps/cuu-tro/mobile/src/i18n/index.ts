// SPDX-License-Identifier: Apache-2.0
// i18next: tiếng Việt mặc định (người dùng là tình nguyện viên, đội cứu hộ ở xã), có tiếng Anh (cứu trợ quốc tế,
// tình nguyện viên nước ngoài). Lần đầu theo ngôn ngữ của máy nếu là en/vi, không thì vi; người dùng đổi trong
// Cài đặt (lưu ở stores/caiDatStore.ts).
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { findBestLanguageTag } from 'react-native-localize';
import { en } from './locales/en';
import { vi } from './locales/vi';
import { boQua } from '../utils/boQua';

export const NGON_NGU = ['vi', 'en'] as const;
export type NgonNgu = (typeof NGON_NGU)[number];
export const NGON_NGU_MAC_DINH: NgonNgu = 'vi';

export const TEN_NGON_NGU: Record<NgonNgu, string> = { vi: 'Tiếng Việt', en: 'English' };

export function ngonNguMay(): NgonNgu {
  const tag = findBestLanguageTag([...NGON_NGU])?.languageTag;
  return tag === 'en' ? 'en' : NGON_NGU_MAC_DINH;
}

export function khoiTaoI18n(ngonNgu: NgonNgu = NGON_NGU_MAC_DINH): typeof i18n {
  if (!i18n.isInitialized) {
    boQua(i18n.use(initReactI18next).init({
      resources: { vi: { translation: vi }, en: { translation: en } },
      lng: ngonNgu,
      fallbackLng: NGON_NGU_MAC_DINH,
      interpolation: { escapeValue: false },
      returnNull: false,
      // Tài nguyên nạp sẵn: khởi tạo đồng bộ, màn hình đầu tiên đã có chữ
      initAsync: false,
    }));
  } else if (i18n.language !== ngonNgu) {
    boQua(i18n.changeLanguage(ngonNgu));
  }
  return i18n;
}

export default i18n;
