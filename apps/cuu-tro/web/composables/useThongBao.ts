// SPDX-License-Identifier: Apache-2.0
// Kết nối Centrifugo (#68) để nhận thông báo realtime trên kênh "dieu-phoi". SDK centrifuge-js tự
// kết nối lại (backoff), tự xin token mới trước khi hết hạn và lấy bù tin lỡ khi kết nối lại (recovery).
// Token kết nối xin từ API ứng dụng qua gateway (/workflow/realtime/token, kèm JWT Keycloak): không có
// bí mật nào trong web. API trả 401/403 (hết phiên, không phải điều phối) thì dừng hẳn, không thử lại.
import { Centrifuge, State, UnauthorizedError, type PublicationContext, type StateContext } from 'centrifuge'
import { docThongBao, themThongBao, tokenUrl, wsUrl, type ThongBao } from '~/utils/thong-bao'

export type TrangThaiKetNoi = 'tat' | 'dang-ket-noi' | 'da-ket-noi' | 'mat-ket-noi' | 'bi-tu-choi'

let client: Centrifuge | null = null

export function useThongBao() {
  const rc = useRuntimeConfig().public
  const { authHeader } = useAuth()
  const ds = useState<ThongBao[]>('thong-bao', () => [])
  const chuaDoc = useState<number>('thong-bao-chua-doc', () => 0)
  const trangThai = useState<TrangThaiKetNoi>('thong-bao-ket-noi', () => 'tat')

  async function layToken(): Promise<string> {
    const r = await fetch(tokenUrl(rc.gatewayUrl as string), { headers: authHeader(), cache: 'no-store' })
    if (r.status === 401 || r.status === 403) {
      trangThai.value = 'bi-tu-choi'
      throw new UnauthorizedError(`API từ chối cấp token (${r.status})`)
    }
    if (!r.ok) throw new Error(`API cấp token lỗi HTTP ${r.status}`)
    const body = (await r.json()) as { token?: string }
    if (!body.token) throw new Error('API không trả token')
    return body.token
  }

  function nhan(ctx: PublicationContext) {
    const tb = docThongBao(ctx.data)
    if (!tb) return
    const truoc = ds.value
    ds.value = themThongBao(truoc, tb)
    if (ds.value !== truoc) chuaDoc.value += 1
  }

  function batDau() {
    if (client) return
    client = new Centrifuge(wsUrl(rc.gatewayUrl as string), {
      getToken: layToken,
      minReconnectDelay: 500,
      maxReconnectDelay: 20_000,
    })
    client.on('state', (ctx: StateContext) => {
      if (trangThai.value === 'bi-tu-choi' && ctx.newState === State.Disconnected) return
      trangThai.value = ctx.newState === State.Connected ? 'da-ket-noi'
        : ctx.newState === State.Connecting ? (trangThai.value === 'da-ket-noi' ? 'mat-ket-noi' : 'dang-ket-noi')
          : 'tat'
    })
    // Kênh server-side: publication đến thẳng client, không cần subscribe phía web
    client.on('publication', nhan)
    client.connect()
  }

  function dung() {
    client?.disconnect()
    client?.removeAllListeners()
    client = null
    trangThai.value = 'tat'
  }

  function daDoc() {
    chuaDoc.value = 0
  }

  return { ds, chuaDoc, trangThai, batDau, dung, daDoc }
}
