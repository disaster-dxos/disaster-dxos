// SPDX-License-Identifier: Apache-2.0
import type { StyleSpecification } from 'maplibre-gl'
import { describe, expect, it } from 'vitest'
import {
  CUM_ZOOM_TOI_DA, NHAN_TIENG_VIET, THUOC_TINH_CUM, bieuThucMauCum, bieuThucMauKhan, bieuThucMauTrangThai, kieuDuPhongOsm,
  nhanTiengViet, tinSangGeoJson, toaDoHopLe, zoomChon,
} from '~/utils/ban-do'
import { MAU_TRANG_THAI, MUC_KHAN, type TinKeuCuu } from '~/utils/tin'

const T1: TinKeuCuu = {
  id: 'd0000000-0000-4000-8000-000000000001', location: [108.2212, 15.9785], urgency: 'khan_cap', status: 'tiep_nhan',
  created_at: '2026-10-29T07:56:00Z',
}
const T2: TinKeuCuu = { ...T1, id: 'd0000000-0000-4000-8000-000000000002', location: [108.19, 15.94], urgency: 'cao', status: 'dang_cuu' }

describe('bản đồ', () => {
  it('GeoJSON giữ id, tọa độ và thuộc tính để tô màu, gom cụm', () => {
    const g = tinSangGeoJson([T1, T2])
    expect(g.type).toBe('FeatureCollection')
    expect(g.features).toHaveLength(2)
    expect(g.features[0]!.id).toBe(T1.id)
    expect(g.features[0]!.geometry).toEqual({ type: 'Point', coordinates: [108.2212, 15.9785] })
    expect(g.features[0]!.properties).toEqual({ id: T1.id, urgency: 'khan_cap', status: 'tiep_nhan', khan: 1, moi: false })
    expect(g.features[1]!.properties).toMatchObject({ urgency: 'cao', status: 'dang_cuu', khan: 0 })
  })
  it('GeoJSON chỉ mang id, mức khẩn, trạng thái: không có SĐT, tên, mô tả dù đầu vào có', () => {
    const lo = { ...T1, reporter_phone: '0900000001', reporter_name: 'Người Mẫu', description: 'x' } as TinKeuCuu
    const p = tinSangGeoJson([lo]).features[0]!.properties
    expect(Object.keys(p).sort()).toEqual(['id', 'khan', 'moi', 'status', 'urgency'])
    expect(JSON.stringify(p)).not.toContain('0900000001')
  })
  it('đánh dấu tin mới theo Map hoặc Set id', () => {
    expect(tinSangGeoJson([T1, T2], new Map([[T2.id, 1]])).features.map((f) => f.properties.moi)).toEqual([false, true])
    expect(tinSangGeoJson([T1, T2], new Set([T1.id])).features.map((f) => f.properties.moi)).toEqual([true, false])
    expect(tinSangGeoJson([]).features).toEqual([])
  })
  it('biểu thức màu có đủ 4 mức khẩn và 5 trạng thái, có màu mặc định', () => {
    const e = bieuThucMauKhan()
    expect(e.slice(0, 2)).toEqual(['match', ['get', 'urgency']])
    for (const [k, v] of Object.entries(MUC_KHAN)) expect(e[e.indexOf(k) + 1]).toBe(v.mau)
    expect(e).toHaveLength(2 + 4 * 2 + 1)
    const s = bieuThucMauTrangThai()
    expect(s.slice(0, 2)).toEqual(['match', ['get', 'status']])
    for (const [k, v] of Object.entries(MAU_TRANG_THAI)) expect(s[s.indexOf(k) + 1]).toBe(v)
    expect(s).toHaveLength(2 + 5 * 2 + 1)
  })
  it('màu nhận diện Team 1 cho mức cao và trạng thái phân công', () => {
    expect(MUC_KHAN.cao.mau).toBe('#F07B1D')
    expect(MUC_KHAN.trung_binh.mau).toBe('#1FA2C9')
    expect(MAU_TRANG_THAI.phan_cong).toBe('#12355B')
  })
  it('gom cụm: cộng dồn số tin khẩn cấp, cụm có tin khẩn tô đỏ, chọn tin thì zoom đủ để tách cụm', () => {
    expect(THUOC_TINH_CUM.khan).toEqual(['+', ['get', 'khan']])
    const c = bieuThucMauCum()
    expect(c[0]).toBe('case')
    expect(c[1]).toEqual(['>', ['get', 'khan'], 0])
    expect(c[2]).toBe(MUC_KHAN.khan_cap.mau)
    expect(zoomChon(8)).toBe(CUM_ZOOM_TOI_DA + 1)
    expect(zoomChon(16)).toBe(16)
  })
  it('nhãn tên đổi sang tiếng Việt, nhãn khác và lớp không phải symbol giữ nguyên', () => {
    const style = {
      version: 8, sources: {},
      layers: [
        { id: 'nen', type: 'background' },
        { id: 'tp', type: 'symbol', source: 's', layout: { 'text-field': ['coalesce', ['get', 'name_en'], ['get', 'name']] } },
        { id: 'so-duong', type: 'symbol', source: 's', layout: { 'text-field': '{ref}' } },
        { id: 'icon', type: 'symbol', source: 's', layout: { 'icon-image': 'x' } },
      ],
    } as unknown as StyleSpecification
    const out = nhanTiengViet(style)
    expect((out.layers[1] as { layout: Record<string, unknown> }).layout['text-field']).toEqual(NHAN_TIENG_VIET)
    expect(out.layers[2]).toBe(style.layers[2])
    expect(out.layers[3]).toBe(style.layers[3])
    expect(out.layers[0]).toBe(style.layers[0])
    // Không sửa object gốc
    expect((style.layers[1] as { layout: Record<string, unknown> }).layout['text-field']).not.toEqual(NHAN_TIENG_VIET)
  })
  it('kiểu dự phòng OSM có ghi công', () => {
    const s = kieuDuPhongOsm()
    expect(s.version).toBe(8)
    expect(JSON.stringify(s.sources)).toContain('OpenStreetMap')
  })
  it('kiểm tọa độ', () => {
    expect(toaDoHopLe([108, 16])).toBe(true)
    expect(toaDoHopLe([181, 0])).toBe(false)
    expect(toaDoHopLe([Number.NaN, 0])).toBe(false)
    expect(toaDoHopLe(undefined)).toBe(false)
  })
})
