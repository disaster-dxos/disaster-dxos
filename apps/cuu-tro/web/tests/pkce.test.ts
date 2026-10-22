// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest'
import { base64UrlEncode, createCodeChallenge, createCodeVerifier, randomString } from '~/utils/pkce'

describe('PKCE', () => {
  it('khớp vector mẫu của RFC 7636 phụ lục B', async () => {
    const verifier = 'dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk'
    expect(await createCodeChallenge(verifier)).toBe('E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM')
  })

  it('base64url không đệm, không + /', () => {
    expect(base64UrlEncode(new Uint8Array([251, 255, 191]))).toBe('-_-_')
    expect(base64UrlEncode(new Uint8Array([1]))).toBe('AQ')
  })

  it('code_verifier đúng độ dài và bộ ký tự unreserved', () => {
    const v = createCodeVerifier()
    expect(v).toHaveLength(64)
    expect(v).toMatch(/^[A-Za-z0-9\-._~]+$/)
    expect(createCodeVerifier(43)).toHaveLength(43)
    expect(createCodeVerifier(128)).toHaveLength(128)
  })

  it('từ chối độ dài ngoài 43..128', () => {
    expect(() => createCodeVerifier(42)).toThrow(RangeError)
    expect(() => createCodeVerifier(129)).toThrow(RangeError)
    expect(() => randomString(0)).toThrow(RangeError)
  })

  it('mỗi lần sinh khác nhau', () => {
    const s = new Set(Array.from({ length: 50 }, () => randomString(32)))
    expect(s.size).toBe(50)
  })
})
