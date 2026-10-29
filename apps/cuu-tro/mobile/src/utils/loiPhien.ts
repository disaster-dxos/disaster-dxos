// SPDX-License-Identifier: Apache-2.0
// Phân loại lỗi khi làm mới access token (react-native-app-auth → token endpoint của Keycloak, #108).
// App dùng ngoài hiện trường, mạng chập chờn: mặc định GIỮ phiên. Chỉ xóa phiên khi Keycloak trả lời rõ ràng
// là refresh token không còn dùng được (OAuth 2.0 `invalid_grant`: hết hạn, bị thu hồi, phiên SSO đã đóng;
// `invalid_client`/`unauthorized_client`: client bị tắt hoặc đổi cấu hình). Mọi lỗi khác (mất mạng, hết giờ,
// DNS, chứng chỉ, máy chủ 5xx, thông điệp lạ) là lỗi tạm: giữ phiên, hàng đợi thử lại sau.

/** Lỗi tạm khi lấy token: chưa tới được Keycloak hoặc Keycloak lỗi. Client API coi như mất mạng (status 0). */
export class LoiTamToken extends Error {
  constructor(public nguyenNhan: unknown) {
    super('Không làm mới được token lúc này');
  }
}

// AppAuth (Android/iOS) đưa mã lỗi OAuth của máy chủ vào message hoặc userInfo; Keycloak kèm mô tả
// "Token is not active", "Session not active", "Stale token", "Offline user session not found"
const TU_CHOI = /invalid_grant|invalid_client|unauthorized_client|token is not active|session not active|stale token|session not found|offline (user )?session/i;

function chuoiLoi(e: unknown): string {
  if (e instanceof Error) {
    const them = e as Error & { code?: unknown; userInfo?: unknown };
    return [e.message, typeof them.code === 'string' ? them.code : '', JSON.stringify(them.userInfo ?? '')].join(' ');
  }
  return typeof e === 'string' ? e : JSON.stringify(e ?? '');
}

/** true: Keycloak từ chối refresh token → phải đăng nhập lại. false: lỗi tạm → giữ phiên. */
export function phienBiTuChoi(e: unknown): boolean {
  return TU_CHOI.test(chuoiLoi(e));
}
