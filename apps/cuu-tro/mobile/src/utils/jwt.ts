// SPDX-License-Identifier: Apache-2.0
// Đọc phần thân access token Keycloak (KHÔNG kiểm chữ ký: token lấy thẳng từ Keycloak qua PKCE; APISIX, Hasura
// và API kiểm chữ ký mỗi lời gọi). Chỉ để hiển thị người dùng và chọn giao diện theo vai.
import type { VaiTro } from '@/types/api';

const HASURA_NS = 'https://hasura.io/jwt/claims';
const VAI_HOP_LE: readonly VaiTro[] = ['dieu-phoi', 'cuu-ho', 'tinh-nguyen'];

export interface NguoiDung {
  sub: string;
  tenDangNhap: string;
  hoTen: string | null;
  vaiTro: VaiTro[];
}

/** base64url → chuỗi UTF-8 (atob có sẵn trên Hermes của React Native 0.74+ và trên Node) */
export function giaiBase64Url(s: string): string {
  const b64 = s.replace(/-/g, '+').replace(/_/g, '/');
  const nhiPhan = atob(b64 + '='.repeat((4 - (b64.length % 4)) % 4));
  // Từng byte → %XX rồi giải UTF-8 (tên người dùng tiếng Việt có dấu)
  return decodeURIComponent(Array.from(nhiPhan, (c: string) => '%' + c.charCodeAt(0).toString(16).padStart(2, '0')).join(''));
}

export function nguoiDungTuToken(token: string): NguoiDung {
  const phan = token.split('.')[1];
  if (!phan) {
    throw new Error('token không đúng dạng JWT');
  }
  const c = JSON.parse(giaiBase64Url(phan)) as Record<string, unknown>;
  const ns = (c[HASURA_NS] ?? {}) as { 'x-hasura-allowed-roles'?: unknown };
  const roles = Array.isArray(ns['x-hasura-allowed-roles']) ? ns['x-hasura-allowed-roles'] : [];
  return {
    sub: typeof c.sub === 'string' ? c.sub : '',
    tenDangNhap: typeof c.preferred_username === 'string' ? c.preferred_username : '',
    hoTen: typeof c.name === 'string' ? c.name : null,
    vaiTro: VAI_HOP_LE.filter(v => roles.includes(v)),
  };
}

/**
 * Vai dùng trong app hiện trường: cứu hộ (cập nhật vị trí đội, ảnh tin của đội) ưu tiên hơn tình nguyện viên;
 * điều phối dùng như tình nguyện viên (gửi tin, chuyển tin) vì màn điều phối nằm trên web.
 */
export function vaiChinh(n: NguoiDung | null): VaiTro | null {
  if (!n) {
    return null;
  }
  for (const v of ['cuu-ho', 'tinh-nguyen', 'dieu-phoi'] as const) {
    if (n.vaiTro.includes(v)) {
      return v;
    }
  }
  return null;
}
