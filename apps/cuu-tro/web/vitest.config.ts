// SPDX-License-Identifier: Apache-2.0
// Test đơn vị cho phần không cần mạng (utils/, server/utils/): PKCE, phiên đăng nhập, dữ liệu bản đồ, CSP.
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  resolve: {
    alias: { '~': fileURLToPath(new URL('.', import.meta.url)) },
  },
  test: {
    environment: 'node',
    include: ['tests/**/*.test.ts'],
  },
})
