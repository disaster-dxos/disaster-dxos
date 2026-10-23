// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest'
import {
  NHOM_THEO_VAI, Q_HANG_PHAN_CONG, demNguoc, ghiChuDoiDoi, giaoCuoi, giaoDangCho, hangTuKetQua, hanhDongDuoc,
  khoangCach, queryTinPhanCong, tiLeDaQua, tinPhanCongTuHang, tomTatGiao, vaiPhanCong, wfTuPhanHoi, nhomTin,
  type TinPhanCong, type TrangThaiWf,
} from '~/utils/phan-cong'
import type { UserInfo } from '~/utils/session'
import type { MucKhan, TrangThai } from '~/utils/tin'

const NOW = Date.parse('2026-10-23T08:00:00Z')
const INC = 'b0000000-0000-4000-8000-000000000004'
const DOI1 = 'a0000000-0000-4000-8000-000000000001'
const DOI2 = 'a0000000-0000-4000-8000-000000000002'
const iso = (giayTuNow: number) => new Date(NOW + giayTuNow * 1000).toISOString()

const user = (roles: string[]): UserInfo => ({ username: 'u', displayName: 'U', roles })
const wf = (buoc: string, trangThai = 'RUNNING', doiId: string | null = DOI1): TrangThaiWf => ({
  workflowId: `phan-cong-${INC}`, trangThai, buoc, doiId, doiTen: 'Đội xung kích thôn 1', khoangCachM: 432,
  hanNhanGiay: 300, ketQua: null, daBaoDieuPhoi: false, nguoiXacNhan: null, lichSu: [],
})
const hang = (o: Record<string, unknown> = {}) => ({
  id: INC,
  location: { type: 'Point', coordinates: [108.1003, 15.8528] },
  urgency: 'khan_cap',
  status: 'phan_cong',
  created_at: iso(-600),
  updated_at: iso(-60),
  description: 'Nước dâng nhanh, 3 người trên mái',
  address_text: 'Thôn 1 (giả định)',
  people_count: 3,
  assigned_team: { name: 'Đội ca nô Biên phòng (giả định)' },
  assignments: [
    { attempt_no: 1, team_id: DOI1, distance_m: 432.4, assigned_at: iso(-500), deadline_at: iso(-200), result: 'tu_choi',
      responded_at: iso(-400), responded_by: 'cuuho01', note: 'ca nô đang sửa', team: null },
    { attempt_no: 2, team_id: DOI2, distance_m: 1890, assigned_at: iso(-120), deadline_at: iso(180), result: 'cho_nhan',
      responded_at: null, responded_by: null, note: null, team: { name: 'Đội ca nô Biên phòng (giả định)' } },
  ],
  ...o,
})
const tin = (n: number, urgency: MucKhan, status: TrangThai): TinPhanCong => ({
  ...(tinPhanCongTuHang(hang({ id: `d0000000-0000-4000-8000-${String(n).padStart(12, '0')}`, urgency, status, created_at: iso(-n * 60) }))!),
})

describe('vai trên màn phân công', () => {
  it('điều phối ưu tiên hơn cứu hộ; vai khác không vào được', () => {
    expect(vaiPhanCong(user(['cuu-ho', 'dieu-phoi']))).toBe('dieu-phoi')
    expect(vaiPhanCong(user(['cuu-ho']))).toBe('cuu-ho')
    expect(vaiPhanCong(user(['tinh-nguyen']))).toBeNull()
    expect(vaiPhanCong(null)).toBeNull()
  })
})

describe('GraphQL hàng đợi và chi tiết', () => {
  it('hàng đợi không bao giờ hỏi SĐT, tên người báo', () => {
    expect(Q_HANG_PHAN_CONG).not.toMatch(/reporter_phone|reporter_name/)
    expect(Q_HANG_PHAN_CONG).toContain('assignments(')
  })
  it('chi tiết chỉ hỏi cột liên hệ với vai được Hasura cho đọc', () => {
    expect(queryTinPhanCong('dieu-phoi')).toContain('reporter_phone')
    expect(queryTinPhanCong('cuu-ho')).toContain('reporter_phone')
    expect(queryTinPhanCong('tinh-nguyen')).not.toContain('reporter_phone')
    expect(queryTinPhanCong(null)).not.toContain('reporter_phone')
  })
  it('hàng → tin kèm lịch sử giao; liên hệ chỉ có khi query có cột', () => {
    const t = tinPhanCongTuHang(hang())!
    expect(t.location).toEqual([108.1003, 15.8528])
    expect(t.doiTen).toBe('Đội ca nô Biên phòng (giả định)')
    expect(t.giao.map((g) => `${g.lan}:${g.ketQua}:${g.doiTen}`)).toEqual(['1:tu_choi:null', '2:cho_nhan:Đội ca nô Biên phòng (giả định)'])
    expect(t).not.toHaveProperty('reporter_phone')
    expect(tinPhanCongTuHang(hang({ reporter_phone: '0900000001', reporter_name: null }))).toMatchObject({ reporter_phone: '0900000001', reporter_name: null })
  })
  it('bỏ hàng hỏng và lần giao hỏng, không làm vỡ màn hình', () => {
    expect(tinPhanCongTuHang(hang({ status: 'la' }))).toBeNull()
    expect(tinPhanCongTuHang(hang({ location: null }))).toBeNull()
    const t = tinPhanCongTuHang(hang({ assignments: [{ attempt_no: 1, result: 'la' }, null] }))!
    expect(t.giao).toEqual([])
    expect(hangTuKetQua({ incidents: [hang(), { id: 1 }] })).toHaveLength(1)
    expect(hangTuKetQua(null)).toEqual([])
  })
  it('lần giao đang chờ và lần giao cuối', () => {
    const t = tinPhanCongTuHang(hang())!
    expect(giaoDangCho(t)?.lan).toBe(2)
    expect(giaoCuoi(t)?.lan).toBe(2)
    expect(giaoDangCho({ giao: [] })).toBeNull()
  })
})

describe('nhóm tin', () => {
  const DS = [tin(1, 'thap', 'tiep_nhan'), tin(2, 'khan_cap', 'phan_cong'), tin(3, 'cao', 'dang_cuu'),
    tin(4, 'khan_cap', 'tiep_nhan'), tin(5, 'cao', 'da_cuu')]
  it('theo trạng thái, khẩn hơn trước; tin đã cứu không vào hàng đợi', () => {
    const n = nhomTin(DS)
    expect(n.cho_phan_cong.map((t) => t.id.slice(-1))).toEqual(['4', '1'])
    expect(n.cho_doi_nhan.map((t) => t.id.slice(-1))).toEqual(['2'])
    expect(n.dang_cuu.map((t) => t.id.slice(-1))).toEqual(['3'])
    expect(n.can_xu_ly).toEqual([])
  })
  it('thông báo "cần xử lý" kéo tin tiep_nhan/dang_cuu lên nhóm riêng, tin đã được giao lại thì thôi', () => {
    const n = nhomTin(DS, new Set([DS[0]!.id, DS[1]!.id, DS[2]!.id]))
    expect(n.can_xu_ly.map((t) => t.id.slice(-1))).toEqual(['3', '1'])
    expect(n.cho_doi_nhan.map((t) => t.id.slice(-1))).toEqual(['2'])
  })
  it('cứu hộ chỉ thấy nhóm chờ nhận và đang thực hiện', () => {
    expect(NHOM_THEO_VAI['cuu-ho']).toEqual(['cho_doi_nhan', 'dang_cuu'])
    expect(NHOM_THEO_VAI['dieu-phoi'][0]).toBe('can_xu_ly')
  })
})

describe('trạng thái workflow', () => {
  it('đọc phản hồi GET /workflow/{id}', () => {
    const w = wfTuPhanHoi({ workflow_id: `phan-cong-${INC}`, trang_thai: 'RUNNING', chi_tiet: {
      incident_id: INC, buoc: 'cho_nhan', doi_id: DOI1, doi_ten: 'Đội 1', khoang_cach_m: 432.4, han_nhan_giay: 300,
      ket_qua: null, xac_nhan: { nguoi: 'cuuho01' }, lich_su: ['a', 1, 'b'], da_bao_dieu_phoi: true, giao: [] } })!
    expect(w).toMatchObject({ trangThai: 'RUNNING', buoc: 'cho_nhan', doiId: DOI1, khoangCachM: 432.4, nguoiXacNhan: 'cuuho01',
      daBaoDieuPhoi: true, lichSu: ['a', 'b'] })
    expect(wfTuPhanHoi({ detail: 'x' })).toBeNull()
    expect(wfTuPhanHoi(null)).toBeNull()
  })
})

describe('nút theo vai (khớp luật của API)', () => {
  const tn = { status: 'tiep_nhan' as const }
  const pc = { status: 'phan_cong' as const }
  const dc = { status: 'dang_cuu' as const }
  it('điều phối: phân công tay khi tin tiep_nhan và không có luồng đang chạy', () => {
    expect(hanhDongDuoc('dieu-phoi', tn, null)).toEqual(['phan_cong'])
    expect(hanhDongDuoc('dieu-phoi', tn, wf('xong', 'COMPLETED'))).toEqual(['phan_cong'])
    // Đang tìm đội: không khởi chạy thêm (API trả 409), chỉ hủy được
    expect(hanhDongDuoc('dieu-phoi', tn, wf('tim_doi'))).toEqual(['huy'])
  })
  it('điều phối: đổi đội và hủy khi chờ nhận; xác nhận khi đang cứu; không hủy khi đội đã nhận', () => {
    expect(hanhDongDuoc('dieu-phoi', pc, wf('cho_nhan'))).toEqual(['doi_doi', 'huy'])
    expect(hanhDongDuoc('dieu-phoi', dc, wf('cho_xac_nhan'))).toEqual(['xac_nhan'])
    expect(hanhDongDuoc('dieu-phoi', dc, wf('xong', 'COMPLETED'))).toEqual([])
  })
  it('cứu hộ: nhận/từ chối khi chờ nhận, xác nhận khi đang cứu; không bao giờ phân công, đổi đội, hủy', () => {
    expect(hanhDongDuoc('cuu-ho', pc, wf('cho_nhan'))).toEqual(['nhan', 'tu_choi'])
    expect(hanhDongDuoc('cuu-ho', dc, wf('cho_xac_nhan'))).toEqual(['xac_nhan'])
    expect(hanhDongDuoc('cuu-ho', tn, null)).toEqual([])
    expect(hanhDongDuoc('cuu-ho', pc, wf('cho_nhan', 'COMPLETED'))).toEqual([])
    for (const b of ['tim_doi', 'cho_nhan', 'cho_xac_nhan']) {
      expect(hanhDongDuoc('cuu-ho', pc, wf(b))).not.toContain('huy')
      expect(hanhDongDuoc('cuu-ho', pc, wf(b))).not.toContain('doi_doi')
    }
  })
  it('vai khác không có nút nào', () => {
    expect(hanhDongDuoc(null, pc, wf('cho_nhan'))).toEqual([])
  })
  it('ghi chú đổi đội ghi rõ do điều phối, không quá 500 ký tự', () => {
    expect(ghiChuDoiDoi('  đội ở xa ')).toBe('Điều phối đổi đội: đội ở xa')
    expect(ghiChuDoiDoi('')).toBe('Điều phối đổi đội')
    expect(ghiChuDoiDoi('x'.repeat(600))).toHaveLength(500)
  })
})

describe('hiển thị', () => {
  it('đếm ngược hạn nhận', () => {
    expect(demNguoc(iso(245), NOW)).toMatchObject({ nhan: '4:05', gap: false })
    expect(demNguoc(iso(3723), NOW).nhan).toBe('1:02:03')
    expect(demNguoc(iso(30), NOW)).toMatchObject({ nhan: '0:30', gap: true })
    expect(demNguoc(iso(-1), NOW)).toEqual({ conLaiMs: 0, nhan: 'Quá hạn', gap: true })
    expect(demNguoc('hong', NOW).nhan).toBe('Quá hạn')
  })
  it('tỉ lệ thời gian nhận đã qua', () => {
    expect(tiLeDaQua({ giaoLuc: iso(-100), hanLuc: iso(100) }, NOW)).toBe(0.5)
    expect(tiLeDaQua({ giaoLuc: iso(-100), hanLuc: iso(-10) }, NOW)).toBe(1)
    expect(tiLeDaQua({ giaoLuc: iso(10), hanLuc: iso(100) }, NOW)).toBe(0)
  })
  it('khoảng cách và tóm tắt lần giao', () => {
    expect(khoangCach(432.4)).toBe('432 m')
    expect(khoangCach(1890)).toBe('1,9 km')
    expect(khoangCach(null)).toBe('chưa rõ')
    const t = tinPhanCongTuHang(hang())!
    expect(tomTatGiao(t)).toBe('Đội ca nô Biên phòng (giả định) · cách 1,9 km · lần giao 2')
    expect(tomTatGiao({ ...t, giao: [] , status: 'tiep_nhan' })).toBe('Chưa giao đội nào')
    expect(tomTatGiao({ ...t, giao: [t.giao[0]!], doiTen: null })).toBe('đội khác: từ chối')
  })
})
