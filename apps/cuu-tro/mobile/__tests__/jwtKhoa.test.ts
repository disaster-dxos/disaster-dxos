// SPDX-License-Identifier: Apache-2.0
import { giaiBase64Url, nguoiDungTuToken, vaiChinh } from '@/utils/jwt';
import { khoaHopLe, taoKhoa } from '@/utils/khoaIdempotency';

const BANG = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';

/** UTF-8 → base64url (không padding), viết tay để không phụ thuộc Buffer của Node */
function b64url(s: string): string {
  const bytes = Array.from(unescape(encodeURIComponent(s)), c => c.charCodeAt(0));
  let out = '';
  for (let i = 0; i < bytes.length; i += 3) {
    const n = (bytes[i] ?? 0) * 65536 + (bytes[i + 1] ?? 0) * 256 + (bytes[i + 2] ?? 0);
    const so = Math.ceil(((Math.min(3, bytes.length - i)) * 8) / 6);
    for (let j = 0; j < so; j++) {
      out += BANG[Math.floor(n / 64 ** (3 - j)) % 64];
    }
  }
  return out;
}

function token(payload: object): string {
  return `${b64url(JSON.stringify({ alg: 'RS256' }))}.${b64url(JSON.stringify(payload))}.chu-ky`;
}

describe('khóa idempotency', () => {
  it('UUID v4 đúng dạng, máy chủ nhận, không trùng', () => {
    const ds = Array.from({ length: 500 }, taoKhoa);
    for (const k of ds) {
      expect(k).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
      expect(khoaHopLe(k)).toBe(true);
    }
    expect(new Set(ds).size).toBe(500);
    expect(khoaHopLe('ngan')).toBe(false);
    expect(khoaHopLe('co dau cach 12345')).toBe(false);
  });
});

describe('đọc access token Keycloak', () => {
  it('sub, tên đăng nhập, họ tên có dấu, vai từ claim Hasura', () => {
    const n = nguoiDungTuToken(
      token({
        sub: '9b000000-0000-4000-8000-000000000003',
        preferred_username: 'tinhnguyen01',
        name: 'Tình nguyện Mẫu',
        'https://hasura.io/jwt/claims': { 'x-hasura-allowed-roles': ['offline_access', 'tinh-nguyen'] },
      }),
    );
    expect(n).toEqual({
      sub: '9b000000-0000-4000-8000-000000000003',
      tenDangNhap: 'tinhnguyen01',
      hoTen: 'Tình nguyện Mẫu',
      vaiTro: ['tinh-nguyen'],
    });
    expect(vaiChinh(n)).toBe('tinh-nguyen');
  });

  it('vai chính: cứu hộ > tình nguyện > điều phối; token hỏng thì lỗi', () => {
    expect(vaiChinh({ sub: '', tenDangNhap: '', hoTen: null, vaiTro: ['dieu-phoi', 'cuu-ho'] })).toBe('cuu-ho');
    expect(vaiChinh({ sub: '', tenDangNhap: '', hoTen: null, vaiTro: ['dieu-phoi'] })).toBe('dieu-phoi');
    expect(vaiChinh(null)).toBeNull();
    expect(() => nguoiDungTuToken('khong-phai-jwt')).toThrow();
    expect(giaiBase64Url(b64url('Đà Nẵng'))).toBe('Đà Nẵng');
  });
});
