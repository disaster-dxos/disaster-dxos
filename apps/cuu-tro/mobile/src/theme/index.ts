// SPDX-License-Identifier: Apache-2.0
import { StyleSheet } from 'react-native';
import { BO_GOC, CO_CHU, DO_DAM, KHOANG } from './kich-thuoc';
import { MAU } from './mau';

export { MAU, MAU_MUC_KHAN } from './mau';
export { BO_GOC, CO_CHU, DO_DAM, KHOANG, VUNG_CHAM } from './kich-thuoc';

/** Kiểu chữ dùng chung (font hệ thống: có đủ dấu tiếng Việt, không phải tải font). */
export const CHU = StyleSheet.create({
  tieuDe: { fontSize: CO_CHU.tieuDe, fontWeight: DO_DAM.dam, color: MAU.chu },
  muc: { fontSize: CO_CHU.lon, fontWeight: DO_DAM.dam, color: MAU.chu },
  nhan: { fontSize: CO_CHU.thuong, fontWeight: DO_DAM.vua, color: MAU.chu },
  thuong: { fontSize: CO_CHU.thuong, color: MAU.chu, lineHeight: 24 },
  phu: { fontSize: CO_CHU.nho, color: MAU.chuPhu, lineHeight: 20 },
});

/** Thẻ: viền 1 px, không đổ bóng (đọc rõ dưới nắng, nhẹ cho máy yếu). */
export const THE = StyleSheet.create({
  coBan: {
    backgroundColor: MAU.beMat,
    borderColor: MAU.vien,
    borderWidth: 1,
    borderRadius: BO_GOC.vua,
    padding: KHOANG.lg,
  },
});
