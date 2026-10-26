// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest'
import {
  bodyTuForm, docSo, formTuBody, hangChoTuKetQua, hienGiaTri, loiTheoTruong, mucTuHang, oToaDo, phanTichLoi,
  queryHangCho, sapXepHangCho, toaDoForm, truongDaSua, type MucHangCho,
} from '~/utils/hang-cho'

const ID = '7d000000-0000-4000-8000-000000000001'
const INC = 'b0000000-0000-4000-8000-000000000009'

/** Một hàng GraphQL ai_intake_reviews như Hasura trả cho vai dieu-phoi */
function hang(over: Record<string, unknown> = {}) {
  return {
    id: ID,
    status: 'cho_duyet',
    raw_text: 'Cuu voi, nha o thon 3 ngap toi mai, 4 nguoi, goi 0905 111 222',
    text_source: 'zalo',
    created_at: '2026-10-26T01:00:00+00:00',
    submitted_by_name: 'tinhnguyen01',
    submitted_role: 'tinh-nguyen',
    ai_urgency: 'khan_cap',
    ai_valid: false,
    ai_provider: 'ollama',
    ai_model: 'qwen2.5:7b',
    ai_fallback: false,
    ai_duration_ms: 11500,
    ai_result: {
      de_xuat: { urgency: 'khan_cap', nhu_cau: ['cuu_nguoi', 3] },
      tin_keu_cuu: { reporter_phone: '0905111222', people_count: 4, urgency: 'khan_cap', description: 'Ngập tới mái', source: 'mang_xa_hoi', lat: null },
      poka_yoke: { hop_le: false, loi: [{ truong: 'lat', thong_bao: 'Thiếu vĩ độ' }, { truong: 'lon', thong_bao: 'Thiếu kinh độ' }, { x: 1 }], tin_trung: null },
      ai: { nha_cung_cap: 'ollama' },
      canh_bao: ['Mô hình đưa SĐT không có trong tin (đã bỏ)', 7],
    },
    reviewed_at: null,
    reviewed_by_name: null,
    incident_id: null,
    cancel_reason: null,
    edited_fields: null,
    final_body: null,
    ...over,
  }
}

describe('đọc hàng chờ từ Hasura', () => {
  it('query theo trạng thái, đếm số chờ duyệt, thứ tự đúng', () => {
    expect(queryHangCho('cho_duyet')).toContain('order_by: {created_at: asc}')
    expect(queryHangCho('da_duyet')).toContain('order_by: {reviewed_at: desc}')
    expect(queryHangCho('da_huy')).toContain('ai_intake_reviews_aggregate(where: {status: {_eq: "cho_duyet"}})')
  })

  it('hàng → MucHangCho: đề xuất dạng body /keu-cuu, bỏ giá trị lạ', () => {
    const m = mucTuHang(hang())!
    expect(m).toMatchObject({
      id: ID, trangThai: 'cho_duyet', nguon: 'zalo', urgency: 'khan_cap', hopLe: false, nguoiGui: 'tinhnguyen01',
      ai: { nhaCungCap: 'ollama', moHinh: 'qwen2.5:7b', duPhong: false, thoiGianMs: 11500 },
      nhuCau: ['cuu_nguoi'], tinTrung: null, canhBao: ['Mô hình đưa SĐT không có trong tin (đã bỏ)'],
      duyetLuc: null, truongDaSua: null, tinCuoi: null,
    })
    // lat: null không vào body; loi thiếu trường bị bỏ
    expect(m.deXuat).toEqual({ reporter_phone: '0905111222', people_count: 4, urgency: 'khan_cap', description: 'Ngập tới mái', source: 'mang_xa_hoi' })
    expect(m.loi.map((x) => x.truong)).toEqual(['lat', 'lon'])
  })

  it('đã duyệt: vết duyệt, trường sửa, tin cuối', () => {
    const m = mucTuHang(hang({
      status: 'da_duyet', reviewed_at: '2026-10-26T01:05:00+00:00', reviewed_by_name: 'dieuphoi01', incident_id: INC,
      edited_fields: { lat: { ai: null, nguoi: 16.07 } }, final_body: { lat: 16.07, lon: 108.15 },
    }))!
    expect(m).toMatchObject({ trangThai: 'da_duyet', nguoiDuyet: 'dieuphoi01', incidentId: INC, truongDaSua: { lat: { ai: null, nguoi: 16.07 } } })
    expect(m.tinCuoi).toEqual({ lat: 16.07, lon: 108.15 })
  })

  it('tin trùng từ Poka-yoke lúc bóc tách', () => {
    const m = mucTuHang(hang({ ai_result: { de_xuat: {}, tin_keu_cuu: {}, poka_yoke: { tin_trung: { incident_id: INC, khoang_cach_m: 120, thong_bao: 'trùng' } } } }))!
    expect(m.tinTrung).toEqual({ incident_id: INC, khoang_cach_m: 120, thong_bao: 'trùng' })
  })

  it('hàng hỏng bị bỏ, kết quả rỗng an toàn', () => {
    expect(mucTuHang(null)).toBeNull()
    expect(mucTuHang(hang({ status: 'la' }))).toBeNull()
    expect(mucTuHang(hang({ raw_text: 1 }))).toBeNull()
    expect(hangChoTuKetQua(null)).toEqual({ ds: [], soChoDuyet: 0 })
    const kq = hangChoTuKetQua({ ai_intake_reviews: [hang(), { id: 1 }], cho: { aggregate: { count: 3 } } })
    expect(kq.ds).toHaveLength(1)
    expect(kq.soChoDuyet).toBe(3)
  })

  it('hàng chờ: khẩn trước, cùng mức thì cũ trước; đã xử lý giữ thứ tự', () => {
    const m = (id: string, urgency: string, t: string, status = 'cho_duyet') =>
      mucTuHang(hang({ id, ai_urgency: urgency, created_at: t, status, reviewed_at: status === 'cho_duyet' ? null : t, reviewed_by_name: 'x' }))!
    const ds = [m('a', 'thap', '2026-10-26T01:00:00Z'), m('b', 'khan_cap', '2026-10-26T03:00:00Z'), m('c', 'khan_cap', '2026-10-26T02:00:00Z')]
    expect(sapXepHangCho(ds).map((x) => x.id)).toEqual(['c', 'b', 'a'])
    const xong = [m('x', 'thap', '2026-10-26T05:00:00Z', 'da_duyet'), m('y', 'khan_cap', '2026-10-26T04:00:00Z', 'da_duyet')]
    expect(sapXepHangCho(xong).map((x: MucHangCho) => x.id)).toEqual(['x', 'y'])
  })
})

describe('form sửa đề xuất ↔ body /keu-cuu', () => {
  const deXuat = { reporter_phone: '0905111222', people_count: 4, urgency: 'khan_cap', description: 'Ngập tới mái', source: 'mang_xa_hoi' }

  it('form từ đề xuất: ô trống cho trường AI không thấy, mức khẩn mặc định trung bình', () => {
    const f = formTuBody(deXuat)
    expect(f).toMatchObject({ reporter_phone: '0905111222', people_count: '4', lat: '', lon: '', reporter_name: '' })
    expect(formTuBody({}).urgency).toBe('trung_binh')
  })

  it('đọc số: dấu phẩy thập phân kiểu Việt, chữ → NaN, trống → null', () => {
    expect(docSo('16,0712')).toBe(16.0712)
    expect(docSo(' 108.15 ')).toBe(108.15)
    expect(docSo('-3')).toBe(-3)
    expect(docSo('')).toBeNull()
    expect(docSo('16°04')).toBeNaN()
    expect(docSo('1e3')).toBeNaN()
  })

  it('body đầy đủ, số là số, bỏ ô trống', () => {
    const f = { ...formTuBody(deXuat), lat: '16,0712', lon: '108.1503', address_text: '  thôn 3  ' }
    const { body, loi } = bodyTuForm(f)
    expect(loi).toEqual([])
    expect(body).toEqual({ ...deXuat, lat: 16.0712, lon: 108.1503, address_text: 'thôn 3' })
  })

  it('báo sớm: thiếu tọa độ, số sai, số người lẻ, thiếu SĐT/mô tả, quá dài', () => {
    const { loi } = bodyTuForm({ ...formTuBody({}), lon: 'abc', people_count: '2.5', reporter_name: 'x'.repeat(101) })
    const truong = loi.map((x) => x.truong)
    expect(truong).toEqual(expect.arrayContaining(['lat', 'lon', 'people_count', 'reporter_phone', 'description', 'reporter_name']))
    expect(loi.find((x) => x.truong === 'lat')!.thong_bao).toMatch(/chọn vị trí trên bản đồ/)
    expect(loi.find((x) => x.truong === 'lon')!.thong_bao).toMatch(/phải là số/)
  })

  it('trường đã sửa: so sau chuẩn hóa (SĐT có dấu cách/+84, số 16.0 = 16)', () => {
    const goc = { ...formTuBody(deXuat), lat: '16', lon: '108' }
    expect(truongDaSua({ ...goc, reporter_phone: '+84 905 111 222', lat: '16.0', lon: '108,0' }, goc)).toEqual([])
    expect(truongDaSua({ ...goc, people_count: '5', urgency: 'cao', address_text: 'thôn 3' }, goc))
      .toEqual(['address_text', 'people_count', 'urgency'])
  })

  it('tọa độ form ↔ bản đồ', () => {
    expect(toaDoForm({ ...formTuBody({}), lat: '16,07', lon: '108.15' })).toEqual([108.15, 16.07])
    expect(toaDoForm({ ...formTuBody({}), lat: '95', lon: '108' })).toBeNull()
    expect(toaDoForm(formTuBody({}))).toBeNull()
    expect(oToaDo({ lng: 108.1503333, lat: 16.07121 })).toEqual({ lat: '16.071210', lon: '108.150333' })
  })

  it('lỗi theo trường: câu đầu tiên mỗi trường, trường lạ gom vào body', () => {
    expect(loiTheoTruong([
      { truong: 'lat', thong_bao: 'a' }, { truong: 'lat', thong_bao: 'b' }, { truong: 'tin_keu_cuu', thong_bao: 'c' },
    ])).toEqual({ lat: 'a', body: 'c' })
    expect(hienGiaTri(null)).toBe('(trống)')
    expect(hienGiaTri(4)).toBe('4')
  })
})

describe('lỗi API → câu tiếng Việt', () => {
  it('409 tin trùng: mã tin đang mở + gợi ý hủy với lý do trùng', () => {
    const p = phanTichLoi({ status: 409, detail: { ma: 'tin_trung', thong_bao: 'Số này đã báo cách 80 m.', incident_id: INC } }, 'duyet')
    expect(p.tinTrungId).toBe(INC)
    expect(p.thongBao).toMatch(/80 m.*Trùng tin kêu cứu đã có/)
  })
  it('409 đã xử lý: tải lại hàng chờ', () => {
    const p = phanTichLoi({ status: 409, detail: { ma: 'da_xu_ly', thong_bao: 'Tin này đã được duyệt bởi dieuphoi02.' } }, 'duyet')
    expect(p).toMatchObject({ daXuLy: true, thongBao: 'Tin này đã được duyệt bởi dieuphoi02.' })
  })
  it('422 theo trường của Poka-yoke', () => {
    const p = phanTichLoi({ status: 422, detail: { ma: 'du_lieu_khong_hop_le', loi: [{ truong: 'lat', thong_bao: 'Vị trí nằm ngoài vùng phục vụ' }] } }, 'duyet')
    expect(p.loi).toEqual([{ truong: 'lat', thong_bao: 'Vị trí nằm ngoài vùng phục vụ' }])
    expect(p.thongBao).toMatch(/trường được đánh dấu/)
    expect(phanTichLoi({ status: 422, detail: { loi: [{ truong: 'van_ban', thong_bao: 'Thiếu văn bản' }] } }, 'boc_tach').thongBao).toBe('Thiếu văn bản')
    expect(phanTichLoi({ status: 422, detail: {} }, 'huy').thongBao).toMatch(/500 ký tự/)
  })
  it('mất mạng, hết phiên, không quyền, không còn, quá nhanh, AI tắt, máy chủ lỗi', () => {
    expect(phanTichLoi({ status: 0, detail: '' }, 'duyet').thongBao).toMatch(/Không kết nối/)
    expect(phanTichLoi({ status: 401, detail: '' }, 'duyet').thongBao).toMatch(/đăng nhập/)
    expect(phanTichLoi({ status: 403, detail: '' }, 'huy').thongBao).toMatch(/không có quyền/)
    expect(phanTichLoi({ status: 404, detail: {} }, 'duyet').thongBao).toMatch(/Không còn/)
    expect(phanTichLoi({ status: 429, detail: '' }, 'boc_tach').thongBao).toMatch(/quá nhanh/)
    expect(phanTichLoi({ status: 503, detail: '' }, 'boc_tach').thongBao).toMatch(/AI bóc tách đang tắt/)
    expect(phanTichLoi({ status: 502, detail: '' }, 'duyet').thongBao).toMatch(/HTTP 502/)
  })
})
