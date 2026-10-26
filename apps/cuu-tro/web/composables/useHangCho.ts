// SPDX-License-Identifier: Apache-2.0
// Gọi mạng cho hàng chờ duyệt tin AI (#104), mọi lời gọi qua API Gateway kèm JWT của người dùng:
//  - đọc hàng chờ: query GraphQL HTTP /graphql với vai dieu-phoi (Hasura: chỉ vai này thấy văn bản và đề xuất);
//  - bóc tách + đưa vào hàng chờ: POST /workflow/ai/boc-tach {"vao_hang_cho": true};
//  - duyệt / hủy: POST /workflow/hang-cho/{id}/duyet | huy (API kiểm quyền, Poka-yoke, tin trùng, người khác
//    vừa xử lý).
import { hangChoTuKetQua, queryHangCho, type BodyTin, type LoiApi, type MucHangCho, type NguonVanBan, type TrangThaiHangCho } from '~/utils/hang-cho'
import { httpGraphqlUrl } from '~/utils/tin-graphql'
import { goiWorkflow } from '~/utils/workflow-api'

export type KetQua<T> = { ok: true; data: T } | ({ ok: false } & LoiApi)

export function useHangCho() {
  const rc = useRuntimeConfig().public
  const { session, user, khoiPhuc } = useAuth()
  const laDieuPhoi = computed(() => Boolean(user.value?.roles.includes('dieu-phoi')))

  async function headers(): Promise<Record<string, string>> {
    if (!(await khoiPhuc()) || !session.value) throw new Error('Phiên đăng nhập đã hết. Hãy đăng nhập lại.')
    return { 'Authorization': `Bearer ${session.value.accessToken}`, 'X-Hasura-Role': 'dieu-phoi' }
  }

  async function taiHang(tt: TrangThaiHangCho): Promise<{ ds: MucHangCho[]; soChoDuyet: number }> {
    const r = await fetch(httpGraphqlUrl(rc.gatewayUrl as string), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(await headers()) },
      body: JSON.stringify({ query: queryHangCho(tt), variables: { tt } }),
      cache: 'no-store',
    })
    if (!r.ok) throw new Error(r.status === 401 ? 'Phiên đăng nhập đã hết. Hãy đăng nhập lại.' : `Không tải được hàng chờ (HTTP ${r.status})`)
    const body = (await r.json()) as { data?: unknown; errors?: Array<{ message?: string }> }
    if (body.errors?.length) throw new Error(`Máy chủ từ chối truy vấn: ${body.errors[0]?.message ?? 'lỗi GraphQL'}`)
    return hangChoTuKetQua(body.data)
  }

  async function goi<T>(path: string, body: Record<string, unknown>): Promise<KetQua<T>> {
    let h: Record<string, string>
    try {
      h = await headers()
    } catch (e) {
      return { ok: false, status: 401, detail: e instanceof Error ? e.message : String(e) }
    }
    const kq = await goiWorkflow<T>(fetch, rc.gatewayUrl as string, h, 'POST', path, body)
    return kq.ok ? { ok: true, data: kq.data } : { ok: false, status: kq.status, detail: kq.detail ?? kq.chiTiet }
  }

  /** AI bóc tách rồi lưu vào hàng chờ (API tự lưu đề xuất, không tạo tin). */
  const bocTach = (vanBan: string, nguon: NguonVanBan) =>
    goi<{ hang_cho: { id: string } }>('/ai/boc-tach', { van_ban: vanBan, nguon, vao_hang_cho: true })

  /** Duyệt với body /keu-cuu đầy đủ đã sửa → tạo tin kêu cứu thật. */
  const duyet = (id: string, tin: BodyTin) =>
    goi<{ incident_id: string; truong_da_sua: string[] }>(`/hang-cho/${id}/duyet`, { tin_keu_cuu: tin })

  const huy = (id: string, lyDo: string) =>
    goi<{ trang_thai: string }>(`/hang-cho/${id}/huy`, lyDo.trim() ? { ly_do: lyDo.trim() } : {})

  return { laDieuPhoi, taiHang, bocTach, duyet, huy }
}
