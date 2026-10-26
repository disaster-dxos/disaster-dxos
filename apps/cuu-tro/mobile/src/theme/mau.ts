// SPDX-License-Identifier: Apache-2.0
// Màu của app hiện trường: bộ nhận diện Team 1 (navy #12355B, cam cứu hộ #F07B1D, xanh nước #1FA2C9) và
// màu mức khẩn cấp giống web điều phối (apps/cuu-tro/web/utils/tin.ts). Đây là nơi DUY NHẤT được viết mã màu
// (ESLint chặn ở chỗ khác). Chỉ có giao diện sáng: dùng ngoài trời, nắng gắt, cần tương phản cao.

export const MAU = {
  navy: '#12355B',
  navyDam: '#0C2440',
  navyNhat: '#E8EEF5',
  cam: '#F07B1D',
  camDam: '#B85A0F',
  camNhat: '#FDF0E4',
  nuoc: '#1FA2C9',
  nuocNhat: '#E6F5FA',
  nen: '#F4F6F9',
  beMat: '#FFFFFF',
  chu: '#0F1B2D',
  chuPhu: '#475569',
  chuMo: '#64748B',
  vien: '#D5DCE5',
  trang: '#FFFFFF',
  loi: '#B42318',
  loiNhat: '#FEECEB',
  thanhCong: '#157A3D',
  thanhCongNhat: '#E7F6EC',
  canhBao: '#9A5B00',
  canhBaoNhat: '#FFF4E0',
  phuMo: 'rgba(15, 27, 45, 0.45)',
} as const;

/** Mức khẩn cấp (cùng giá trị với API /keu-cuu và web điều phối). Chữ trắng trên nền đạt tương phản AA. */
export const MAU_MUC_KHAN = {
  khan_cap: '#C81E1E',
  cao: '#B85A0F',
  trung_binh: '#13789A',
  thap: '#55606E',
} as const;
