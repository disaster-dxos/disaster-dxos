// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest'
import { TRANG_THAI_PHIEU, chuanHoaMa, docPhanHoi, laMaHopLe, loiKhiTra, urlTraPhieu } from '~/utils/minh-bach'

const MA = '3f6c2a10-8b4d-4e2f-9a1c-5d7e8f901234'
const phanHoi = (trangThai: string) => ({
  ma: MA, trang_thai: trangThai, chi_tiet: ['Bản ghi khớp lá trên sổ cái'],
  ban_ghi_chuan_hoa: { direction: 'xuat', quantity: '250', note: null, created_at: '2026-10-23T02:00:00Z' },
  sha256: 'ab', hien_thi: { mat_hang: 'Nước uống', don_vi: 'thùng', kho: 'Kho xã', diem_nhan: null },
  so_cai: { index: 11, logged_at: '2026-10-23T02:01:00Z', checkpoint: null }, tu_kiem_chung: 'go run …',
})

describe('mã phiếu', () => {
  it('chuẩn hóa: bỏ khoảng trắng, chữ thường', () => {
    expect(chuanHoaMa(` ${MA.toUpperCase().replace('-', ' - ')} \n`)).toBe(MA)
  })
  it('chỉ nhận UUID', () => {
    expect(laMaHopLe(MA)).toBe(true)
    expect(laMaHopLe(MA.toUpperCase())).toBe(true)
    expect(laMaHopLe('3f6c2a10')).toBe(false)
    expect(laMaHopLe(`${MA}0`)).toBe(false)
    expect(laMaHopLe('../../admin')).toBe(false)
  })
  it('URL qua gateway, bỏ dấu / thừa', () => {
    expect(urlTraPhieu('http://localhost:9080/', ` ${MA} `)).toBe(`http://localhost:9080/workflow/minh-bach/phieu/${MA}`)
  })
})

describe('ánh xạ phản hồi API → hiển thị', () => {
  it('200 với đủ 4 trạng thái xác minh', () => {
    for (const tt of Object.keys(TRANG_THAI_PHIEU)) {
      const r = docPhanHoi(200, phanHoi(tt))
      expect(r.ok).toBe(true)
      if (r.ok) expect(r.kq.trang_thai).toBe(tt)
    }
  })
  it('mỗi trạng thái có nhãn, màu, biểu tượng khác nhau', () => {
    const ds = Object.values(TRANG_THAI_PHIEU)
    expect(new Set(ds.map((x) => x.icon)).size).toBe(4)
    expect(new Set(ds.map((x) => x.mau)).size).toBe(4)
  })
  it('trạng thái lạ hoặc thiếu trường → báo phản hồi sai dạng, không hiện kết quả', () => {
    expect(docPhanHoi(200, phanHoi('gia_mao')).ok).toBe(false)
    expect(docPhanHoi(200, { trang_thai: 'da_xac_minh' }).ok).toBe(false)
    expect(docPhanHoi(200, null).ok).toBe(false)
  })
  it('lỗi HTTP thành câu tiếng Việt', () => {
    expect(docPhanHoi(404, { detail: 'Không có phiếu này' })).toEqual({ ok: false, loi: expect.stringContaining('Không tìm thấy phiếu') })
    expect(docPhanHoi(429, null)).toEqual({ ok: false, loi: expect.stringContaining('quá nhanh') })
    expect(docPhanHoi(502, null)).toEqual({ ok: false, loi: expect.stringContaining('502') })
    expect(docPhanHoi(400, null)).toEqual({ ok: false, loi: 'Máy chủ trả lỗi 400.' })
  })
  it('mất mạng có câu riêng', () => {
    expect(loiKhiTra(new TypeError('Failed to fetch'))).toContain('Không kết nối được')
    expect(loiKhiTra(new Error('x'))).toBe('x')
  })
})
