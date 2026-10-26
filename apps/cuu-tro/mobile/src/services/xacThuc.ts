// SPDX-License-Identifier: Apache-2.0
// Đăng nhập Keycloak bằng OIDC Authorization Code + PKCE (react-native-app-auth, MIT): client công khai
// `dxos-mobile`, không có client secret trong app. Trang đăng nhập mở bằng trình duyệt hệ thống (Custom Tabs /
// ASWebAuthenticationSession) nên OTP của vai điều phối và chính sách mật khẩu của Keycloak áp nguyên vẹn.
import { authorize, logout, refresh, type AuthConfiguration } from 'react-native-app-auth';
import { MAC_DINH } from '@/config/env';

export interface Token {
  accessToken: string;
  refreshToken: string | null;
  idToken: string;
  /** ms epoch */
  hetHan: number;
}

export function cauHinhOidc(keycloakUrl: string): AuthConfiguration {
  return {
    issuer: `${keycloakUrl}/realms/${MAC_DINH.realm}`,
    clientId: MAC_DINH.clientId,
    redirectUrl: MAC_DINH.redirectUrl,
    // offline_access: làm việc ngoài hiện trường nhiều ngày, mất mạng lâu vẫn làm mới được token khi có mạng
    scopes: ['openid', 'profile', 'offline_access'],
    usePKCE: true,
    // Chỉ máy dev (http://localhost) mới cần; máy chủ thật dùng HTTPS
    dangerouslyAllowInsecureHttpRequests: keycloakUrl.startsWith('http://'),
    iosPrefersEphemeralSession: false,
  };
}

function hetHanMs(iso: string): number {
  const t = Date.parse(iso);
  return Number.isFinite(t) ? t : Date.now() + 5 * 60_000;
}

export async function dangNhap(keycloakUrl: string): Promise<Token> {
  const r = await authorize(cauHinhOidc(keycloakUrl));
  return { accessToken: r.accessToken, refreshToken: r.refreshToken, idToken: r.idToken, hetHan: hetHanMs(r.accessTokenExpirationDate) };
}

export async function lamMoi(keycloakUrl: string, cu: Token): Promise<Token> {
  if (!cu.refreshToken) {
    throw new Error('không có refresh token');
  }
  const r = await refresh(cauHinhOidc(keycloakUrl), { refreshToken: cu.refreshToken });
  return {
    accessToken: r.accessToken,
    refreshToken: r.refreshToken ?? cu.refreshToken,
    idToken: r.idToken || cu.idToken,
    hetHan: hetHanMs(r.accessTokenExpirationDate),
  };
}

export async function dangXuat(keycloakUrl: string, t: Token): Promise<void> {
  await logout(cauHinhOidc(keycloakUrl), { idToken: t.idToken, postLogoutRedirectUrl: MAC_DINH.redirectUrl });
}
