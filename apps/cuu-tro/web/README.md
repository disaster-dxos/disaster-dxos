<!-- SPDX-License-Identifier: Apache-2.0 -->
# Web điều phối cứu trợ (`apps/cuu-tro/web`)

Ứng dụng Tầng 2 cho người điều phối của xã: bản đồ lớn + danh sách tin kêu cứu bên cạnh. Nuxt 3 + TypeScript + Tailwind CSS 4, bản đồ MapLibre GL JS. Chạy thuần phía trình duyệt (`ssr: false`), không có bí mật nào trong mã web.

![Web điều phối: bản đồ và danh sách tin kêu cứu (dữ liệu giả)](../../../docs/images/web-dieu-phoi.png)

> Trạng thái (#59): khung web, đăng nhập Keycloak, bố cục, logo. Danh sách và bản đồ đang dùng **dữ liệu giả** (`utils/tin-gia.ts`). Việc tiếp theo: #60 (subscription GraphQL), #61 (phân công), #62 (trạm đo), #63 (trang minh bạch), #64 (đưa web vào compose + smoke: đã có, xem mục Chạy).

## Đăng nhập: OIDC Authorization Code + PKCE

| Bước | Ở đâu |
|---|---|
| 1. Chưa có phiên → sinh `state`, `nonce`, `code_verifier` (64 ký tự ngẫu nhiên), `code_challenge = BASE64URL(SHA-256(verifier))`, lưu tạm trong `sessionStorage` rồi chuyển sang Keycloak | `middleware/auth.global.ts`, `composables/useAuth.ts`, `utils/pkce.ts` |
| 2. Keycloak realm `disaster`, client công khai `dxos-web` (`pkce.code.challenge.method = S256`, `apps/cuu-tro/keycloak/realm.json`). Vai `dieu-phoi` phải nhập OTP (luồng `browser-otp-dieu-phoi`, #13) | Keycloak |
| 3. `/auth/callback`: kiểm `state` (chống CSRF), đổi `code` + `code_verifier` lấy token ở token endpoint (không có `client_secret`), kiểm `nonce` trong `id_token` | `pages/auth/callback.vue`, `utils/oidc.ts` |
| 4. Token giữ trong `sessionStorage` (mất khi đóng tab), tự làm mới bằng `refresh_token` 60 giây trước khi hết hạn; đăng xuất gọi `end_session` của Keycloak | `utils/session.ts` |

Web không kiểm chữ ký JWT: token lấy trực tiếp từ Keycloak, còn APISIX (và Hasura) kiểm chữ ký mỗi lời gọi API. Mọi lời gọi lõi đi qua API Gateway (`NUXT_PUBLIC_GATEWAY_URL`, mặc định `http://localhost:9080`) kèm `Authorization: Bearer …` (`useAuth().authHeader()`); riêng trang đăng nhập/đăng xuất là của Keycloak (`NUXT_PUBLIC_KEYCLOAK_URL`). Trang công khai không cần đăng nhập: `/auth/*`, `/minh-bach*` (#63).

## Bản đồ nền

Kiểu vector OpenFreeMap `liberty` (dữ liệu © những người đóng góp OpenStreetMap, ODbL), nhãn đổi sang tên tiếng Việt (`name:vi`) và thêm nhãn Quần đảo Hoàng Sa, Trường Sa (Việt Nam); không tải được thì dùng ô ảnh OpenStreetMap. Đổi nguồn bằng `NUXT_PUBLIC_MAP_STYLE_URL`. Giấy phép: `DEPENDENCIES.md`.

## Chạy

**Trong stack (#64):** `make up` ở gốc repo build image từ `Dockerfile` (Node build → Nitro node server, user không phải root) và chạy dịch vụ `cuu-tro-web`, mở qua APISIX tại **http://localhost:9080/** (`GATEWAY_PUBLIC_URL`). Không mở cổng riêng ra host. Kiểm: `bash scripts/smoke-web.sh` (cũng trong `make smoke`).

Vì sao Nitro node server mà không phải trang tĩnh: với `ssr: false` Nitro vẫn chèn `runtimeConfig` (URL Keycloak, gateway lấy từ `NUXT_PUBLIC_*` lúc chạy) vào trang và đặt header bảo mật (`server/plugins/bao-mat.ts`: CSP có hash của script inline, `frame-ancestors 'none'`, `X-Frame-Options`, `nosniff`). Một image dùng cho mọi địa chỉ, không build lại.

**Phát triển:** cần Node.js ≥ 22.12. Lõi (`make up` ở gốc repo) phải chạy để có Keycloak ở `http://localhost:8080`; client `dxos-web` chấp nhận `redirect_uri` `http://localhost:3000/*` (dev) và `${GATEWAY_PUBLIC_URL}/*` (qua gateway).

```bash
cd apps/cuu-tro/web
npm ci
npm run dev                         # http://localhost:3000, đăng nhập dieuphoi01 (mật khẩu KC_DEMO_USER_PASSWORD trong .env, có OTP)
npm run build && node .output/server/index.mjs   # bản build, cổng PORT (mặc định 3000)
```

Biến môi trường `NUXT_PUBLIC_*`: xem `.env.example` ở gốc repo (mục "Web điều phối").

## Kiểm thử

```bash
npm test              # Vitest: PKCE (vector RFC 7636), URL OIDC, state/nonce, hạn token, dữ liệu bản đồ, CSP
npm run typecheck     # vue-tsc
npm run licenses      # giấy phép mọi gói npm trong package-lock.json
```

CI chạy cả bốn lệnh, `npm run build`, rồi build image Docker và chạy thử ở job `web` (`.github/workflows/ci.yml`).

## Cấu trúc

| Thư mục | Nội dung |
|---|---|
| `pages/` | `index.vue` (trang điều phối), `auth/callback.vue` |
| `server/` | Nitro: `plugins/bao-mat.ts` (header bảo mật), `utils/csp.ts` (dựng CSP, hàm thuần có test) |
| `components/` | `AppHeader.vue` (logo, người dùng, đăng xuất), `BanDo.vue` (MapLibre), `DanhSachTin.vue` |
| `composables/` | `useAuth.ts` (phiên đăng nhập), `useNow.ts` |
| `utils/` | Hàm thuần, có test: `pkce.ts`, `oidc.ts`, `session.ts`, `ban-do.ts`, `tin-gia.ts` |
| `tests/` | Vitest |
| `scripts/check-licenses.mjs` | Kiểm giấy phép npm |

Logo lấy thẳng từ `docs/images/logo/` của repo (phục vụ ở `/logo/…`, cấu hình trong `nuxt.config.ts`), không chép bản sao.
