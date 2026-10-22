// SPDX-License-Identifier: Apache-2.0
// Web điều phối (Tầng 2, #59). Chạy thuần phía trình duyệt (ssr: false): đăng nhập OIDC + PKCE
// với client công khai, không có bí mật nào trong mã web. Mọi lời gọi lõi đi qua API Gateway.
import { fileURLToPath } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import type { NitroConfig } from 'nitropack'

export default defineNuxtConfig({
  compatibilityDate: '2026-10-01',
  ssr: false,
  devtools: { enabled: false },
  telemetry: false,
  css: ['~/assets/css/main.css'],
  vite: {
    plugins: [tailwindcss()],
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
    // Nuxt 3.21 khai báo kiểu tham số là NitroConfigFallback, thiếu publicAssets: ép về NitroConfig
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
    },
  },
})
