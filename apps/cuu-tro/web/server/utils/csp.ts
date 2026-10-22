// SPDX-License-Identifier: Apache-2.0
// Content-Security-Policy cho trang HTML của web điều phối (#64). Hàm thuần, có test (tests/csp.test.ts).
// Nuxt (ssr: false) chèn một <script> inline chứa runtimeConfig, nội dung đổi theo biến môi trường lúc
// chạy: không dùng 'unsafe-inline' mà tính hash SHA-256 của đúng các script inline trong trang.
import { createHash } from 'node:crypto'

export interface CspNguon {
  keycloakUrl: string
  gatewayUrl: string
  mapStyleUrl: string
}

// Ô ảnh dự phòng khi không tải được kiểu nền vector (utils/ban-do.ts, kieuDuPhongOsm)
const OSM_TILE = 'https://tile.openstreetmap.org'

/** Origin (scheme://host:port) của một URL; URL sai thì bỏ qua. */
export function origin(url: string): string | null {
  try {
    const u = new URL(url)
    return u.protocol === 'http:' || u.protocol === 'https:' ? u.origin : null
  } catch {
    return null
  }
}

/** Hash 'sha256-…' của mọi <script> inline có thực thi (bỏ qua script có src và khối dữ liệu JSON). */
export function hashScriptInline(html: string): string[] {
  const ds: string[] = []
  for (const m of html.matchAll(/<script(\s[^>]*)?>([\s\S]*?)<\/script>/gi)) {
    const attrs = m[1] ?? ''
    if (/\ssrc\s*=/i.test(attrs)) continue
    const type = /\stype\s*=\s*["']?([^"'\s>]+)/i.exec(attrs)?.[1]?.toLowerCase()
    if (type && type !== 'module' && type !== 'text/javascript') continue
    ds.push(`'sha256-${createHash('sha256').update(m[2] ?? '', 'utf8').digest('base64')}'`)
  }
  return [...new Set(ds)]
}

export function buildCsp(nguon: CspNguon, scriptHashes: string[]): string {
  const ban = origin(nguon.mapStyleUrl)
  const ketNoi = [...new Set(
    ["'self'", origin(nguon.keycloakUrl), origin(nguon.gatewayUrl), ban, OSM_TILE].filter((x): x is string => !!x),
  )]
  const anh = [...new Set(["'self'", 'data:', 'blob:', ban, OSM_TILE].filter((x): x is string => !!x))]
  return [
    "default-src 'self'",
    `script-src 'self' ${scriptHashes.join(' ')}`.trim(),
    // Vue/MapLibre đặt style trực tiếp trên phần tử; không có script nào chạy được qua style
    "style-src 'self' 'unsafe-inline'",
    `img-src ${anh.join(' ')}`,
    "font-src 'self'",
    `connect-src ${ketNoi.join(' ')}`,
    // MapLibre tạo Web Worker từ blob:
    "worker-src 'self' blob:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join('; ')
}
