// SPDX-License-Identifier: Apache-2.0
// Tương phản màu (#113): mọi cặp chữ/nền và viền thành phần khai báo trong theme/mau.ts (CAP_MAU) đạt ngưỡng WCAG 2.2
// theo loại; công thức độ chói tương đối của WCAG. App dùng ngoài trời nên chữ đọc chính phải đạt AAA (7:1).
import { CAP_MAU, MAU } from '@/theme/mau';
import { tyLeTuongPhan } from '@/utils/tuongPhan';

const NGUONG = { chuChinh: 7, chu: 4.5, thanhPhan: 3 } as const;

describe('tỷ lệ tương phản WCAG', () => {
  it('khớp giá trị chuẩn', () => {
    expect(tyLeTuongPhan('#000000', '#FFFFFF')).toBeCloseTo(21, 5);
    expect(tyLeTuongPhan('#FFFFFF', '#FFFFFF')).toBeCloseTo(1, 5);
    expect(tyLeTuongPhan('#777777', '#FFFFFF')).toBeCloseTo(4.48, 2);
    // Không phụ thuộc thứ tự, nhận chữ thường và dạng rút gọn
    expect(tyLeTuongPhan('#fff', '#12355b')).toBeCloseTo(tyLeTuongPhan('#12355B', '#FFFFFF'), 10);
  });

  it('chữ trắng trên cam cứu hộ không đạt AA (lý do nút cam dùng chữ tối)', () => {
    expect(tyLeTuongPhan(MAU.trang, MAU.cam)).toBeLessThan(4.5);
  });

  it('viền thẻ cũ không đủ làm viền ô nhập (lý do có vienO)', () => {
    expect(tyLeTuongPhan(MAU.vien, MAU.beMat)).toBeLessThan(3);
  });

  it.each(CAP_MAU.map(([ten, truoc, nen, loai]) => [ten, truoc, nen, loai] as const))(
    '%s (%s trên %s) đạt ngưỡng %s',
    (_ten, truoc, nen, loai) => {
      expect(tyLeTuongPhan(truoc, nen)).toBeGreaterThanOrEqual(NGUONG[loai]);
    },
  );

  it('từ chối mã màu sai', () => {
    expect(() => tyLeTuongPhan('đỏ', '#FFFFFF')).toThrow();
    expect(() => tyLeTuongPhan('rgba(0,0,0,0.5)', '#FFFFFF')).toThrow();
  });
});
