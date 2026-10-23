// SPDX-License-Identifier: Apache-2.0
// PKCE (RFC 7636) cho client công khai: code_verifier ngẫu nhiên, code_challenge = S256(verifier).

const UNRESERVED = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~'

/** Base64url không đệm (RFC 4648 §5), dùng cho code_challenge. */
export function base64UrlEncode(bytes: Uint8Array): string {
  let bin = ''
  for (const b of bytes) bin += String.fromCharCode(b)
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

/** Chuỗi ngẫu nhiên từ bộ ký tự unreserved; độ dài 43..128 với code_verifier. */
export function randomString(length = 64): string {
  if (length < 1) throw new RangeError('length phải > 0')
  // 66 ký tự: lấy mẫu loại bỏ (rejection sampling) để không lệch phân bố
  const limit = 256 - (256 % UNRESERVED.length)
  let out = ''
  while (out.length < length) {
    const buf = crypto.getRandomValues(new Uint8Array(length * 2))
    for (const b of buf) {
      if (b < limit) out += UNRESERVED[b % UNRESERVED.length]
      if (out.length === length) break
    }
  }
  return out
}

export function createCodeVerifier(length = 64): string {
  if (length < 43 || length > 128) throw new RangeError('code_verifier dài 43..128 ký tự (RFC 7636)')
  return randomString(length)
}

export async function createCodeChallenge(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))
  return base64UrlEncode(new Uint8Array(digest))
}
