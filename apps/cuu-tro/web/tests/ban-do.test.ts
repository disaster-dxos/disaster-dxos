// SPDX-License-Identifier: Apache-2.0
import type { StyleSpecification } from 'maplibre-gl'
import { describe, expect, it } from 'vitest'
import { NHAN_TIENG_VIET, bieuThucMauKhan, kieuDuPhongOsm, nhanTiengViet, tinSangGeoJson, toaDoHopLe } from '~/utils/ban-do'
import { MUC_KHAN, cheSdt, demTheoTrangThai, sapXepTin, thoiGianTruoc, tinGia } from '~/utils/tin-gia'

const NOW = Date.parse('2026-10-29T08:00:00Z')

describe('dữ liệu giả', () => {
  const ds = tinGia(NOW)
  it('mọi tin có tọa độ hợp lệ trong vùng mẫu và SĐT dạng 0 + 9 số', () => {
    for (const t of ds) {
      expect(toaDoHopLe(t.location)).toBe(true)
      expect(t.location[0]).toBeGreaterThan(107.5)
      expect(t.location[1]).toBeGreaterThan(15.5)
      expect(t.reporter_phone).toMatch(/^0\d{9}$/)
    }
    expect(new Set(ds.map((t) => t.id)).size).toBe(ds.length)
  })
  it('sắp xếp: chưa xong trước, khẩn hơn trước, cũ hơn trước', () => {
    const s = sapXepTin(ds)
    expect(s[0]!.urgency).toBe('khan_cap')
    expect(s.at(-1)!.status).toBe('da_cuu')
    const khan = s.filter((t) => t.urgency === 'khan_cap')
    expect(khan[0]!.created_at < khan[1]!.created_at).toBe(true)
  })
  it('đếm theo trạng thái', () => {
    const d = demTheoTrangThai(ds)
    expect(Object.values(d).reduce((a, b) => a + b, 0)).toBe(ds.length)
    expect(d.tiep_nhan).toBe(4)
  })
  it('thời gian tương đối và che SĐT', () => {
    expect(thoiGianTruoc(new Date(NOW - 20_000).toISOString(), NOW)).toBe('vừa xong')
    expect(thoiGianTruoc(new Date(NOW - 5 * 60_000).toISOString(), NOW)).toBe('5 phút trước')
    expect(thoiGianTruoc(new Date(NOW - 3 * 3_600_000).toISOString(), NOW)).toBe('3 giờ trước')
    expect(thoiGianTruoc(new Date(NOW - 50 * 3_600_000).toISOString(), NOW)).toBe('2 ngày trước')
    expect(cheSdt('0900000001')).toBe('0900***001')
  })
})

describe('bản đồ', () => {
  it('GeoJSON giữ id và thuộc tính để tô màu', () => {
    const g = tinSangGeoJson(tinGia(NOW).slice(0, 2))
    expect(g.features).toHaveLength(2)
    expect(g.features[0]!.geometry.coordinates).toEqual([108.2212, 15.9785])
    expect(g.features[0]!.properties).toMatchObject({ urgency: 'khan_cap', status: 'tiep_nhan' })
  })
  it('biểu thức màu có đủ 4 mức khẩn', () => {
    const e = bieuThucMauKhan()
    expect(e.slice(0, 2)).toEqual(['match', ['get', 'urgency']])
    for (const [k, v] of Object.entries(MUC_KHAN)) expect(e[e.indexOf(k) + 1]).toBe(v.mau)
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
