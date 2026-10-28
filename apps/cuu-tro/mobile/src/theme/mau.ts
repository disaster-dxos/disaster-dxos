// SPDX-License-Identifier: Apache-2.0
// Màu của app hiện trường: bộ nhận diện Team 1 (navy #12355B, cam cứu hộ #F07B1D, xanh nước #1FA2C9) và
// màu mức khẩn cấp giống web điều phối (apps/cuu-tro/web/utils/tin.ts). Đây là nơi DUY NHẤT được viết mã màu
// (ESLint chặn ở chỗ khác). Chỉ có giao diện sáng: dùng ngoài trời, nắng gắt, cần tương phản cao.
// Mọi cặp chữ/nền và viền thành phần đang dùng khai báo ở CAP_MAU; __tests__/tuongPhan.test.ts kiểm tỷ lệ
// tương phản WCAG 2.2 (chữ ≥ 4,5:1, chữ chính ≥ 7:1, viền ô nhập/nút ≥ 3:1) (#113).

export const MAU = {
  navy: '#12355B',
  navyDam: '#0C2440',
  navyNhat: '#E8EEF5',
  // Cam cứu hộ chỉ làm NỀN với chữ tối (chu): chữ trắng trên cam chỉ đạt 2,78:1 (#113)
  cam: '#F07B1D',
  camDam: '#B85A0F',
  camNhat: '#FDF0E4',
  nuoc: '#1FA2C9',
  nuocNhat: '#E6F5FA',
  nen: '#F4F6F9',
  beMat: '#FFFFFF',
  chu: '#0F1B2D',
  chuPhu: '#424F63',
  chuMo: '#64748B',
  // Viền thẻ (trang trí, không cần đạt 3:1)
  vien: '#D5DCE5',
  // Viền thành phần bấm/nhập được (ô nhập, ô chọn, nút phụ): ≥ 3:1 trên nền trắng và nền xám (WCAG 1.4.11)
  vienO: '#6B7A8C',
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

type Loai = 'chu' | 'chuChinh' | 'thanhPhan';

/**
 * Cặp màu đang dùng: [tên, màu trước, màu nền, loại]. chuChinh = chữ đọc chính trên nền màn (≥ 7:1, AAA, đọc
 * ngoài nắng); chu = mọi chữ khác kể cả nhãn, lỗi, placeholder (≥ 4,5:1); thanhPhan = viền/biểu tượng của thành
 * phần bấm được (≥ 3:1). Thêm màu hoặc cặp mới ở màn nào thì thêm vào đây.
 */
export const CAP_MAU: ReadonlyArray<readonly [string, string, string, Loai]> = [
  ['chữ chính trên nền màn', MAU.chu, MAU.nen, 'chuChinh'],
  ['chữ chính trên thẻ', MAU.chu, MAU.beMat, 'chuChinh'],
  ['chữ phụ trên nền màn', MAU.chuPhu, MAU.nen, 'chuChinh'],
  ['chữ phụ trên thẻ', MAU.chuPhu, MAU.beMat, 'chuChinh'],
  ['placeholder ô nhập', MAU.chuMo, MAU.beMat, 'chu'],
  ['nút chính (chữ trắng trên navy)', MAU.trang, MAU.navy, 'chuChinh'],
  ['nút cam (chữ tối trên cam)', MAU.chu, MAU.cam, 'chu'],
  ['huy hiệu tab Hàng đợi', MAU.chu, MAU.cam, 'chu'],
  ['nút phụ (navy trên trắng)', MAU.navy, MAU.beMat, 'chuChinh'],
  ['nút nguy hiểm (đỏ trên trắng)', MAU.loi, MAU.beMat, 'chu'],
  ['tab đang chọn', MAU.navy, MAU.beMat, 'chu'],
  ['tab không chọn', MAU.chuPhu, MAU.beMat, 'chu'],
  ['lỗi trên nền màn', MAU.loi, MAU.nen, 'chu'],
  ['lỗi trên thẻ', MAU.loi, MAU.beMat, 'chu'],
  ['tóm tắt lỗi', MAU.loi, MAU.loiNhat, 'chu'],
  ['thành công trên nền màn', MAU.thanhCong, MAU.nen, 'chu'],
  ['thành công trên thẻ', MAU.thanhCong, MAU.beMat, 'chu'],
  ['báo đã lưu', MAU.chu, MAU.thanhCongNhat, 'chuChinh'],
  ['báo đề xuất AI', MAU.chu, MAU.nuocNhat, 'chuChinh'],
  ['băng mất mạng', MAU.chu, MAU.canhBaoNhat, 'chuChinh'],
  ['biểu tượng mất mạng', MAU.canhBao, MAU.canhBaoNhat, 'chu'],
  ['băng chờ gửi', MAU.chu, MAU.navyNhat, 'chuChinh'],
  ['trạng thái chờ gửi', MAU.canhBao, MAU.beMat, 'chu'],
  ['cảnh báo trên nền màn', MAU.canhBao, MAU.nen, 'chu'],
  ['ô chọn đang chọn (navy)', MAU.trang, MAU.navy, 'chu'],
  ['mức khẩn cấp: khẩn cấp', MAU.trang, MAU_MUC_KHAN.khan_cap, 'chu'],
  ['mức khẩn cấp: cao', MAU.trang, MAU_MUC_KHAN.cao, 'chu'],
  ['mức khẩn cấp: trung bình', MAU.trang, MAU_MUC_KHAN.trung_binh, 'chu'],
  ['mức khẩn cấp: thấp', MAU.trang, MAU_MUC_KHAN.thap, 'chu'],
  ['viền ô nhập/ô chọn/nút phụ trên thẻ', MAU.vienO, MAU.beMat, 'thanhPhan'],
  ['viền ô nhập/ô chọn/nút phụ trên nền màn', MAU.vienO, MAU.nen, 'thanhPhan'],
];
