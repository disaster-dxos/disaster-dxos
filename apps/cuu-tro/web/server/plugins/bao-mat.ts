// SPDX-License-Identifier: Apache-2.0
// Header bảo mật (#64): header chung cho mọi phản hồi (cả tệp tĩnh), CSP có hash của script inline
// cho trang HTML.
import { buildCsp, hashScriptInline } from '../utils/csp'

const HEADER_CHUNG = {
  'x-content-type-options': 'nosniff',
  'x-frame-options': 'DENY',
  'referrer-policy': 'strict-origin-when-cross-origin',
  'permissions-policy': 'camera=(), microphone=(), geolocation=(self)',
}

export default defineNitroPlugin((nitroApp) => {
  nitroApp.hooks.hook('request', (event) => {
    setResponseHeaders(event, HEADER_CHUNG)
  })
  nitroApp.hooks.hook('render:response', (response) => {
    if (typeof response.body !== 'string') return
    const pub = useRuntimeConfig().public
    response.headers ??= {}
    response.headers['content-security-policy'] = buildCsp(
      { keycloakUrl: pub.keycloakUrl, gatewayUrl: pub.gatewayUrl, mapStyleUrl: pub.mapStyleUrl, mapStyleUrlToi: pub.mapStyleUrlToi },
      hashScriptInline(response.body),
    )
    delete response.headers['x-powered-by']
  })
})
