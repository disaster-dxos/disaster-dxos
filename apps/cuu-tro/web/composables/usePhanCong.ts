// SPDX-License-Identifier: Apache-2.0
// Gọi mạng cho màn phân công (#61), mọi lời gọi qua API Gateway kèm JWT của người dùng:
//  - hàng đợi và chi tiết tin: query GraphQL HTTP /graphql (Hasura lọc theo vai: cuu-ho chỉ thấy tin của đội mình);
//  - trạng thái workflow và thao tác (phân công, đổi đội, hủy, nhận, từ chối, xác nhận): REST /workflow/*.
// Signal của Temporal là bất đồng bộ (API trả 202): sau thao tác, chờ workflow sang bước mới rồi tải lại.
import type { ComputedRef } from 'vue'
import {
  Q_HANG_PHAN_CONG, TRANG_THAI_HANG, hangTuKetQua, queryTinPhanCong, tinPhanCongTuHang, vaiPhanCong, wfTuPhanHoi,
  HANH_DONG, type HanhDong, type LienHe, type TinPhanCong, type TrangThaiWf, type VaiPhanCong,
} from '~/utils/phan-cong'
import { goiWorkflow, thongBaoLoi, workflowId, yeuCauHanhDong, type KetQuaApi } from '~/utils/workflow-api'
import { httpGraphqlUrl } from '~/utils/tin-graphql'

export interface KetQuaThaoTac { ok: boolean; thongBao: string; status: number }

export function usePhanCong() {
  const rc = useRuntimeConfig().public
  const { session, user, khoiPhuc } = useAuth()
  const vai: ComputedRef<VaiPhanCong | null> = computed(() => vaiPhanCong(user.value))

  async function headers(): Promise<Record<string, string>> {
    if (!(await khoiPhuc()) || !session.value) throw new Error('Phiên đăng nhập đã hết. Hãy đăng nhập lại.')
    const h: Record<string, string> = { Authorization: `Bearer ${session.value.accessToken}` }
    if (vai.value) h['X-Hasura-Role'] = vai.value
    return h
  }

  async function hoiGraphql(query: string, variables: Record<string, unknown>): Promise<unknown> {
    const r = await fetch(httpGraphqlUrl(rc.gatewayUrl as string), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(await headers()) },
      body: JSON.stringify({ query, variables }),
      cache: 'no-store',
    })
    if (!r.ok) throw new Error(r.status === 401 ? 'Phiên đăng nhập đã hết. Hãy đăng nhập lại.' : `Không tải được dữ liệu (HTTP ${r.status})`)
    const body = (await r.json()) as { data?: unknown; errors?: Array<{ message?: string }> }
    if (body.errors?.length) throw new Error(`Máy chủ từ chối truy vấn: ${body.errors[0]?.message ?? 'lỗi GraphQL'}`)
    return body.data
  }

  /** Tin còn việc phân công/cứu (theo quyền của vai). */
  async function taiHang(): Promise<TinPhanCong[]> {
    return hangTuKetQua(await hoiGraphql(Q_HANG_PHAN_CONG, { trangThai: TRANG_THAI_HANG }))
  }

  /** Một tin kèm lịch sử giao và liên hệ người báo (null = không có hoặc vai không được xem). */
  async function taiTin(id: string): Promise<(TinPhanCong & Partial<LienHe>) | null> {
    const data = await hoiGraphql(queryTinPhanCong(vai.value), { id })
    return tinPhanCongTuHang((data as { incidents_by_pk?: unknown } | null)?.incidents_by_pk)
  }

  /** Trạng thái workflow phân công của tin; 404 (chưa từng chạy) → data null. */
  async function taiWorkflow(incidentId: string): Promise<KetQuaApi<TrangThaiWf | null>> {
    const kq = await goiWorkflow(fetch, rc.gatewayUrl as string, await headers(), 'GET', `/${workflowId(incidentId)}`)
    if (!kq.ok) return kq.status === 404 ? { ok: true, status: 404, data: null } : kq
    return { ok: true, status: kq.status, data: wfTuPhanHoi(kq.data) }
  }

  async function thucHien(hd: HanhDong, incidentId: string, ghiChu = ''): Promise<KetQuaThaoTac> {
    const { path, body } = yeuCauHanhDong(hd, incidentId, ghiChu)
    let h: Record<string, string>
    try {
      h = await headers()
    } catch (e) {
      return { ok: false, status: 401, thongBao: e instanceof Error ? e.message : String(e) }
    }
    const kq = await goiWorkflow(fetch, rc.gatewayUrl as string, h, 'POST', path, body)
    if (kq.ok) return { ok: true, status: kq.status, thongBao: HANH_DONG[hd].thanhCong }
    return { ok: false, status: kq.status, thongBao: thongBaoLoi(kq.status, kq.chiTiet, hd, vai.value) }
  }

  /** Chờ workflow đổi trạng thái sau một signal (tối đa ~10 giây); trả trạng thái cuối đọc được. */
  async function choWorkflowDoi(incidentId: string, truoc: TrangThaiWf | null, soLan = 10): Promise<TrangThaiWf | null> {
    const dau = truoc ? `${truoc.trangThai}|${truoc.buoc}|${truoc.doiId}` : ''
    let cuoi = truoc
    for (let i = 0; i < soLan; i++) {
      await new Promise((r) => setTimeout(r, 1_000))
      const kq = await taiWorkflow(incidentId)
      if (!kq.ok) break
      cuoi = kq.data
      const sau = cuoi ? `${cuoi.trangThai}|${cuoi.buoc}|${cuoi.doiId}` : ''
      // Bước chuyển tiếp (đang tìm đội, đang giao lại) chưa phải trạng thái người dùng cần thấy: chờ thêm
      if (sau !== dau && cuoi?.buoc !== 'tim_doi' && cuoi?.buoc !== 'phan_cong_lai' && cuoi?.buoc !== 'doc_tin') break
    }
    return cuoi
  }

  return { vai, taiHang, taiTin, taiWorkflow, thucHien, choWorkflowDoi }
}
