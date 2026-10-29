// SPDX-License-Identifier: Apache-2.0
import { phanLoaiLoi } from '@/utils/loiApi';

describe('phân loại lỗi gửi', () => {
  it.each([
    [0, 'tam', 'loi.mang'],
    [401, 'can_dang_nhap', 'loi.hetPhien'],
    [429, 'tam', 'loi.quaNhanh'],
    [502, 'tam', 'loi.mayChu'],
    [504, 'tam', 'loi.mayChu'],
    [403, 'vinh_vien', 'loi.khongQuyen'],
    [404, 'vinh_vien', 'loi.khongCo'],
    [413, 'vinh_vien', 'loi.quaLon'],
    [415, 'vinh_vien', 'loi.dinhDangAnh'],
    [418, 'vinh_vien', 'loi.khac'],
  ])('HTTP %i → %s', (status, loai, khoa) => {
    expect(phanLoaiLoi(status, null)).toMatchObject({ loai, khoa, status });
  });

  it('409 tin trùng: giữ mã tin đang mở và câu của API', () => {
    const l = phanLoaiLoi(409, { ma: 'tin_trung', thong_bao: 'Đã có tin cách 80 m', incident_id: 'inc-1' });
    expect(l).toEqual({ loai: 'vinh_vien', status: 409, khoa: 'loi.tinTrung', chiTiet: 'Đã có tin cách 80 m', maTinTrung: 'inc-1' });
  });

  it('422: câu lỗi đầu tiên theo trường của API', () => {
    const l = phanLoaiLoi(422, { ma: 'du_lieu_khong_hop_le', loi: [{ truong: 'lat', thong_bao: 'Ngoài vùng phục vụ' }] });
    expect(l).toMatchObject({ loai: 'vinh_vien', khoa: 'loi.duLieuSai', chiTiet: 'Ngoài vùng phục vụ' });
    expect(phanLoaiLoi(403, 'Cần vai trò: dieu-phoi').chiTiet).toBe('Cần vai trò: dieu-phoi');
  });
});
