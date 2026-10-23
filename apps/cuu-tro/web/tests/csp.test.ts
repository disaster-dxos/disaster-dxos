// SPDX-License-Identifier: Apache-2.0
import { createHash } from 'node:crypto'
import { describe, expect, it } from 'vitest'
import { buildCsp, hashScriptInline, origin, wsOrigin } from '../server/utils/csp'

const sha = (s: string) => `'sha256-${createHash('sha256').update(s, 'utf8').digest('base64')}'`
const nguon = {
  keycloakUrl: 'http://localhost:8080',
  gatewayUrl: 'http://localhost:9080/',
  mapStyleUrl: 'https://tiles.openfreemap.org/styles/liberty',
}

describe('hash script inline', () => {
  it('chỉ hash script có thực thi, bỏ script có src và khối JSON', () => {
    const cfg = 'window.__NUXT__={};window.__NUXT__.config={public:{}}'
    const html = `<head><script type="module" src="/_nuxt/a.js" crossorigin></script>
      <script id="unhead:payload" type="application/json">{"title":"x"}</script></head>
      <body><script>${cfg}</script>
      <script type="application/json" data-nuxt-data="nuxt-app" id="__NUXT_DATA__">[{}]</script></body>`
    expect(hashScriptInline(html)).toEqual([sha(cfg)])
  })

  it('không có script inline thì không có hash', () => {
    expect(hashScriptInline('<script src="/a.js"></script>')).toEqual([])
  })
})

describe('CSP', () => {
  const csp = buildCsp(nguon, [sha('x')])
  const muc = Object.fromEntries(csp.split('; ').map((d) => [d.split(' ')[0], d.split(' ').slice(1)]))

  it('script chỉ từ chính web và hash, không unsafe-inline/unsafe-eval', () => {
    expect(muc['script-src']).toEqual(["'self'", sha('x')])
    expect(csp).not.toMatch(/script-src[^;]*unsafe/)
  })

  it('chống nhúng iframe và chặn object/base', () => {
    expect(muc['frame-ancestors']).toEqual(["'none'"])
    expect(muc['object-src']).toEqual(["'none'"])
    expect(muc['base-uri']).toEqual(["'self'"])
  })

  it('chỉ kết nối tới Keycloak, gateway (cả WebSocket realtime và GraphQL subscription) và nguồn bản đồ', () => {
    expect(muc['connect-src']).toEqual([
      "'self'", 'http://localhost:8080', 'http://localhost:9080', 'ws://localhost:9080',
      'https://tiles.openfreemap.org', 'https://tile.openstreetmap.org',
    ])
    expect(muc['worker-src']).toContain('blob:')
  })

  it('gateway HTTPS thì WebSocket là wss, không mở ws/wss tới nơi khác', () => {
    expect(wsOrigin('https://cuutro.example.vn/x')).toBe('wss://cuutro.example.vn')
    const c = buildCsp({ ...nguon, gatewayUrl: 'https://cuutro.example.vn' }, [])
    expect(c).toContain('wss://cuutro.example.vn')
    expect(c).not.toContain('ws://')
    expect(wsOrigin('khong-phai-url')).toBeNull()
  })

  it('bỏ qua URL sai', () => {
    expect(origin('khong-phai-url')).toBeNull()
    expect(origin('javascript:alert(1)')).toBeNull()
    expect(buildCsp({ ...nguon, mapStyleUrl: 'x' }, [])).toContain("script-src 'self';")
  })
})
