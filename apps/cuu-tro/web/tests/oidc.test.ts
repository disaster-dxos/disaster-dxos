// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it, vi } from 'vitest'
import {
  buildAuthorizeUrl, buildLogoutUrl, exchangeCode, parseCallback, refreshTokens, safeReturnTo,
  type OidcConfig, type PendingLogin,
} from '~/utils/oidc'

const cfg: OidcConfig = {
  keycloakUrl: 'http://localhost:8080/',
  realm: 'disaster',
  clientId: 'dxos-web',
  redirectUri: 'http://localhost:3000/auth/callback',
}
const pending: PendingLogin = { state: 'st-1', nonce: 'no-1', verifier: 'v'.repeat(43), returnTo: '/' }

describe('URL OIDC', () => {
  it('authorize URL có PKCE S256, state, nonce và không có bí mật', () => {
    const u = new URL(buildAuthorizeUrl(cfg, { state: 'st-1', nonce: 'no-1', challenge: 'ch' }))
    expect(u.origin + u.pathname).toBe('http://localhost:8080/realms/disaster/protocol/openid-connect/auth')
    expect(Object.fromEntries(u.searchParams)).toEqual({
      client_id: 'dxos-web',
      redirect_uri: 'http://localhost:3000/auth/callback',
      response_type: 'code',
      scope: 'openid profile',
      state: 'st-1',
      nonce: 'no-1',
      code_challenge: 'ch',
      code_challenge_method: 'S256',
    })
    expect(u.search).not.toMatch(/secret/i)
  })

  it('logout URL kèm id_token_hint khi có', () => {
    const u = new URL(buildLogoutUrl(cfg, 'idt', 'http://localhost:3000/'))
    expect(u.pathname).toBe('/realms/disaster/protocol/openid-connect/logout')
    expect(u.searchParams.get('id_token_hint')).toBe('idt')
    expect(u.searchParams.get('post_logout_redirect_uri')).toBe('http://localhost:3000/')
    expect(new URL(buildLogoutUrl(cfg, undefined, '/')).searchParams.has('id_token_hint')).toBe(false)
  })
})

describe('parseCallback', () => {
  it('nhận code khi state khớp', () => {
    expect(parseCallback('?code=abc&state=st-1', pending)).toEqual({ ok: true, code: 'abc' })
  })
  it('state lệch → lỗi (chống CSRF)', () => {
    expect(parseCallback('?code=abc&state=khac', pending).ok).toBe(false)
  })
  it('không có phiên chờ → lỗi', () => {
    expect(parseCallback('?code=abc&state=st-1', null).ok).toBe(false)
  })
  it('Keycloak báo lỗi → trả mô tả lỗi', () => {
    expect(parseCallback('?error=access_denied&error_description=Bi%20tu%20choi', pending))
      .toEqual({ ok: false, error: 'Bi tu choi' })
  })
  it('thiếu code → lỗi', () => {
    expect(parseCallback('?state=st-1', pending).ok).toBe(false)
  })
})

describe('safeReturnTo', () => {
  it.each([
    ['/', '/'], ['/ban-do?x=1', '/ban-do?x=1'], [null, '/'], ['', '/'],
    ['https://evil.example', '/'], ['//evil.example', '/'], ['/\\evil.example', '/'], ['/auth/callback', '/'],
  ])('%s → %s', (vao, ra) => expect(safeReturnTo(vao)).toBe(ra))
})

describe('token endpoint', () => {
  const ok = { access_token: 'a', refresh_token: 'r', id_token: 'i', expires_in: 900, token_type: 'Bearer' }

  it('đổi code gửi code_verifier, không gửi client_secret', async () => {
    const f = vi.fn().mockResolvedValue(new Response(JSON.stringify(ok), { status: 200 }))
    await expect(exchangeCode(cfg, 'abc', pending.verifier, f)).resolves.toEqual(ok)
    const [url, init] = f.mock.calls[0]!
    expect(url).toBe('http://localhost:8080/realms/disaster/protocol/openid-connect/token')
    const body = new URLSearchParams(init.body)
    expect(Object.fromEntries(body)).toEqual({
      client_id: 'dxos-web', grant_type: 'authorization_code', code: 'abc',
      redirect_uri: cfg.redirectUri, code_verifier: pending.verifier,
    })
  })

  it('làm mới bằng refresh_token', async () => {
    const f = vi.fn().mockResolvedValue(new Response(JSON.stringify(ok), { status: 200 }))
    await refreshTokens(cfg, 'r-1', f)
    expect(new URLSearchParams(f.mock.calls[0]![1].body).get('grant_type')).toBe('refresh_token')
  })

  it('lỗi từ Keycloak → ném lỗi có mô tả', async () => {
    const f = vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: 'invalid_grant', error_description: 'Code not valid' }), { status: 400 }))
    await expect(exchangeCode(cfg, 'x', 'y', f)).rejects.toThrow('Code not valid')
    const g = vi.fn().mockResolvedValue(new Response('oops', { status: 502 }))
    await expect(exchangeCode(cfg, 'x', 'y', g)).rejects.toThrow('502')
  })
})
