// SPDX-License-Identifier: Apache-2.0
import { chuanHoaSdt, docSo, FORM_TRONG, formTuDeXuat, kiemTraKeuCuu, type FormKeuCuu } from '@/utils/kiemTra';

const HOP_LE: FormKeuCuu = {
  ...FORM_TRONG,
  sdt: '+84 935 111 222',
  moTa: '  Nước ngập tới mái, 3 người  ',
  soNguoi: '3',
  mucKhan: 'khan_cap',
  lat: 15.9512345678,
  lon: 108.2512345678,
};

describe('Poka-yoke phía app (cùng luật API /keu-cuu)', () => {
  it('chuẩn hóa SĐT như API', () => {
    expect(chuanHoaSdt('0935.111.222')).toBe('0935111222');
    expect(chuanHoaSdt('+84 935 111 222')).toBe('0935111222');
    expect(chuanHoaSdt('84935111222')).toBe('0935111222');
    expect(chuanHoaSdt('0235111222')).toBeNull();
    expect(chuanHoaSdt('093511122')).toBeNull();
  });

  it('đọc số kiểu Việt', () => {
    expect(docSo('16,07')).toBe(16.07);
    expect(docSo('3')).toBe(3);
    expect(docSo('ba')).toBeNaN();
  });

  it('form hợp lệ → body đã chuẩn hóa (tọa độ 6 chữ số, mô tả bỏ khoảng trắng, nguồn app)', () => {
    const { body, loi } = kiemTraKeuCuu({ ...HOP_LE, diaChi: ' thôn 3 ', ten: '' });
    expect(loi).toEqual([]);
    expect(body).toEqual({
      lat: 15.951235,
      lon: 108.251235,
      reporter_phone: '0935111222',
      description: 'Nước ngập tới mái, 3 người',
      urgency: 'khan_cap',
      people_count: 3,
      source: 'app',
      address_text: 'thôn 3',
    });
  });

  it('thiếu vị trí, SĐT, mô tả → lỗi theo trường (khóa i18n), không có body', () => {
    const { body, loi } = kiemTraKeuCuu(FORM_TRONG);
    expect(body).toBeNull();
    expect(loi.map(l => [l.truong, l.khoa])).toEqual([
      ['lat', 'loi.thieuViTri'],
      ['sdt', 'loi.thieuSdt'],
      ['moTa', 'loi.thieuMoTa'],
    ]);
  });

  it('SĐT sai, số người sai, quá dài, ký tự điều khiển', () => {
    const { loi } = kiemTraKeuCuu({ ...HOP_LE, sdt: '123', soNguoi: '0', moTa: 'a'.repeat(501), ten: 'x\u0001' });
    const theoTruong = Object.fromEntries(loi.map(l => [l.truong, l.khoa]));
    expect(theoTruong).toEqual({ sdt: 'loi.sdtSai', soNguoi: 'loi.soNguoiSai', moTa: 'loi.quaDai', ten: 'loi.kyTuLa' });
    expect(kiemTraKeuCuu({ ...HOP_LE, soNguoi: '2.5' }).loi[0]?.truong).toBe('soNguoi');
    expect(kiemTraKeuCuu({ ...HOP_LE, lat: 95 }).loi[0]?.khoa).toBe('loi.viTriSai');
  });

  it('đề xuất AI điền form, trường AI không thấy giữ giá trị đang có', () => {
    const f = formTuDeXuat({ ...FORM_TRONG, sdt: '0900000000', lat: 1, lon: 2 }, { people_count: 4, urgency: 'cao' });
    expect(f).toMatchObject({ sdt: '0900000000', soNguoi: '4', mucKhan: 'cao', lat: 1, lon: 2 });
  });
});
