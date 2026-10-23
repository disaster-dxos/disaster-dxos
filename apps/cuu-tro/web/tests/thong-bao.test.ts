// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest'
import { docThongBao, themThongBao, tokenUrl, wsUrl, type ThongBao } from '../utils/thong-bao'
import { maNgan } from '../utils/tin'

const INC = 'b0000000-0000-4000-8000-000000000004'
const BAY_GIO = new Date('2026-10-22T10:00:00Z')

describe('URL realtime', () => {
  it('WebSocket đi qua gateway: http → ws, https → wss, bỏ đường/tham số cũ', () => {
    expect(wsUrl('http://localhost:9080')).toBe('ws://localhost:9080/realtime/websocket')
    expect(wsUrl('https://cuutro.example.vn/abc?x=1#y')).toBe('wss://cuutro.example.vn/realtime/websocket')
    expect(() => wsUrl('javascript:alert(1)')).toThrow()
  })

  it('token xin qua route /workflow của gateway', () => {
    expect(tokenUrl('http://localhost:9080/')).toBe('http://localhost:9080/workflow/realtime/token')
  })
})

describe('đọc thông báo', () => {
  it('cần xử lý: mã ngắn của tin, lý do tiếng Việt, mức khẩn', () => {
    const tb = docThongBao({ loai: 'can_xu_ly', id: 'S:1', incident_id: INC, ly_do: 'het_lan_giao',
      urgency: 'khan_cap', so_lan_giao: 3, luc: '2026-10-22T09:59:00Z' }, BAY_GIO)
    expect(tb).toMatchObject({ id: 'S:1', loai: 'can_xu_ly', mucDo: 'khan', incidentId: INC,
      tieuDe: `Cần xử lý: tin ${maNgan(INC)}`, luc: '2026-10-22T09:59:00Z' })
    expect(tb!.noiDung).toBe('Đã giao hết số lần, không đội nào nhận · mức Khẩn cấp')
  })

  it('lý do lạ thì dùng mô tả, không có gì thì câu mặc định', () => {
    expect(docThongBao({ loai: 'can_xu_ly', id: 'a', incident_id: INC, ly_do: 'moi', mo_ta: 'X' })!.noiDung).toBe('X · mức Chưa rõ')
    expect(docThongBao({ loai: 'can_xu_ly', id: 'a', incident_id: INC })!.noiDung).toContain('đã dừng')
  })

  it('tin mới: khẩn cấp thì nổi bật, mức khác là thông tin; thiếu thời điểm thì lấy lúc nhận', () => {
    const khan = docThongBao({ loai: 'tin_moi', id: 'b', incident_id: INC, urgency: 'khan_cap' }, BAY_GIO)!
    expect(khan.mucDo).toBe('khan')
    expect(khan.luc).toBe(BAY_GIO.toISOString())
    expect(docThongBao({ loai: 'tin_moi', id: 'c', incident_id: INC, urgency: 'thap' })!.mucDo).toBe('thong-tin')
  })

  it('cảnh báo mực nước: tên trạm, giá trị và ngưỡng', () => {
    const tb = docThongBao({ loai: 'canh_bao', id: 'd', ma_tram: 'TRAM-01', ten_tram: 'Cầu Trắng', muc: 'nguy_hiem',
      gia_tri: 4.256, nguong: 4, don_vi: 'm', thoi_diem: '2026-10-22T09:00:00Z' })!
    expect(tb).toMatchObject({ tieuDe: 'Nguy hiểm: Cầu Trắng', noiDung: 'Đo được 4.26 m, ngưỡng 4 m', mucDo: 'khan',
      luc: '2026-10-22T09:00:00Z' })
    expect(docThongBao({ loai: 'canh_bao', id: 'e', ma_tram: 'T2', muc: 'canh_bao' })!).toMatchObject({
      tieuDe: 'Cảnh báo: T2', noiDung: 'Trạm đo vượt ngưỡng', mucDo: 'canh-bao' })
  })

  it('dữ liệu lạ hoặc thiếu trường bị bỏ qua', () => {
    for (const d of [null, 'x', 1, {}, { loai: 'tin_moi', incident_id: INC }, { loai: 'khac', id: 'f' },
      { loai: 'tin_moi', id: 'g' }, { loai: 'canh_bao', id: 'h' }, { loai: 'can_xu_ly', id: 'i', incident_id: 5 }]) {
      expect(docThongBao(d)).toBeNull()
    }
  })
})

describe('danh sách thông báo', () => {
  const tb = (id: string): ThongBao => ({ id, loai: 'tin_moi', tieuDe: id, noiDung: '', mucDo: 'thong-tin', luc: '' })

  it('mới nhất lên đầu, nhận lại cùng id (kết nối lại) không thêm, giữ tối đa n', () => {
    let ds: ThongBao[] = []
    for (const id of ['a', 'b', 'c']) ds = themThongBao(ds, tb(id), 2)
    expect(ds.map((x) => x.id)).toEqual(['c', 'b'])
    const truoc = ds
    expect(themThongBao(ds, tb('b'), 2)).toBe(truoc)
  })
})
