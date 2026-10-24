// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest'
import {
  TRANG_THAI_PHIEU, chuanHoaMa, docPhanHoi, laMaHopLe, loiKhiTra, moTaMuc, mucSoCaiTuPhanHoi, quyTuPhanHoi, tieuDeKetQua,
  urlKhoaSoCai, urlQuy, urlSoCai, urlXacMinh,
} from '~/utils/minh-bach'

const MA = '3f6c2a10-8b4d-4e2f-9a1c-5d7e8f901234'
// Phản hồi mẫu của GET /workflow/minh-bach/xac-minh/{ma} — dữ liệu giả
const phanHoi = (trangThai: string, loai = 'phieu_kho') => ({
  hop_le: trangThai === 'da_xac_minh', loai, ma: MA, trang_thai: trangThai, chi_tiet: ['Bản ghi khớp lá trên sổ cái'],
  ban_ghi_chuan_hoa: loai === 'phieu_kho'
    ? { loai: 'cuu-tro.phieu-kho/v1', id: MA, direction: 'xuat', quantity: '250', note: null, created_at: '2026-10-23T02:00:00Z' }
    : { loai: 'cuu-tro.khoan-tien/v1', id: MA, direction: 'thu', amount: '50000000', currency: 'VND', category: 'ung_ho', purpose: null, created_at: '2026-10-23T02:00:00Z' },
  sha256: 'ab',
  hien_thi: loai === 'phieu_kho' ? { mat_hang: 'Nước uống', don_vi: 'thùng', kho: 'Kho xã', diem_nhan: null } : { hang_muc: 'ung_ho', don_vi: 'VND', diem_nhan: null },
  so_cai: { index: 11, leaf_hash: 'cd', logged_at: '2026-10-23T02:01:00Z', checkpoint: null, la: '{}' },
  bang_chung: { leaf_index: 11, leaf_hash: 'cd', tree_size: 12, inclusion_proof: ['ef'], checkpoint: 'x\n12\nAA==\n\n— x AA==\n' },
  tu_kiem_chung: 'go run …',
})

describe('mã tra cứu', () => {
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
  it('URL qua gateway: một đường xác minh cho cả phiếu kho và bút toán, khóa sổ cái, sổ cái, quỹ', () => {
    expect(urlXacMinh('http://localhost:9080/', ` ${MA} `)).toBe(`http://localhost:9080/workflow/minh-bach/xac-minh/${MA}`)
    expect(urlKhoaSoCai('http://localhost:9080')).toBe('http://localhost:9080/ledger/verifier')
    expect(urlSoCai('http://localhost:9080', 5)).toBe('http://localhost:9080/workflow/minh-bach/so-cai?gioi_han=5')
    expect(urlQuy('http://localhost:9080/')).toBe('http://localhost:9080/workflow/minh-bach/quy')
  })
})

describe('ánh xạ phản hồi API → hiển thị', () => {
  it('200 với đủ 4 trạng thái xác minh, cả hai loại mã', () => {
    for (const loai of ['phieu_kho', 'khoan_tien']) {
      for (const tt of Object.keys(TRANG_THAI_PHIEU)) {
        const r = docPhanHoi(200, phanHoi(tt, loai))
        expect(r.ok).toBe(true)
        if (r.ok) expect([r.kq.trang_thai, r.kq.loai]).toEqual([tt, loai])
      }
    }
  })
  it('chưa ghi sổ: bằng chứng null vẫn hợp lệ; bằng chứng sai dạng thì không', () => {
    expect(docPhanHoi(200, { ...phanHoi('chua_ghi_so'), bang_chung: null }).ok).toBe(true)
    const r = docPhanHoi(200, { ...phanHoi('chua_ghi_so'), bang_chung: undefined })
    expect(r.ok && r.kq.bang_chung).toBeNull()
    expect(docPhanHoi(200, { ...phanHoi('da_xac_minh'), bang_chung: { leaf_index: '1' } }).ok).toBe(false)
  })
  it('mỗi trạng thái có nhãn, màu, biểu tượng khác nhau', () => {
    const ds = Object.values(TRANG_THAI_PHIEU)
    expect(new Set(ds.map((x) => x.icon)).size).toBe(4)
    expect(new Set(ds.map((x) => x.mau)).size).toBe(4)
  })
  it('trạng thái hoặc loại lạ, thiếu trường → báo phản hồi sai dạng, không hiện kết quả', () => {
    expect(docPhanHoi(200, phanHoi('gia_mao')).ok).toBe(false)
    expect(docPhanHoi(200, phanHoi('da_xac_minh', 'loai_la')).ok).toBe(false)
    expect(docPhanHoi(200, { trang_thai: 'da_xac_minh' }).ok).toBe(false)
    expect(docPhanHoi(200, null).ok).toBe(false)
  })
  it('lỗi HTTP thành câu tiếng Việt', () => {
    expect(docPhanHoi(404, { detail: 'x' })).toEqual({ ok: false, loi: expect.stringContaining('phiếu hay bút toán') })
    expect(docPhanHoi(429, null)).toEqual({ ok: false, loi: expect.stringContaining('quá nhanh') })
    expect(docPhanHoi(502, null)).toEqual({ ok: false, loi: expect.stringContaining('502') })
    expect(docPhanHoi(400, null)).toEqual({ ok: false, loi: 'Máy chủ trả lỗi 400.' })
  })
  it('mất mạng có câu riêng', () => {
    expect(loiKhiTra(new TypeError('Failed to fetch'))).toContain('Không kết nối được')
    expect(loiKhiTra(new Error('x'))).toBe('x')
  })
  it('tiêu đề kết quả: hàng (số lượng + đơn vị + mặt hàng) và tiền (đồng)', () => {
    const p = docPhanHoi(200, phanHoi('da_xac_minh'))
    const t = docPhanHoi(200, phanHoi('da_xac_minh', 'khoan_tien'))
    expect(p.ok && tieuDeKetQua(p.kq)).toEqual({ so: '250', donVi: 'thùng', noiDung: 'Nước uống' })
    expect(t.ok && tieuDeKetQua(t.kq)).toEqual({ so: '50.000.000', donVi: 'đ', noiDung: '' })
  })
})

describe('quỹ và sổ cái gần đây', () => {
  const muc = (o: Record<string, unknown>) => ({
    loai: 'phieu_kho', ma: MA, chieu: 'xuat', so_luong: '40', don_vi: 'thùng', noi_dung: 'Mì tôm', diem_nhan: 'Trường THCS',
    thoi_diem: '2026-10-24T02:00:00Z', ledger_index: 7, ...o,
  })
  it('lọc mục hỏng, mô tả ngắn từng loại', () => {
    const ds = mucSoCaiTuPhanHoi({ muc: [muc({}), muc({ ma: 'x' }), muc({ loai: 'khoan_tien', chieu: 'thu', so_luong: '50000000', don_vi: 'VND', noi_dung: 'ung_ho', diem_nhan: null })] })
    expect(ds).toHaveLength(2)
    expect(moTaMuc(ds[0]!)).toBe('Xuất 40 thùng Mì tôm → Trường THCS')
    expect(moTaMuc(ds[1]!)).toBe('Thu 50.000.000 đ · Ủng hộ')
    expect(mucSoCaiTuPhanHoi(null)).toEqual([])
  })
  it('tổng hợp quỹ', () => {
    expect(quyTuPhanHoi({ don_vi: 'VND', tong_thu: '10', tong_chi: '4', so_du: '6', khoan_tien_da_niem_phong: 2 }))
      .toEqual({ don_vi: 'VND', tong_thu: '10', tong_chi: '4', so_du: '6' })
    expect(quyTuPhanHoi({ tong_thu: 10 })).toBeNull()
  })
})
