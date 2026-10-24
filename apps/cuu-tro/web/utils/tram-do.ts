// SPDX-License-Identifier: Apache-2.0
// Lớp trạm đo mực nước trên bản đồ điều phối (#62): hàm thuần, có test (tests/tram-do.test.ts).
// Vị trí, mực nước mới nhất và cấp báo động lấy từ bản sao số trạm đo NGSI-LD trên Scorpio (#85) qua API
// Gateway (GET /ngsi-ld/v1/entities, Accept: application/geo+json; gateway tự đặt @context nên dùng tên ngắn).
// Biểu đồ nhỏ trong popup: chuỗi đo 24 giờ gần nhất từ GraphQL sensor_readings (mọi vai đều đọc được).
// Dữ liệu trạm không định danh: chỉ mã, tên, tọa độ trạm, giá trị đo và ngưỡng.

export type MucTram = 'binh_thuong' | 'canh_bao' | 'nguy_hiem'

export interface TramDo {
  /** id thực thể NGSI-LD (urn:ngsi-ld:WaterLevelStation:<mã>) */
  id: string
  ma: string
  ten: string
  /** [kinh độ, vĩ độ] (WGS 84) */
  location: [number, number]
  /** Mực nước mới nhất (cm), null nếu trạm chưa có lần đo */
  mucNuoc: number | null
  muc: MucTram
  nguongCanhBao: number | null
  nguongNguyHiem: number | null
}

export interface DiemDo {
  luc: string
  giaTri: number
  muc: MucTram
}

export const MUC_TRAM: Record<MucTram, { nhan: string; mau: string; thuTu: number }> = {
  nguy_hiem: { nhan: 'Nguy hiểm', mau: '#DC2626', thuTu: 0 },
  canh_bao: { nhan: 'Cảnh báo', mau: '#F59E0B', thuTu: 1 },
  binh_thuong: { nhan: 'Bình thường', mau: '#16A34A', thuTu: 2 },
}
export const DS_MUC_TRAM: MucTram[] = ['nguy_hiem', 'canh_bao', 'binh_thuong']

/** Tải lại danh sách trạm định kỳ (ms); có cảnh báo realtime từ Centrifugo thì tải ngay. */
export const CHU_KY_TAI_TRAM = 60_000
/** Số giờ chuỗi đo trong biểu đồ nhỏ và số điểm tối đa */
export const GIO_LICH_SU = 24
export const SO_DIEM_TOI_DA = 96
/** Đủ cho mọi trạm của một xã/huyện; Scorpio mặc định chỉ trả 20 thực thể */
export const SO_TRAM_TOI_DA = 200

export const DUONG_TRAM = `/ngsi-ld/v1/entities?type=WaterLevelStation&options=keyValues&limit=${SO_TRAM_TOI_DA}`
export const ACCEPT_TRAM = 'application/geo+json'

/** URL danh sách trạm đo mực nước qua API Gateway */
export function tramUrl(gatewayUrl: string): string {
  const u = new URL(gatewayUrl)
  if (u.protocol !== 'http:' && u.protocol !== 'https:') throw new Error(`gatewayUrl không hợp lệ: ${gatewayUrl}`)
  return new URL(DUONG_TRAM, u).toString()
}

/** Chuỗi đo của một trạm từ mốc $tu, mới nhất trước (đảo lại khi vẽ). */
export const Q_LICH_SU_TRAM = `query LichSuTram($ma: String!, $tu: timestamptz!) {
  sensor_readings(where: {sensor: {code: {_eq: $ma}}, observed_at: {_gte: $tu}}, order_by: {observed_at: desc}, limit: ${SO_DIEM_TOI_DA}) {
    observed_at value level
  }
}`

function so(v: unknown): number | null {
  if (typeof v === 'number' && Number.isFinite(v)) return v
  if (typeof v === 'string' && v.trim() !== '' && Number.isFinite(Number(v))) return Number(v)
  return null
}

function laMuc(v: unknown): v is MucTram {
  return v === 'binh_thuong' || v === 'canh_bao' || v === 'nguy_hiem'
}

function toaDo(g: unknown): [number, number] | null {
  const c = (g as { type?: unknown; coordinates?: unknown } | null)?.coordinates
  if ((g as { type?: unknown } | null)?.type !== 'Point' || !Array.isArray(c) || c.length < 2) return null
  const [x, y] = c as unknown[]
  if (typeof x !== 'number' || typeof y !== 'number' || Math.abs(x) > 180 || Math.abs(y) > 90) return null
  return [x, y]
}

/** Một Feature GeoJSON của Scorpio (keyValues) → trạm; thiếu mã hoặc tọa độ thì bỏ. */
export function tramTuFeature(f: unknown): TramDo | null {
  const ft = f as { id?: unknown; geometry?: unknown; properties?: Record<string, unknown> } | null
  const p = ft?.properties
  const loc = toaDo(ft?.geometry)
  if (!p || !loc || typeof p.stationCode !== 'string' || !p.stationCode) return null
  const ma = p.stationCode
  return {
    id: typeof ft?.id === 'string' ? ft.id : `urn:ngsi-ld:WaterLevelStation:${ma}`,
    ma,
    ten: typeof p.name === 'string' && p.name ? p.name : ma,
    location: loc,
    mucNuoc: so(p.waterLevel),
    muc: laMuc(p.alertLevel) ? p.alertLevel : 'binh_thuong',
    nguongCanhBao: so(p.warningThreshold),
    nguongNguyHiem: so(p.dangerThreshold),
  }
}

/** FeatureCollection của Scorpio → danh sách trạm, nguy hiểm trước rồi theo mã. */
export function tramTuGeoJson(fc: unknown): TramDo[] {
  const fs = (fc as { type?: unknown; features?: unknown } | null)
  if (fs?.type !== 'FeatureCollection' || !Array.isArray(fs.features)) throw new Error('Phản hồi NGSI-LD không phải GeoJSON FeatureCollection')
  return sapXepTram(fs.features.map(tramTuFeature).filter((t): t is TramDo => t !== null))
}

export function sapXepTram(ds: TramDo[]): TramDo[] {
  return [...ds].sort((a, b) => MUC_TRAM[a.muc].thuTu - MUC_TRAM[b.muc].thuTu || a.ma.localeCompare(b.ma))
}

export function demTheoMuc(ds: TramDo[]): Record<MucTram, number> {
  const d: Record<MucTram, number> = { nguy_hiem: 0, canh_bao: 0, binh_thuong: 0 }
  for (const t of ds) d[t.muc]++
  return d
}

/** GeoJSON cho nguồn 'tram' của MapLibre: chỉ thuộc tính cần để vẽ và mở popup. */
export function tramSangGeoJson(ds: TramDo[]) {
  return {
    type: 'FeatureCollection' as const,
    features: ds.map((t) => ({
      type: 'Feature' as const,
      id: t.ma,
      geometry: { type: 'Point' as const, coordinates: t.location },
      properties: { ma: t.ma, muc: t.muc, nhan: t.mucNuoc === null ? t.ma : `${t.ma} · ${dinhDangCm(t.mucNuoc)}`, thuTu: MUC_TRAM[t.muc].thuTu },
    })),
  }
}

/** Biểu thức màu MapLibre theo cấp báo động (giống MUC_TRAM) */
export function bieuThucMauTram(): unknown[] {
  return ['match', ['get', 'muc'], ...DS_MUC_TRAM.flatMap((m) => [m, MUC_TRAM[m].mau]), MUC_TRAM.binh_thuong.mau]
}

/** Kết quả GraphQL LichSuTram → điểm đo theo thời gian tăng dần */
export function lichSuTuKetQua(data: unknown): DiemDo[] {
  const hang = (data as { sensor_readings?: unknown } | null)?.sensor_readings
  if (!Array.isArray(hang)) return []
  const ds: DiemDo[] = []
  for (const h of hang as Array<Record<string, unknown>>) {
    const v = so(h?.value)
    if (typeof h?.observed_at !== 'string' || v === null || Number.isNaN(Date.parse(h.observed_at))) continue
    ds.push({ luc: h.observed_at, giaTri: v, muc: laMuc(h.level) ? h.level : 'binh_thuong' })
  }
  return ds.sort((a, b) => Date.parse(a.luc) - Date.parse(b.luc))
}

export function mocLichSu(now = Date.now()): string {
  return new Date(now - GIO_LICH_SU * 3600_000).toISOString()
}

export interface BieuDo {
  /** Thuộc tính d của <path> đường mực nước; rỗng nếu chưa có điểm */
  duong: string
  /** Điểm cuối (mới nhất) để vẽ chấm */
  cuoi: { x: number; y: number } | null
  /** Tọa độ y của vạch ngưỡng (null nếu ngưỡng nằm ngoài khung hoặc không có) */
  yCanhBao: number | null
  yNguyHiem: number | null
  min: number
  max: number
}

/**
 * Biểu đồ nhỏ (sparkline) trong khung rong×cao (px), lề trong `le`. Trục y gồm cả các ngưỡng để thấy mực
 * nước còn cách ngưỡng bao xa; trục x theo thời gian thật (khoảng trống khi trạm mất tín hiệu vẫn thấy).
 */
export function bieuDo(diem: DiemDo[], rong: number, cao: number, nguong: { canhBao: number | null; nguyHiem: number | null }, le = 3): BieuDo {
  const gt = diem.map((d) => d.giaTri)
  const tr = [nguong.canhBao, nguong.nguyHiem].filter((v): v is number => v !== null)
  const tatCa = [...gt, ...tr]
  if (gt.length === 0) return { duong: '', cuoi: null, yCanhBao: null, yNguyHiem: null, min: 0, max: 0 }
  let min = Math.min(...tatCa)
  let max = Math.max(...tatCa)
  if (max === min) { min -= 1; max += 1 }
  const t = diem.map((d) => Date.parse(d.luc))
  const t0 = t[0]!
  const dt = t[t.length - 1]! - t0
  const x = (i: number) => le + (dt > 0 ? ((t[i]! - t0) / dt) * (rong - 2 * le) : (rong - 2 * le) / 2)
  const y = (v: number) => le + (1 - (v - min) / (max - min)) * (cao - 2 * le)
  const lam = (v: number) => Math.round(v * 10) / 10
  const duong = diem.map((d, i) => `${i ? 'L' : 'M'}${lam(x(i))} ${lam(y(d.giaTri))}`).join(' ')
  const n = diem.length - 1
  return {
    duong,
    cuoi: { x: lam(x(n)), y: lam(y(diem[n]!.giaTri)) },
    yCanhBao: nguong.canhBao === null ? null : lam(y(nguong.canhBao)),
    yNguyHiem: nguong.nguyHiem === null ? null : lam(y(nguong.nguyHiem)),
    min,
    max,
  }
}

export function dinhDangCm(v: number | null): string {
  return v === null ? '—' : `${v.toLocaleString('vi-VN', { maximumFractionDigits: 1 })} cm`
}

/** Còn cách ngưỡng tiếp theo bao nhiêu (cm), hoặc đã vượt ngưỡng nguy hiểm bao nhiêu */
export function khoangCachNguong(t: TramDo): string | null {
  if (t.mucNuoc === null) return null
  if (t.nguongNguyHiem !== null && t.mucNuoc >= t.nguongNguyHiem) return `Vượt ngưỡng nguy hiểm ${dinhDangCm(t.mucNuoc - t.nguongNguyHiem)}`
  if (t.nguongCanhBao !== null && t.mucNuoc >= t.nguongCanhBao) {
    return t.nguongNguyHiem === null ? `Vượt ngưỡng cảnh báo ${dinhDangCm(t.mucNuoc - t.nguongCanhBao)}`
      : `Còn ${dinhDangCm(t.nguongNguyHiem - t.mucNuoc)} tới ngưỡng nguy hiểm`
  }
  if (t.nguongCanhBao !== null) return `Còn ${dinhDangCm(t.nguongCanhBao - t.mucNuoc)} tới ngưỡng cảnh báo`
  return null
}
