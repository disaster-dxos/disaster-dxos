// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest'
import {
  canRefresh, checkNonce, decodeJwtPayload, isAccessValid, laDieuPhoi, refreshDelay, sessionFromTokens, userFromAccessToken,
} from '~/utils/session'

/** JWT giả (chữ ký không hợp lệ, chỉ để đọc claim) */
function jwt(payload: object): string {
  const b64 = (o: object) => Buffer.from(JSON.stringify(o)).toString('base64url')
  return `${b64({ alg: 'RS256', typ: 'JWT' })}.${b64(payload)}.chu-ky-gia`
}

describe('JWT và người dùng', () => {
  it('đọc payload có ký tự tiếng Việt', () => {
    expect(decodeJwtPayload(jwt({ name: 'Điều phối Mẫu' })).name).toBe('Điều phối Mẫu')
  })
  it('JWT hỏng → ném lỗi', () => {
    expect(() => decodeJwtPayload('abc')).toThrow()
  })
  it('lấy vai trò từ claim Hasura, bỏ vai trò lạ', () => {
    const u = userFromAccessToken(jwt({
      preferred_username: 'dieuphoi01',
      given_name: 'Điều phối', family_name: 'Mẫu',
      'https://hasura.io/jwt/claims': { 'x-hasura-allowed-roles': ['dieu-phoi', 'offline_access'], 'x-hasura-default-role': 'dieu-phoi' },
    }))
    expect(u).toEqual({ username: 'dieuphoi01', displayName: 'Điều phối Mẫu', roles: ['dieu-phoi'], defaultRole: 'dieu-phoi' })
    expect(laDieuPhoi(u)).toBe(true)
  })
  it('không có claim Hasura → dùng realm_access', () => {
    const u = userFromAccessToken(jwt({ preferred_username: 'cuuho01', realm_access: { roles: ['cuu-ho', 'default-roles-disaster'] } }))
    expect(u.roles).toEqual(['cuu-ho'])
    expect(u.displayName).toBe('cuuho01')
    expect(laDieuPhoi(u)).toBe(false)
    expect(laDieuPhoi(null)).toBe(false)
  })
})

describe('hạn token', () => {
  const now = 1_000_000
  const s = sessionFromTokens({ access_token: 'a', refresh_token: 'r', expires_in: 900, refresh_expires_in: 1800, token_type: 'Bearer' }, now)

  it('tính mốc hết hạn', () => {
    expect(s.expiresAt).toBe(now + 900_000)
    expect(s.refreshExpiresAt).toBe(now + 1_800_000)
  })
  it('còn hạn / sắp hết hạn', () => {
    expect(isAccessValid(s, now)).toBe(true)
    expect(isAccessValid(s, now + 880_000)).toBe(false)
    expect(isAccessValid(null, now)).toBe(false)
  })
  it('làm mới trước hạn 60 giây', () => {
    expect(refreshDelay(s, now)).toBe(840_000)
    expect(refreshDelay(s, now + 899_000)).toBe(0)
  })
  it('refresh token hết hạn thì không làm mới được', () => {
    expect(canRefresh(s, now)).toBe(true)
    expect(canRefresh(s, now + 1_800_001)).toBe(false)
    expect(canRefresh({ ...s, refreshToken: undefined }, now)).toBe(false)
  })
  it('kiểm nonce trong id_token', () => {
    expect(checkNonce(jwt({ nonce: 'n1' }), 'n1')).toBe(true)
    expect(checkNonce(jwt({ nonce: 'n2' }), 'n1')).toBe(false)
    expect(checkNonce(undefined, 'n1')).toBe(false)
    expect(checkNonce('hong', 'n1')).toBe(false)
  })
})
