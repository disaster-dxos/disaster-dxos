// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest'
import {
  DUONG_TRAM, MUC_TRAM, Q_LICH_SU_TRAM, SO_TRAM_TOI_DA, bieuDo, bieuThucMauTram, demTheoMuc, dinhDangCm,
  khoangCachNguong, lichSuTuKetQua, mocLichSu, tramSangGeoJson, tramTuFeature, tramTuGeoJson, tramUrl, type TramDo,
} from '~/utils/tram-do'

// Phản hồi mẫu của Scorpio (Accept: application/geo+json, options=keyValues) — dữ liệu giả
const F = (ma: string, muc: string, gt: number, xy: [number, number] = [108.11, 15.86]) => ({
  type: 'Feature',
  id: `urn:ngsi-ld:WaterLevelStation:${ma}`,
  geometry: { type: 'Point', coordinates: xy },
  properties: {
    id: `urn:ngsi-ld:WaterLevelStation:${ma}`, type: 'WaterLevelStation', name: `Trạm ${ma}`, stationCode: ma,
    location: { type: 'Point', coordinates: xy }, waterLevel: gt, alertLevel: muc, warningThreshold: 350, dangerThreshold: 450,
  },
})
const FC = { type: 'FeatureCollection', features: [F('QN-CL-01', 'canh_bao', 380), F('AL-MN-01', 'binh_thuong', 120), F('DN-CLE-01', 'nguy_hiem', 470)] }

describe('trạm đo: lấy dữ liệu NGSI-LD', () => {
  it('URL qua API Gateway: entities kiểu WaterLevelStation, keyValues, đủ giới hạn', () => {
    const u = new URL(tramUrl('http://localhost:9080'))
    expect(u.origin).toBe('http://localhost:9080')
    expect(u.pathname).toBe('/ngsi-ld/v1/entities')
    expect(u.searchParams.get('type')).toBe('WaterLevelStation')
    expect(u.searchParams.get('options')).toBe('keyValues')
    expect(Number(u.searchParams.get('limit'))).toBe(SO_TRAM_TOI_DA)
    expect(DUONG_TRAM.startsWith('/ngsi-ld/v1/')).toBe(true)
    expect(() => tramUrl('javascript:alert(1)')).toThrow()
  })
  it('đọc FeatureCollection: đủ trường, nguy hiểm trước rồi cảnh báo, bình thường', () => {
    const ds = tramTuGeoJson(FC)
    expect(ds.map((t) => t.ma)).toEqual(['DN-CLE-01', 'QN-CL-01', 'AL-MN-01'])
    expect(ds[1]).toEqual({
      id: 'urn:ngsi-ld:WaterLevelStation:QN-CL-01', ma: 'QN-CL-01', ten: 'Trạm QN-CL-01', location: [108.11, 15.86],
      mucNuoc: 380, muc: 'canh_bao', nguongCanhBao: 350, nguongNguyHiem: 450,
    })
  })
  it('bỏ feature thiếu mã hoặc tọa độ sai; cấp lạ coi là bình thường; giá trị chuỗi số vẫn đọc', () => {
    expect(tramTuFeature({ ...F('X-01', 'canh_bao', 1), geometry: { type: 'Point', coordinates: [200, 10] } })).toBeNull()
    expect(tramTuFeature({ ...F('X-01', 'canh_bao', 1), geometry: null })).toBeNull()
    expect(tramTuFeature({ geometry: { type: 'Point', coordinates: [108, 16] }, properties: { name: 'x' } })).toBeNull()
    const t = tramTuFeature({ ...F('X-01', 'lu_lut', 1), properties: { stationCode: 'X-01', alertLevel: 'lu_lut', waterLevel: '12.5' }, geometry: { type: 'Point', coordinates: [108, 16] } })
    expect(t).toMatchObject({ ma: 'X-01', ten: 'X-01', muc: 'binh_thuong', mucNuoc: 12.5, nguongCanhBao: null })
  })
  it('phản hồi không phải FeatureCollection (vd. lỗi JSON-LD) → báo lỗi, không vẽ sai', () => {
    expect(() => tramTuGeoJson([{ id: 'x' }])).toThrow(/FeatureCollection/)
    expect(() => tramTuGeoJson(null)).toThrow()
  })
  it('đếm theo cấp báo động cho chú thích', () => {
    expect(demTheoMuc(tramTuGeoJson(FC))).toEqual({ nguy_hiem: 1, canh_bao: 1, binh_thuong: 1 })
  })
})

describe('trạm đo: lớp bản đồ', () => {
  it('GeoJSON nguồn tram chỉ mang mã, cấp, nhãn, thứ tự vẽ', () => {
    const g = tramSangGeoJson(tramTuGeoJson(FC))
    expect(g.features).toHaveLength(3)
    expect(g.features[0]!.id).toBe('DN-CLE-01')
    expect(g.features[0]!.properties).toEqual({ ma: 'DN-CLE-01', muc: 'nguy_hiem', nhan: 'DN-CLE-01 · 470 cm', thuTu: 0 })
    expect(g.features[0]!.geometry).toEqual({ type: 'Point', coordinates: [108.11, 15.86] })
  })
  it('màu theo cấp báo động: biểu thức match đủ 3 cấp, mặc định bình thường', () => {
    const e = bieuThucMauTram()
    expect(e.slice(0, 2)).toEqual(['match', ['get', 'muc']])
    expect(e).toContain(MUC_TRAM.nguy_hiem.mau)
    expect(e[e.indexOf('canh_bao') + 1]).toBe(MUC_TRAM.canh_bao.mau)
    expect(e.at(-1)).toBe(MUC_TRAM.binh_thuong.mau)
    expect(new Set(Object.values(MUC_TRAM).map((m) => m.mau)).size).toBe(3)
  })
})

describe('trạm đo: popup', () => {
  const T: TramDo = { id: 'x', ma: 'QN-CL-01', ten: 'Cẩm Lệ', location: [108.2, 16], mucNuoc: 380, muc: 'canh_bao', nguongCanhBao: 350, nguongNguyHiem: 450 }
  it('query lịch sử: lọc theo mã trạm và mốc thời gian, có giới hạn số điểm', () => {
    expect(Q_LICH_SU_TRAM).toContain('sensor_readings(where: {sensor: {code: {_eq: $ma}}, observed_at: {_gte: $tu}}')
    expect(Q_LICH_SU_TRAM).toMatch(/limit: \d+/)
    expect(mocLichSu(Date.parse('2026-10-24T12:00:00Z'))).toBe('2026-10-23T12:00:00.000Z')
  })
  it('kết quả lịch sử sắp theo thời gian tăng dần, bỏ dòng hỏng', () => {
    const ds = lichSuTuKetQua({ sensor_readings: [
      { observed_at: '2026-10-24T03:00:00Z', value: 380, level: 'canh_bao' },
      { observed_at: 'khong-phai-ngay', value: 1, level: 'canh_bao' },
      { observed_at: '2026-10-24T02:00:00Z', value: '340.5', level: 'binh_thuong' },
      { observed_at: '2026-10-24T01:00:00Z', value: null },
    ] })
    expect(ds).toEqual([
      { luc: '2026-10-24T02:00:00Z', giaTri: 340.5, muc: 'binh_thuong' },
      { luc: '2026-10-24T03:00:00Z', giaTri: 380, muc: 'canh_bao' },
    ])
    expect(lichSuTuKetQua(null)).toEqual([])
  })
  it('biểu đồ nhỏ: đường nằm trong khung, điểm cuối bên phải, trục y gồm cả ngưỡng', () => {
    const d = [
      { luc: '2026-10-24T00:00:00Z', giaTri: 300, muc: 'binh_thuong' as const },
      { luc: '2026-10-24T06:00:00Z', giaTri: 360, muc: 'canh_bao' as const },
      { luc: '2026-10-24T12:00:00Z', giaTri: 380, muc: 'canh_bao' as const },
    ]
    const b = bieuDo(d, 200, 50, { canhBao: 350, nguyHiem: 450 })
    expect(b.duong.startsWith('M3 ')).toBe(true)
    expect(b.duong.split(' L')).toHaveLength(3)
    expect(b.cuoi!.x).toBe(197)
    expect(b.min).toBe(300)
    expect(b.max).toBe(450)
    expect(b.yNguyHiem).toBe(3)            // ngưỡng cao nhất ở mép trên
    expect(b.yCanhBao! > b.yNguyHiem!).toBe(true)
    for (const m of b.duong.matchAll(/[ML]([\d.]+) ([\d.]+)/g)) {
      expect(Number(m[1])).toBeGreaterThanOrEqual(0); expect(Number(m[1])).toBeLessThanOrEqual(200)
      expect(Number(m[2])).toBeGreaterThanOrEqual(0); expect(Number(m[2])).toBeLessThanOrEqual(50)
    }
  })
  it('biểu đồ nhỏ: không có điểm → rỗng; một điểm, giá trị phẳng → không chia cho 0', () => {
    expect(bieuDo([], 200, 50, { canhBao: null, nguyHiem: null }).duong).toBe('')
    const b = bieuDo([{ luc: '2026-10-24T00:00:00Z', giaTri: 5, muc: 'binh_thuong' }], 200, 50, { canhBao: null, nguyHiem: null })
    expect(b.duong).toBe('M100 25')
    expect(b.yCanhBao).toBeNull()
  })
  it('khoảng cách tới ngưỡng', () => {
    expect(khoangCachNguong(T)).toBe('Còn 70 cm tới ngưỡng nguy hiểm')
    expect(khoangCachNguong({ ...T, mucNuoc: 470 })).toBe('Vượt ngưỡng nguy hiểm 20 cm')
    expect(khoangCachNguong({ ...T, mucNuoc: 300 })).toBe('Còn 50 cm tới ngưỡng cảnh báo')
    expect(khoangCachNguong({ ...T, mucNuoc: null })).toBeNull()
    expect(dinhDangCm(null)).toBe('—')
    expect(dinhDangCm(12.25)).toBe('12,3 cm')
  })
})
