// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest'
import {
  DS_MUC_KHAN, DS_TRANG_THAI, THOI_GIAN_TIN_MOI_MS, batTat, boLocMacDinh, capNhatTinMoi, cheSdt, demTheoMucKhan,
  demTheoTrangThai, locTin, maNgan, noiTinMoi, sapXepTin, thoiGianTruoc, type MucKhan, type TinKeuCuu, type TrangThai,
} from '~/utils/tin'

const NOW = Date.parse('2026-10-29T08:00:00Z')
const tin = (n: number, urgency: MucKhan, status: TrangThai, phut: number): TinKeuCuu => ({
  id: `d0000000-0000-4000-8000-${String(n).padStart(12, '0')}`,
  location: [108.2 + n / 100, 15.9],
  urgency, status,
  created_at: new Date(NOW - phut * 60_000).toISOString(),
})
const DS = [
  tin(1, 'trung_binh', 'tiep_nhan', 5),
  tin(2, 'khan_cap', 'phan_cong', 3),
  tin(3, 'khan_cap', 'tiep_nhan', 10),
  tin(4, 'thap', 'da_cuu', 60),
  tin(5, 'cao', 'dong', 90),
  tin(6, 'cao', 'dang_cuu', 20),
]

describe('sắp xếp và đếm', () => {
  it('chưa xong trước, khẩn hơn trước, cũ hơn trước', () => {
    expect(sapXepTin(DS).map((t) => t.id.slice(-1))).toEqual(['3', '2', '6', '1', '5', '4'])
  })
  it('đếm theo trạng thái và mức khẩn', () => {
    expect(demTheoTrangThai(DS)).toEqual({ tiep_nhan: 2, phan_cong: 1, dang_cuu: 1, da_cuu: 1, dong: 1 })
    expect(demTheoMucKhan(DS)).toEqual({ khan_cap: 2, cao: 2, trung_binh: 1, thap: 1 })
  })
})

describe('bộ lọc', () => {
  it('mặc định: mọi mức khẩn, ẩn tin đã đóng', () => {
    const loc = boLocMacDinh()
    expect(loc.mucKhan).toEqual(DS_MUC_KHAN)
    expect(loc.trangThai).toEqual(['tiep_nhan', 'phan_cong', 'dang_cuu', 'da_cuu'])
    expect(locTin(DS, loc).map((t) => t.status)).not.toContain('dong')
    expect(locTin(DS, loc)).toHaveLength(5)
  })
  it('lọc theo trạng thái và mức khẩn cùng lúc (AND), giữ thứ tự đầu vào', () => {
    const r = locTin(DS, { trangThai: ['tiep_nhan', 'phan_cong'], mucKhan: ['khan_cap'] })
    expect(r.map((t) => t.id.slice(-1))).toEqual(['2', '3'])
    expect(locTin(DS, { trangThai: [], mucKhan: DS_MUC_KHAN })).toEqual([])
  })
  it('bật/tắt giữ thứ tự gốc, bỏ qua giá trị lạ', () => {
    expect(batTat(['tiep_nhan', 'dang_cuu'], 'phan_cong', DS_TRANG_THAI)).toEqual(['tiep_nhan', 'phan_cong', 'dang_cuu'])
    expect(batTat(['tiep_nhan', 'dang_cuu'], 'tiep_nhan', DS_TRANG_THAI)).toEqual(['dang_cuu'])
    const cu: MucKhan[] = ['cao']
    expect(batTat(cu, 'khong_co' as MucKhan, DS_MUC_KHAN)).toBe(cu)
  })
  it('không sửa bộ lọc mặc định giữa các lần gọi', () => {
    boLocMacDinh().trangThai.push('dong')
    expect(boLocMacDinh().trangThai).not.toContain('dong')
  })
})

describe('tin mới', () => {
  it('kết quả đầu tiên chỉ ghi nhận, không đánh dấu mới', () => {
    const r = capNhatTinMoi(new Set(), new Map(), DS, true, NOW)
    expect(r.moi.size).toBe(0)
    expect(r.daBiet.size).toBe(DS.length)
  })
  it('tin xuất hiện sau đó được đánh dấu mới, hết hạn sau 60 giây hoặc khi biến mất', () => {
    const dau = capNhatTinMoi(new Set(), new Map(), DS.slice(0, 3), true, NOW)
    const sau = capNhatTinMoi(dau.daBiet, dau.moi, DS, false, NOW + 1000)
    expect([...sau.moi.keys()].map((id) => id.slice(-1)).sort()).toEqual(['4', '5', '6'])
    // Kết quả kế tiếp: tin 4 bị lọc khỏi kết quả (vd đổi quyền), tin còn lại giữ mốc cũ
    const tiep = capNhatTinMoi(sau.daBiet, sau.moi, DS.filter((t) => !t.id.endsWith('4')), false, NOW + 2000)
    expect([...tiep.moi.keys()].map((id) => id.slice(-1)).sort()).toEqual(['5', '6'])
    expect(tiep.moi.get(DS[4]!.id)).toBe(NOW + 1000)
    const het = capNhatTinMoi(tiep.daBiet, tiep.moi, DS, false, NOW + 1000 + THOI_GIAN_TIN_MOI_MS)
    expect(het.moi.size).toBe(0)
  })
  it('tin đã biết rồi biến mất rồi quay lại không tính là mới', () => {
    const dau = capNhatTinMoi(new Set(), new Map(), DS, true, NOW)
    const mat = capNhatTinMoi(dau.daBiet, dau.moi, DS.slice(1), false, NOW + 1)
    expect(capNhatTinMoi(mat.daBiet, mat.moi, DS, false, NOW + 2).moi.size).toBe(0)
  })
  it('tin mới nổi lên đầu danh sách, mới nhất trước', () => {
    const moi = new Map([[DS[3]!.id, NOW + 1], [DS[0]!.id, NOW + 5]])
    expect(noiTinMoi(sapXepTin(DS), moi).map((t) => t.id.slice(-1))).toEqual(['1', '4', '3', '2', '6', '5'])
    expect(noiTinMoi(DS, new Map())).toEqual(DS)
  })
})

describe('hiển thị', () => {
  it('thời gian tương đối, che SĐT, mã ngắn', () => {
    expect(thoiGianTruoc(new Date(NOW - 20_000).toISOString(), NOW)).toBe('vừa xong')
    expect(thoiGianTruoc(new Date(NOW - 5 * 60_000).toISOString(), NOW)).toBe('5 phút trước')
    expect(thoiGianTruoc(new Date(NOW - 3 * 3_600_000).toISOString(), NOW)).toBe('3 giờ trước')
    expect(thoiGianTruoc(new Date(NOW - 50 * 3_600_000).toISOString(), NOW)).toBe('2 ngày trước')
    expect(cheSdt('0900000001')).toBe('0900***001')
    expect(maNgan(DS[0]!.id)).toBe('d0000000')
  })
})
