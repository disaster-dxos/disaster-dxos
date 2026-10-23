# SPDX-License-Identifier: Apache-2.0
# Image web điều phối (#64): build Nuxt bằng Node, chạy bằng Nitro node server (không phải trang tĩnh):
# với ssr: false, Nitro vẫn chèn runtimeConfig (NUXT_PUBLIC_* lúc chạy) vào trang HTML và đặt header
# bảo mật/CSP (server/plugins/bao-mat.ts). Một image dùng cho mọi môi trường, không build lại khi đổi URL.
# Không có bí mật nào trong image: client dxos-web là client công khai (PKCE).
#
# Build context = apps/cuu-tro/web; bộ logo của repo (docs/images/logo) đưa vào bằng context phụ "logo"
# (additional_contexts trong apps/cuu-tro/compose.yaml), đặt đúng đường dẫn tương đối mà nuxt.config.ts dùng.
# Build tay: docker build --build-context logo=docs/images/logo -t disaster-dxos/cuu-tro-web:0.2.0 apps/cuu-tro/web

FROM node:22.22.3-bookworm-slim AS build
ENV NUXT_TELEMETRY_DISABLED=1 NPM_CONFIG_UPDATE_NOTIFIER=false NPM_CONFIG_FUND=false
WORKDIR /src/apps/cuu-tro/web
COPY package.json package-lock.json ./
# Bỏ postinstall (nuxt prepare cần mã nguồn); nuxt build tự prepare
RUN npm ci --ignore-scripts --no-audit
COPY --from=logo . /src/docs/images/logo
COPY . .
RUN npm run build

FROM node:22.22.3-alpine3.22
ENV NODE_ENV=production HOST=0.0.0.0 PORT=3000 NUXT_TELEMETRY_DISABLED=1
WORKDIR /app
# .output tự chứa (server + node_modules đã trace + tệp tĩnh), không cần npm ở image chạy
COPY --from=build --chown=root:root /src/apps/cuu-tro/web/.output ./.output
# User node (uid 1000) có sẵn trong image gốc; mã chỉ đọc, thuộc root
USER node
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"]
CMD ["node", ".output/server/index.mjs"]
