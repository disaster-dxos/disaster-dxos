// SPDX-License-Identifier: Apache-2.0
// Cấu hình mặc định của app. Địa chỉ máy chủ đổi được trong app (màn Cài đặt, lưu AsyncStorage) để một bản
// build dùng được cho máy dev, máy chủ của xã hay VPS demo; mặc định trỏ về stack chạy trên máy dev:
//   - iOS Simulator dùng chung localhost với máy Mac;
//   - Android (máy ảo hoặc máy thật cắm cáp): `adb reverse tcp:8080 tcp:8080 && adb reverse tcp:9080 tcp:9080`.
// Issuer của token phải khớp KEYCLOAK_PUBLIC_URL của lõi (Hasura và API kiểm `iss`), nên app phải gọi
// Keycloak đúng địa chỉ công khai đó, không dùng 10.0.2.2.

export const MAC_DINH = {
  /** API Gateway (APISIX) của lõi: /workflow/*, /graphql */
  gatewayUrl: 'http://localhost:9080',
  /** Keycloak, đúng KEYCLOAK_PUBLIC_URL của lõi */
  keycloakUrl: 'http://localhost:8080',
  realm: 'disaster',
  /** Client công khai PKCE trong apps/cuu-tro/keycloak/realm.json */
  clientId: 'dxos-mobile',
  /** Trùng applicationId Android / bundle id iOS; khai trong realm (redirectUris) */
  redirectUrl: 'org.disasterdxos.cuutro:/oauthredirect',
  /** Kiểu nền bản đồ vector (dữ liệu OpenStreetMap), cùng nguồn với web điều phối */
  mapStyleUrl: 'https://tiles.openfreemap.org/styles/liberty',
} as const;

/** Mạng lúc bão chập chờn: chờ 15 giây rồi coi là lỗi mạng, bản ghi ở lại hàng đợi để gửi lại. */
export const THOI_HAN_MS = 15_000;

/** Tâm bản đồ khi chưa có vị trí: vùng dữ liệu mẫu Đà Nẵng – Quảng Nam, [kinh độ, vĩ độ] (giống web). */
export const TAM_MAC_DINH: [number, number] = [108.2, 15.92];
