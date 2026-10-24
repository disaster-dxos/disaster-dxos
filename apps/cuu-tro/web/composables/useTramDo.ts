// SPDX-License-Identifier: Apache-2.0
// Trạm đo mực nước cho bản đồ (#62), mọi lời gọi qua API Gateway kèm JWT của người dùng:
//  - danh sách trạm: NGSI-LD Scorpio GET /ngsi-ld/v1/entities (GeoJSON), tải lại mỗi CHU_KY_TAI_TRAM;
//    trang gọi lamMoi() ngay khi có cảnh báo mực nước realtime (Centrifugo, chỉ vai điều phối);
//    tab ẩn thì bỏ lượt tải định kỳ, hiện lại thì tải ngay;
//  - chuỗi đo 24 giờ của một trạm cho biểu đồ nhỏ: GraphQL sensor_readings, chỉ tải khi mở popup.
import {
  ACCEPT_TRAM, CHU_KY_TAI_TRAM, Q_LICH_SU_TRAM, lichSuTuKetQua, mocLichSu, tramTuGeoJson, tramUrl,
  type DiemDo, type TramDo,
} from '~/utils/tram-do'
import { httpGraphqlUrl } from '~/utils/tin-graphql'

export type TrangThaiTram = 'tat' | 'dang-tai' | 'da-tai' | 'loi'

let henTai: ReturnType<typeof setInterval> | undefined
let dangTai: Promise<void> | null = null

export function useTramDo() {
  const rc = useRuntimeConfig().public
  const { session, khoiPhuc } = useAuth()
  const ds = useState<TramDo[]>('tram-ds', () => [])
  const trangThai = useState<TrangThaiTram>('tram-trang-thai', () => 'tat')
  const loi = useState<string>('tram-loi', () => '')
  const capNhatLuc = useState<number | null>('tram-cap-nhat', () => null)

  async function token(): Promise<string> {
    if (!(await khoiPhuc()) || !session.value) throw new Error('Phiên đăng nhập đã hết. Hãy đăng nhập lại.')
    return session.value.accessToken
  }

  async function tai(): Promise<void> {
    if (trangThai.value === 'tat') trangThai.value = 'dang-tai'
    try {
      const r = await fetch(tramUrl(rc.gatewayUrl as string), {
        headers: { Accept: ACCEPT_TRAM, Authorization: `Bearer ${await token()}` },
        cache: 'no-store',
      })
      if (!r.ok) throw new Error(r.status === 401 ? 'Phiên đăng nhập đã hết. Hãy đăng nhập lại.' : `Không tải được trạm đo (HTTP ${r.status})`)
      ds.value = tramTuGeoJson(await r.json())
      capNhatLuc.value = Date.now()
      loi.value = ''
      trangThai.value = 'da-tai'
    } catch (e) {
      // Giữ danh sách cũ trên bản đồ, chỉ báo lỗi
      loi.value = e instanceof Error ? e.message : String(e)
      trangThai.value = 'loi'
    }
  }

  /** Tải ngay (gộp các lời gọi trùng lúc, ví dụ nhiều cảnh báo đến cùng lúc). */
  function lamMoi(): Promise<void> {
    dangTai ??= tai().finally(() => { dangTai = null })
    return dangTai
  }

  function khiHien() {
    if (document.visibilityState === 'visible') void lamMoi()
  }

  function batDau() {
    if (henTai) return
    void lamMoi()
    henTai = setInterval(() => {
      if (document.visibilityState !== 'hidden') void lamMoi()
    }, CHU_KY_TAI_TRAM)
    document.addEventListener('visibilitychange', khiHien)
  }

  function dung() {
    clearInterval(henTai)
    henTai = undefined
    document.removeEventListener('visibilitychange', khiHien)
    trangThai.value = 'tat'
  }

  /** Chuỗi đo GIO_LICH_SU giờ gần nhất của một trạm (theo thời gian tăng dần). */
  async function layLichSu(ma: string): Promise<DiemDo[]> {
    const r = await fetch(httpGraphqlUrl(rc.gatewayUrl as string), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await token()}` },
      body: JSON.stringify({ query: Q_LICH_SU_TRAM, variables: { ma, tu: mocLichSu() } }),
      cache: 'no-store',
    })
    if (!r.ok) throw new Error(`Không tải được chuỗi đo (HTTP ${r.status})`)
    const body = (await r.json()) as { data?: unknown; errors?: Array<{ message?: string }> }
    if (body.errors?.length) throw new Error(body.errors[0]?.message ?? 'Lỗi GraphQL')
    return lichSuTuKetQua(body.data)
  }

  return { ds, trangThai, loi, capNhatLuc, batDau, dung, lamMoi, layLichSu }
}
