// SPDX-License-Identifier: Apache-2.0
// Luồng OIDC Authorization Code + PKCE với Keycloak, viết thuần (không thư viện) để test được.
// Client công khai dxos-web: không có client_secret; trình duyệt tự đổi code lấy token ở token endpoint.

export interface OidcConfig {
  keycloakUrl: string
  realm: string
  clientId: string
  redirectUri: string
}

export interface TokenResponse {
  access_token: string
  refresh_token?: string
  id_token?: string
  expires_in: number
  refresh_expires_in?: number
  token_type: string
}

/** Thông tin tạm của một lần đăng nhập, giữ trong sessionStorage tới khi Keycloak gọi lại. */
export interface PendingLogin {
  state: string
  nonce: string
  verifier: string
  returnTo: string
}

export function realmBase(cfg: Pick<OidcConfig, 'keycloakUrl' | 'realm'>): string {
  return `${cfg.keycloakUrl.replace(/\/+$/, '')}/realms/${encodeURIComponent(cfg.realm)}/protocol/openid-connect`
}

export function buildAuthorizeUrl(cfg: OidcConfig, p: { state: string; nonce: string; challenge: string }): string {
  const q = new URLSearchParams({
    client_id: cfg.clientId,
    redirect_uri: cfg.redirectUri,
    response_type: 'code',
    scope: 'openid profile',
    state: p.state,
    nonce: p.nonce,
    code_challenge: p.challenge,
    code_challenge_method: 'S256',
  })
  return `${realmBase(cfg)}/auth?${q}`
}

export function buildLogoutUrl(cfg: OidcConfig, idToken: string | undefined, postLogoutRedirectUri: string): string {
  const q = new URLSearchParams({ client_id: cfg.clientId, post_logout_redirect_uri: postLogoutRedirectUri })
  if (idToken) q.set('id_token_hint', idToken)
  return `${realmBase(cfg)}/logout?${q}`
}

export type CallbackResult =
  | { ok: true; code: string }
  | { ok: false; error: string }

/** Kiểm tham số Keycloak trả về /auth/callback: lỗi, thiếu code, state không khớp (chống CSRF). */
export function parseCallback(search: string, pending: PendingLogin | null): CallbackResult {
  const q = new URLSearchParams(search)
  const err = q.get('error')
  if (err) return { ok: false, error: q.get('error_description') || err }
  if (!pending) return { ok: false, error: 'Không có phiên đăng nhập đang chờ. Hãy đăng nhập lại.' }
  if (q.get('state') !== pending.state) return { ok: false, error: 'Tham số state không khớp. Hãy đăng nhập lại.' }
  const code = q.get('code')
  if (!code) return { ok: false, error: 'Keycloak không trả mã đăng nhập.' }
  return { ok: true, code }
}

/** Chỉ cho quay về đường dẫn nội bộ (bắt đầu bằng một dấu "/"), tránh open redirect. */
export function safeReturnTo(path: string | null | undefined): string {
  if (!path || !path.startsWith('/') || path.startsWith('//') || path.startsWith('/\\')) return '/'
  if (path.startsWith('/auth/')) return '/'
  return path
}

type FetchLike = (input: string, init?: RequestInit) => Promise<Response>

async function postToken(cfg: OidcConfig, body: Record<string, string>, fetchFn: FetchLike): Promise<TokenResponse> {
  const res = await fetchFn(`${realmBase(cfg)}/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ client_id: cfg.clientId, ...body }).toString(),
  })
  if (!res.ok) {
    let msg = `Keycloak trả mã ${res.status}`
    try {
      const j = await res.json()
      if (j?.error_description || j?.error) msg = j.error_description || j.error
    } catch { /* thân phản hồi không phải JSON */ }
    throw new Error(msg)
  }
  return (await res.json()) as TokenResponse
}

export function exchangeCode(cfg: OidcConfig, code: string, verifier: string, fetchFn: FetchLike = fetch) {
  return postToken(cfg, {
    grant_type: 'authorization_code',
    code,
    redirect_uri: cfg.redirectUri,
    code_verifier: verifier,
  }, fetchFn)
}

export function refreshTokens(cfg: OidcConfig, refreshToken: string, fetchFn: FetchLike = fetch) {
  return postToken(cfg, { grant_type: 'refresh_token', refresh_token: refreshToken }, fetchFn)
}
