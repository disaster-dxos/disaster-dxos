// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it, vi } from 'vitest'
import { goiWorkflow, thongBaoLoi, workflowId, yeuCauHanhDong } from '~/utils/workflow-api'

const INC = 'b0000000-0000-4000-8000-000000000004'
const WF = `phan-cong-${INC}`
const GW = 'http://localhost:9080'
const AUTH = { 'Authorization': 'Bearer t', 'X-Hasura-Role': 'cuu-ho' }

/** fetch giả: trả mã HTTP + body JSON (hoặc chuỗi thô) và ghi lại lời gọi */
function fetchGia(status: number, body: unknown) {
  return vi.fn(async (_url: string, _init?: RequestInit) => new Response(
    typeof body === 'string' ? body : JSON.stringify(body),
    { status, headers: { 'Content-Type': typeof body === 'string' ? 'text/html' : 'application/json' } },
  ))
}

describe('đường dẫn từng thao tác', () => {
  it('khớp endpoint của API /workflow', () => {
    expect(workflowId(INC)).toBe(WF)
    expect(yeuCauHanhDong('phan_cong', INC)).toEqual({ path: `/phan-cong/${INC}` })
    expect(yeuCauHanhDong('nhan', INC, ' đang đi ')).toEqual({ path: `/${WF}/nhan`, body: { ghi_chu: 'đang đi' } })
    expect(yeuCauHanhDong('tu_choi', INC, 'ca nô hỏng')).toEqual({ path: `/${WF}/tu-choi`, body: { ghi_chu: 'ca nô hỏng' } })
    expect(yeuCauHanhDong('xac_nhan', INC)).toEqual({ path: `/${WF}/xac-nhan`, body: { ghi_chu: '' } })
    expect(yeuCauHanhDong('huy', INC, 'trùng')).toEqual({ path: `/${WF}/huy`, body: { ly_do: 'trùng' } })
  })
  it('đổi đội = signal từ chối do điều phối gửi (workflow giao đội gần nhất kế tiếp)', () => {
    expect(yeuCauHanhDong('doi_doi', INC, 'đội ở xa')).toEqual({ path: `/${WF}/tu-choi`, body: { ghi_chu: 'Điều phối đổi đội: đội ở xa' } })
  })
})

describe('gọi API qua gateway (fetch giả)', () => {
  it('POST: đúng URL qua gateway, JWT + Content-Type, body JSON, không cache', async () => {
    const f = fetchGia(202, { workflow_id: WF, da_gui: 'nhan_nhiem_vu' })
    const kq = await goiWorkflow(f as unknown as typeof fetch, GW, AUTH, 'POST', `/${WF}/nhan`, { ghi_chu: 'x' })
    expect(kq).toEqual({ ok: true, status: 202, data: { workflow_id: WF, da_gui: 'nhan_nhiem_vu' } })
    const [url, init] = f.mock.calls[0]!
    expect(url).toBe(`${GW}/workflow/${WF}/nhan`)
    expect(init).toMatchObject({ method: 'POST', cache: 'no-store', body: '{"ghi_chu":"x"}' })
    expect(init!.headers).toEqual({ ...AUTH, 'Content-Type': 'application/json' })
  })
  it('POST không body vẫn gửi {} (FastAPI nhận body tùy chọn)', async () => {
    const f = fetchGia(202, { workflow_id: WF })
    await goiWorkflow(f as unknown as typeof fetch, `${GW}/`, AUTH, 'POST', `/phan-cong/${INC}`)
    expect(f.mock.calls[0]![0]).toBe(`${GW}/workflow/phan-cong/${INC}`)
    expect(f.mock.calls[0]![1]).toMatchObject({ body: '{}' })
  })
  it('GET không có body, không Content-Type', async () => {
    const f = fetchGia(200, { workflow_id: WF, trang_thai: 'RUNNING', chi_tiet: { buoc: 'cho_nhan' } })
    const kq = await goiWorkflow(f as unknown as typeof fetch, GW, AUTH, 'GET', `/${WF}`)
    expect(kq.ok).toBe(true)
    expect(f.mock.calls[0]![1]).not.toHaveProperty('body')
    expect(f.mock.calls[0]![1]!.headers).toEqual(AUTH)
  })
  it('lỗi: đọc detail chuỗi hoặc đối tượng của FastAPI', async () => {
    const k1 = await goiWorkflow(fetchGia(409, { detail: 'Nhiệm vụ đã được giao cho đội khác' }) as unknown as typeof fetch, GW, AUTH, 'POST', `/${WF}/nhan`)
    expect(k1).toEqual({ ok: false, status: 409, chiTiet: 'Nhiệm vụ đã được giao cho đội khác' })
    const k2 = await goiWorkflow(fetchGia(422, { detail: { ma: 'x', thong_bao: 'Sai' } }) as unknown as typeof fetch, GW, AUTH, 'POST', '/x')
    expect(k2).toEqual({ ok: false, status: 422, chiTiet: 'Sai' })
  })
  it('gateway trả HTML (502, 429): giữ mã HTTP, chi tiết rỗng', async () => {
    const kq = await goiWorkflow(fetchGia(502, '<html>Bad Gateway</html>') as unknown as typeof fetch, GW, AUTH, 'GET', `/${WF}`)
    expect(kq).toEqual({ ok: false, status: 502, chiTiet: '' })
  })
  it('mất mạng: status 0', async () => {
    const f = vi.fn(async () => { throw new TypeError('Failed to fetch') })
    const kq = await goiWorkflow(f as unknown as typeof fetch, GW, AUTH, 'POST', `/${WF}/nhan`)
    expect(kq).toEqual({ ok: false, status: 0, chiTiet: 'Failed to fetch' })
  })
})

describe('mã lỗi → thông báo tiếng Việt', () => {
  it('403 với cứu hộ: đội cũ nhận muộn / quá hạn', () => {
    expect(thongBaoLoi(403, 'Tin kêu cứu không được phân công cho đội của bạn', 'nhan', 'cuu-ho')).toMatch(/không còn giao cho đội của bạn.*quá hạn/)
    expect(thongBaoLoi(403, '', 'xac_nhan', 'cuu-ho')).toMatch(/không còn giao cho đội của bạn/)
  })
  it('403 với thao tác của điều phối: không có quyền', () => {
    expect(thongBaoLoi(403, 'Cần vai trò: dieu-phoi', 'huy', 'cuu-ho')).toBe('Bạn không có quyền thực hiện thao tác này.')
    expect(thongBaoLoi(403, '', 'phan_cong', 'dieu-phoi')).toBe('Bạn không có quyền thực hiện thao tác này.')
  })
  it('409 theo chi tiết của API', () => {
    expect(thongBaoLoi(409, 'Nhiệm vụ đã được giao cho đội khác', 'nhan', 'cuu-ho')).toMatch(/giao cho đội khác.*muộn/)
    expect(thongBaoLoi(409, `Workflow ${WF} đang chạy`, 'phan_cong', 'dieu-phoi')).toMatch(/đang có luồng phân công chạy/)
    expect(thongBaoLoi(409, 'Tin kêu cứu đang ở trạng thái dong, chỉ phân công tin tiep_nhan', 'phan_cong', 'dieu-phoi')).toMatch(/không còn ở trạng thái Tiếp nhận/)
    expect(thongBaoLoi(409, 'Không hủy được: đội đã nhận hoặc workflow đã xong (trạng thái RUNNING, bước cho_xac_nhan)', 'huy', 'dieu-phoi')).toMatch(/^Không hủy được: đội đã nhận/)
    expect(thongBaoLoi(409, 'Workflow không ở bước cho_nhan (trạng thái COMPLETED, bước xong)', 'nhan', 'cuu-ho')).toMatch(/đã sang bước khác/)
  })
  it('mã khác', () => {
    expect(thongBaoLoi(0, 'Failed to fetch', 'nhan', 'cuu-ho')).toMatch(/Không kết nối được máy chủ/)
    expect(thongBaoLoi(401, '', 'nhan', 'cuu-ho')).toMatch(/Phiên đăng nhập đã hết/)
    expect(thongBaoLoi(404, '', 'nhan', 'cuu-ho')).toBe('Tin này chưa có luồng phân công nào.')
    expect(thongBaoLoi(404, '', 'phan_cong', 'dieu-phoi')).toBe('Không tìm thấy tin kêu cứu này.')
    expect(thongBaoLoi(422, '', 'tu_choi', 'cuu-ho')).toMatch(/500 ký tự/)
    expect(thongBaoLoi(429, '', 'nhan', 'cuu-ho')).toMatch(/quá nhanh/)
    expect(thongBaoLoi(503, '', 'nhan', 'cuu-ho')).toMatch(/HTTP 503/)
    expect(thongBaoLoi(418, '', 'nhan', 'cuu-ho')).toBe('Thao tác không thành công (HTTP 418).')
  })
})
