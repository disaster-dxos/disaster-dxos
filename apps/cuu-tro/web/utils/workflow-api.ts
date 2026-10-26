// SPDX-License-Identifier: Apache-2.0
// Gọi API workflow của ứng dụng qua API Gateway (/workflow/*, #61) và đổi lỗi HTTP thành câu tiếng Việt.
// `fetch` truyền vào để test bằng mock (tests/workflow-api.test.ts). Endpoint và luật quyền:
// apps/cuu-tro/workflow/cuu_tro_workflow/api.py; ở đây không viết lại luật, chỉ hiển thị kết quả.
import { ghiChuDoiDoi, type HanhDong, type VaiPhanCong } from './phan-cong'

export const DUONG_WORKFLOW = '/workflow'
export const TIEN_TO_PHAN_CONG = 'phan-cong-'

export function workflowId(incidentId: string): string {
  return `${TIEN_TO_PHAN_CONG}${incidentId}`
}

export type KetQuaApi<T> =
  | { ok: true; status: number; data: T }
  /** status 0 = không tới được máy chủ (mất mạng, gateway tắt); detail = `detail` gốc của FastAPI nếu có */
  | { ok: false; status: number; chiTiet: string; detail?: unknown }

/** Đường dẫn và body của từng thao tác (đổi đội = signal từ chối do điều phối gửi, cùng endpoint). */
export function yeuCauHanhDong(hd: HanhDong, incidentId: string, ghiChu = ''): { path: string; body?: Record<string, string> } {
  const wf = workflowId(incidentId)
  const gc = ghiChu.trim()
  switch (hd) {
    case 'phan_cong': return { path: `/phan-cong/${incidentId}` }
    case 'doi_doi': return { path: `/${wf}/tu-choi`, body: { ghi_chu: ghiChuDoiDoi(gc) } }
    case 'huy': return { path: `/${wf}/huy`, body: { ly_do: gc } }
    case 'nhan': return { path: `/${wf}/nhan`, body: { ghi_chu: gc } }
    case 'tu_choi': return { path: `/${wf}/tu-choi`, body: { ghi_chu: gc } }
    case 'xac_nhan': return { path: `/${wf}/xac-nhan`, body: { ghi_chu: gc } }
  }
}

/** `detail` của FastAPI là chuỗi hoặc đối tượng ({ma, thong_bao, …}); đưa về một chuỗi. */
function chiTietLoi(body: unknown): string {
  const d = (body as { detail?: unknown } | null)?.detail
  if (typeof d === 'string') return d
  if (d && typeof d === 'object' && typeof (d as { thong_bao?: unknown }).thong_bao === 'string') {
    return (d as { thong_bao: string }).thong_bao
  }
  return ''
}

export async function goiWorkflow<T = unknown>(
  fetchFn: typeof fetch, gatewayUrl: string, headers: Record<string, string>,
  method: 'GET' | 'POST', path: string, body?: Record<string, unknown>,
): Promise<KetQuaApi<T>> {
  const url = new URL(DUONG_WORKFLOW + path, gatewayUrl).toString()
  let r: Response
  try {
    r = await fetchFn(url, {
      method,
      headers: { ...headers, ...(method === 'POST' ? { 'Content-Type': 'application/json' } : {}) },
      ...(method === 'POST' ? { body: JSON.stringify(body ?? {}) } : {}),
      cache: 'no-store',
    })
  } catch (e) {
    return { ok: false, status: 0, chiTiet: e instanceof Error ? e.message : String(e) }
  }
  let data: unknown = null
  try {
    data = await r.json()
  } catch {
    // APISIX trả trang lỗi HTML/rỗng (502, 429…): giữ mã HTTP
  }
  if (!r.ok) {
    const detail = (data as { detail?: unknown } | null)?.detail
    return { ok: false, status: r.status, chiTiet: chiTietLoi(data), ...(detail === undefined ? {} : { detail }) }
  }
  return { ok: true, status: r.status, data: data as T }
}

/**
 * Lỗi của thao tác → câu tiếng Việt cho người dùng. Các ca 409/403 theo luật API:
 * - đội cũ bấm muộn (đã quá hạn / bị thay): Hasura không còn cho đội đọc tin → 403, hoặc 409 "đã được giao cho đội khác";
 * - workflow đã sang bước khác (đã nhận, quá hạn, đã xong) → 409 "không ở bước …";
 * - khởi chạy khi luồng đang chạy / tin không ở tiep_nhan → 409; hủy khi đội đã nhận → 409 "Không hủy được".
 */
export function thongBaoLoi(status: number, chiTiet: string, hd: HanhDong | 'xem', vai: VaiPhanCong | null): string {
  const doiThaoTac = hd === 'nhan' || hd === 'tu_choi' || hd === 'xac_nhan' || hd === 'xem'
  switch (true) {
    case status === 0:
      return 'Không kết nối được máy chủ. Kiểm tra mạng rồi thử lại.'
    case status === 401:
      return 'Phiên đăng nhập đã hết. Hãy đăng nhập lại.'
    case status === 403 && vai === 'cuu-ho' && doiThaoTac:
      return 'Nhiệm vụ không còn giao cho đội của bạn: đã quá hạn nhận hoặc đã được giao cho đội khác.'
    case status === 403:
      return 'Bạn không có quyền thực hiện thao tác này.'
    case status === 404:
      return hd === 'phan_cong' ? 'Không tìm thấy tin kêu cứu này.' : 'Tin này chưa có luồng phân công nào.'
    case status === 409 && /đội khác/.test(chiTiet):
      return 'Nhiệm vụ đã được giao cho đội khác (đội bạn trả lời muộn hoặc đã quá hạn nhận).'
    case status === 409 && /đang chạy/.test(chiTiet):
      return 'Tin này đang có luồng phân công chạy, không khởi chạy thêm được.'
    case status === 409 && /chỉ phân công tin tiep_nhan/.test(chiTiet):
      return 'Tin không còn ở trạng thái Tiếp nhận nên không phân công lại được.'
    case status === 409 && /Không hủy được/.test(chiTiet):
      return 'Không hủy được: đội đã nhận nhiệm vụ hoặc luồng phân công đã kết thúc.'
    case status === 409:
      return 'Nhiệm vụ đã sang bước khác (đã nhận, quá hạn hoặc đã xong). Màn hình đã tải lại trạng thái mới.'
    case status === 413 || status === 422:
      return 'Dữ liệu gửi lên không hợp lệ (ghi chú tối đa 500 ký tự).'
    case status === 429:
      return 'Thao tác quá nhanh. Chờ một chút rồi thử lại.'
    case status >= 500:
      return `Máy chủ đang lỗi (HTTP ${status}). Thử lại sau ít phút.`
    default:
      return `Thao tác không thành công (HTTP ${status}).`
  }
}
