// SPDX-License-Identifier: Apache-2.0
// Phiên đăng nhập phía trình duyệt: đọc claim từ JWT (không kiểm chữ ký: token lấy trực tiếp từ
// Keycloak; APISIX và Hasura mới là nơi kiểm chữ ký), tính hạn, rút thông tin hiển thị.
import type { TokenResponse } from './oidc'

export interface Session {
  accessToken: string
  refreshToken?: string
  idToken?: string
  /** Mốc hết hạn access token, mili giây epoch */
  expiresAt: number
  refreshExpiresAt?: number
}

export interface UserInfo {
  username: string
  displayName: string
  roles: string[]
  defaultRole?: string
}

export const VAI_TRO = {
  'dieu-phoi': 'Điều phối',
  'cuu-ho': 'Cứu hộ',
  'tinh-nguyen': 'Tình nguyện',
} as const

const HASURA_CLAIMS = 'https://hasura.io/jwt/claims'

export function decodeJwtPayload(token: string): Record<string, unknown> {
  const parts = token.split('.')
  if (parts.length !== 3 || !parts[1]) throw new Error('JWT không đúng định dạng')
  const b64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
  const bin = atob(b64 + '='.repeat((4 - (b64.length % 4)) % 4))
  const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0))
  return JSON.parse(new TextDecoder().decode(bytes))
}

export function sessionFromTokens(t: TokenResponse, now = Date.now()): Session {
  return {
    accessToken: t.access_token,
    refreshToken: t.refresh_token,
    idToken: t.id_token,
    expiresAt: now + t.expires_in * 1000,
    refreshExpiresAt: t.refresh_expires_in ? now + t.refresh_expires_in * 1000 : undefined,
  }
}

/** Access token còn dùng được nếu còn hạn quá `skewMs` (mặc định 30 giây). */
export function isAccessValid(s: Session | null, now = Date.now(), skewMs = 30_000): boolean {
  return !!s && s.expiresAt - skewMs > now
}

export function canRefresh(s: Session | null, now = Date.now()): boolean {
  return !!s?.refreshToken && (s.refreshExpiresAt === undefined || s.refreshExpiresAt > now)
}

/** Mili giây tới lúc nên làm mới token (trước hạn 60 giây, không âm). */
export function refreshDelay(s: Session, now = Date.now()): number {
  return Math.max(0, s.expiresAt - now - 60_000)
}

/** id_token phải mang đúng nonce đã gửi (chống phát lại token). */
export function checkNonce(idToken: string | undefined, nonce: string): boolean {
  if (!idToken) return false
  try {
    return decodeJwtPayload(idToken).nonce === nonce
  } catch {
    return false
  }
}

export function userFromAccessToken(accessToken: string): UserInfo {
  const p = decodeJwtPayload(accessToken) as {
    preferred_username?: string
    name?: string
    given_name?: string
    family_name?: string
    realm_access?: { roles?: string[] }
    [HASURA_CLAIMS]?: { 'x-hasura-allowed-roles'?: string[]; 'x-hasura-default-role'?: string }
  }
  const hasura = p[HASURA_CLAIMS] ?? {}
  const known = Object.keys(VAI_TRO)
  const roles = (hasura['x-hasura-allowed-roles'] ?? p.realm_access?.roles ?? []).filter((r) => known.includes(r))
  const username = p.preferred_username ?? ''
  const displayName = p.name || [p.given_name, p.family_name].filter(Boolean).join(' ') || username
  return { username, displayName, roles, defaultRole: hasura['x-hasura-default-role'] }
}

export function laDieuPhoi(u: UserInfo | null): boolean {
  return !!u?.roles.includes('dieu-phoi')
}
