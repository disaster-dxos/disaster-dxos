// SPDX-License-Identifier: Apache-2.0
// Trạng thái đăng nhập của web điều phối. Token giữ trong sessionStorage (mất khi đóng tab, không
// chia sẻ giữa các tab); không dùng localStorage hay cookie. Token tự làm mới trước khi hết hạn.
import {
  buildAuthorizeUrl, buildLogoutUrl, exchangeCode, parseCallback, refreshTokens, safeReturnTo,
  type OidcConfig, type PendingLogin,
} from '~/utils/oidc'
import { createCodeChallenge, createCodeVerifier, randomString } from '~/utils/pkce'
import {
  canRefresh, checkNonce, isAccessValid, refreshDelay, sessionFromTokens, userFromAccessToken,
  type Session, type UserInfo,
} from '~/utils/session'

const KHOA_PHIEN = 'dxos.phien'
const KHOA_CHO = 'dxos.dang-nhap'
let henGioLamMoi: ReturnType<typeof setTimeout> | undefined

function docJson<T>(key: string): T | null {
  try {
    const v = sessionStorage.getItem(key)
    return v ? (JSON.parse(v) as T) : null
  } catch {
    return null
  }
}

export function useAuth() {
  const rc = useRuntimeConfig().public
  const session = useState<Session | null>('phien', () => null)
  const user = computed<UserInfo | null>(() => {
    if (!session.value) return null
    try {
      return userFromAccessToken(session.value.accessToken)
    } catch {
      return null
    }
  })

  const cfg = (): OidcConfig => ({
    keycloakUrl: rc.keycloakUrl as string,
    realm: rc.keycloakRealm as string,
    clientId: rc.keycloakClientId as string,
    redirectUri: `${window.location.origin}/auth/callback`,
  })

  function luu(s: Session | null) {
    session.value = s
    if (s) sessionStorage.setItem(KHOA_PHIEN, JSON.stringify(s))
    else sessionStorage.removeItem(KHOA_PHIEN)
    henLamMoi()
  }

  function henLamMoi() {
    clearTimeout(henGioLamMoi)
    const s = session.value
    if (s && canRefresh(s)) henGioLamMoi = setTimeout(() => { void lamMoi() }, refreshDelay(s))
  }

  async function lamMoi(): Promise<boolean> {
    const s = session.value
    if (!s?.refreshToken || !canRefresh(s)) return false
    try {
      luu(sessionFromTokens(await refreshTokens(cfg(), s.refreshToken)))
      return true
    } catch {
      luu(null)
      return false
    }
  }

  /** Khôi phục phiên từ sessionStorage; hết hạn thì thử làm mới. Trả true nếu đã đăng nhập. */
  async function khoiPhuc(): Promise<boolean> {
    if (isAccessValid(session.value)) return true
    const s = session.value ?? docJson<Session>(KHOA_PHIEN)
    if (!s) return false
    session.value = s
    if (isAccessValid(s)) {
      henLamMoi()
      return true
    }
    return lamMoi()
  }

  /** Tạo state, nonce, code_verifier; trả URL trang đăng nhập Keycloak (middleware chuyển hướng). */
  async function urlDangNhap(returnTo = '/'): Promise<string> {
    const pending: PendingLogin = {
      state: randomString(32),
      nonce: randomString(32),
      verifier: createCodeVerifier(),
      returnTo: safeReturnTo(returnTo),
    }
    sessionStorage.setItem(KHOA_CHO, JSON.stringify(pending))
    const challenge = await createCodeChallenge(pending.verifier)
    return buildAuthorizeUrl(cfg(), { ...pending, challenge })
  }

  async function dangNhap(returnTo = '/') {
    window.location.assign(await urlDangNhap(returnTo))
  }

  /** Xử lý /auth/callback: kiểm state, đổi code (kèm code_verifier), kiểm nonce. Trả đường quay về. */
  async function xuLyCallback(search: string): Promise<string> {
    const pending = docJson<PendingLogin>(KHOA_CHO)
    sessionStorage.removeItem(KHOA_CHO)
    const kq = parseCallback(search, pending)
    if (!kq.ok) throw new Error(kq.error)
    const tokens = await exchangeCode(cfg(), kq.code, pending!.verifier)
    if (!checkNonce(tokens.id_token, pending!.nonce)) throw new Error('id_token không mang đúng nonce. Hãy đăng nhập lại.')
    luu(sessionFromTokens(tokens))
    return pending!.returnTo
  }

  function dangXuat() {
    const idToken = session.value?.idToken
    luu(null)
    window.location.assign(buildLogoutUrl(cfg(), idToken, `${window.location.origin}/`))
  }

  /** Header Authorization cho lời gọi qua API Gateway (#60, #61) */
  function authHeader(): Record<string, string> {
    return session.value ? { Authorization: `Bearer ${session.value.accessToken}` } : {}
  }

  return { session, user, khoiPhuc, urlDangNhap, dangNhap, xuLyCallback, dangXuat, lamMoi, authHeader }
}
