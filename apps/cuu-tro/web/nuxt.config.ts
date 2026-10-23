// SPDX-License-Identifier: Apache-2.0
// Web điều phối (Tầng 2, #59). Chạy thuần phía trình duyệt (ssr: false): đăng nhập OIDC + PKCE
// với client công khai, không có bí mật nào trong mã web. Mọi lời gọi lõi đi qua API Gateway.
import { fileURLToPath } from 'node:url'
import type { NitroConfig } from 'nitropack'

export default defineNuxtConfig({
  compatibilityDate: '2026-10-01',
  ssr: false,
  devtools: { enabled: false },
  telemetry: false,
  // Nuxt UI (MIT) mang theo Tailwind CSS 4, bảng màu sáng/tối (@nuxtjs/color-mode) và biểu tượng (@nuxt/icon)
  modules: ['@nuxt/ui'],
  css: ['~/assets/css/main.css'],
  ui: {
    // Không dùng @nuxt/fonts (tải font từ Google lúc build): Be Vietnam Pro tự host trong public/fonts
    fonts: false,
  },
  // Mặc định giao diện sáng; người dùng đổi Sáng/Tối/Theo máy ở menu tài khoản (các màn hỗ trợ tối dần ở #78)
  colorMode: { preference: 'light', fallback: 'light' },
  icon: {
    // Biểu tượng Lucide đóng gói sẵn trong bundle: không gọi API Iconify (CSP chặn, mất mạng vẫn chạy)
    provider: 'none',
    clientBundle: { scan: true },
  },
  app: {
    head: {
      htmlAttrs: { lang: 'vi' },
      title: 'Điều phối cứu trợ · Disaster DX-OS',
      meta: [
        { name: 'description', content: 'Web điều phối ứng phó thiên tai và cứu trợ cộng đồng' },
        { name: 'theme-color', content: '#12355B' },
      ],
      link: [
        { rel: 'icon', href: '/logo/favicon.ico' },
        { rel: 'apple-touch-icon', href: '/logo/mark-180.png' },
      ],
    },
  },
  hooks: {
    // Bộ logo dùng chung của repo (docs/images/logo/) phục vụ ở /logo, không chép thêm bản sao
    // Nuxt khai báo kiểu tham số là NitroConfigFallback, thiếu publicAssets: ép về NitroConfig
    'nitro:config'(cfg) {
      const nitro = cfg as NitroConfig
      nitro.publicAssets ??= []
      nitro.publicAssets.push({
        dir: fileURLToPath(new URL('../../../docs/images/logo', import.meta.url)),
        baseURL: '/logo',
        maxAge: 60 * 60 * 24,
      })
    },
  },
  runtimeConfig: {
    // Ghi đè lúc chạy bằng biến môi trường NUXT_PUBLIC_* (xem .env.example ở gốc repo)
    public: {
      keycloakUrl: 'http://localhost:8080',
      keycloakRealm: 'disaster',
      keycloakClientId: 'dxos-web',
      gatewayUrl: 'http://localhost:9080',
      mapStyleUrl: 'https://tiles.openfreemap.org/styles/liberty',
      // Kiểu nền khi giao diện ở chế độ tối (cùng nguồn OpenFreeMap nên CSP không đổi)
      mapStyleUrlToi: 'https://tiles.openfreemap.org/styles/dark',
    },
  },
})
