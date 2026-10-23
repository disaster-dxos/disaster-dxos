// SPDX-License-Identifier: Apache-2.0
// GraphQL của bản đồ tin kêu cứu (#60): subscription qua WebSocket (graphql-transport-ws) tới Hasura qua
// API Gateway, chuyển kết quả thành TinKeuCuu, phân loại lý do đóng kết nối. Hàm thuần, có test
// (tests/tin-graphql.test.ts). Gọi mạng nằm ở composables/useTinKeuCuu.ts.
import { laMucKhan, laTrangThai, type ChiTietTin, type TinKeuCuu } from './tin'

export const DUONG_GRAPHQL = '/graphql'
/** Số tin tối đa trên bản đồ (mới nhất trước); đủ cho một xã trong một đợt bão */
export const SO_TIN_TOI_DA = 500

/**
 * Live query của Hasura: mỗi khi bảng đổi, Hasura gửi lại toàn bộ kết quả (refetch mặc định 1 giây).
 * CHỈ trường cần cho bản đồ: không SĐT, tên người gọi, mô tả. Quyền theo hàng do Hasura áp theo vai
 * (tinh-nguyen chỉ thấy tin mình tạo, cuu-ho chỉ thấy tin của đội mình).
 */
export const SUB_BAN_DO = `subscription BanDoTin($gioiHan: Int!) {
  incidents(order_by: {created_at: desc}, limit: $gioiHan) { id location urgency status created_at }
}`

/** Vai được đọc SĐT, tên người gọi và đội phụ trách (metadata Hasura #26). */
const VAI_XEM_LIEN_HE = ['dieu-phoi', 'cuu-ho']

/** Query chi tiết một tin khi bấm; cột liên hệ chỉ có trong query của vai được phép đọc. */
export function queryChiTiet(vai: string | undefined): string {
  const lienHe = vai && VAI_XEM_LIEN_HE.includes(vai) ? ' reporter_phone reporter_name assigned_team { name }' : ''
  return `query ChiTietTin($id: uuid!) {
  incidents_by_pk(id: $id) { id location urgency status created_at updated_at description address_text people_count source${lienHe} }
}`
}

/** URL WebSocket GraphQL qua API Gateway: http(s)://gateway → ws(s)://gateway/graphql */
export function wsGraphqlUrl(gatewayUrl: string): string {
  const u = new URL(gatewayUrl)
  if (u.protocol !== 'http:' && u.protocol !== 'https:') throw new Error(`gatewayUrl không hợp lệ: ${gatewayUrl}`)
  u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:'
  u.pathname = DUONG_GRAPHQL
  u.search = ''
  u.hash = ''
  return u.toString()
}

export function httpGraphqlUrl(gatewayUrl: string): string {
  return new URL(DUONG_GRAPHQL, gatewayUrl).toString()
}

/** Tọa độ từ GeoJSON Point của PostGIS (Hasura trả {type, crs, coordinates}); hỏng thì null. */
export function toaDoTuGeoJson(v: unknown): [number, number] | null {
  if (!v || typeof v !== 'object') return null
  const g = v as { type?: unknown; coordinates?: unknown }
  if (g.type !== 'Point' || !Array.isArray(g.coordinates) || g.coordinates.length < 2) return null
  const [lng, lat] = g.coordinates as unknown[]
  if (typeof lng !== 'number' || typeof lat !== 'number') return null
  if (!Number.isFinite(lng) || !Number.isFinite(lat) || Math.abs(lng) > 180 || Math.abs(lat) > 90) return null
  return [lng, lat]
}

/** Một hàng GraphQL → TinKeuCuu; thiếu trường hoặc giá trị lạ thì null (bỏ qua, không làm vỡ bản đồ). */
export function tinTuHang(h: unknown): TinKeuCuu | null {
  if (!h || typeof h !== 'object') return null
  const r = h as Record<string, unknown>
  const location = toaDoTuGeoJson(r.location)
  if (typeof r.id !== 'string' || !location || !laMucKhan(r.urgency) || !laTrangThai(r.status)) return null
  if (typeof r.created_at !== 'string' || Number.isNaN(Date.parse(r.created_at))) return null
  return { id: r.id, location, urgency: r.urgency, status: r.status, created_at: r.created_at }
}

/** Dữ liệu `next` của subscription → danh sách tin hợp lệ (bỏ hàng hỏng, bỏ trùng id). */
export function tinTuKetQua(data: unknown): TinKeuCuu[] {
  const rows = (data as { incidents?: unknown } | null)?.incidents
  if (!Array.isArray(rows)) return []
  const ds: TinKeuCuu[] = []
  const thay = new Set<string>()
  for (const h of rows) {
    const t = tinTuHang(h)
    if (t && !thay.has(t.id)) {
      thay.add(t.id)
      ds.push(t)
    }
  }
  return ds
}

/** Kết quả query chi tiết → ChiTietTin (null nếu không thấy, vd không có quyền theo hàng). */
export function chiTietTuKetQua(data: unknown): ChiTietTin | null {
  const r = (data as { incidents_by_pk?: Record<string, unknown> | null } | null)?.incidents_by_pk
  const t = tinTuHang(r)
  if (!t || !r) return null
  const chuoi = (v: unknown) => (typeof v === 'string' ? v : null)
  const team = r.assigned_team as { name?: unknown } | null | undefined
  return {
    ...t,
    description: chuoi(r.description) ?? '',
    address_text: chuoi(r.address_text),
    people_count: typeof r.people_count === 'number' ? r.people_count : 1,
    source: chuoi(r.source) ?? 'khac',
    updated_at: chuoi(r.updated_at) ?? t.created_at,
    ...('reporter_phone' in r ? { reporter_phone: chuoi(r.reporter_phone) ?? '', reporter_name: chuoi(r.reporter_name) } : {}),
    ...('assigned_team' in r ? { team_name: chuoi(team?.name) } : {}),
  }
}

export type LyDoDong = 'het-han-token' | 'tu-choi' | 'mang'

/**
 * Phân loại lý do WebSocket đóng hoặc lỗi giao thức để quyết định làm gì tiếp:
 * - het-han-token: JWT hết hạn → làm mới token rồi kết nối lại;
 * - tu-choi: JWT sai, thiếu quyền (4401/4403, lỗi JWT/JWK) → làm mới token một lần, vẫn bị thì báo hết phiên;
 * - mang: mất mạng, gateway/Hasura khởi động lại… → kết nối lại theo backoff.
 */
export function phanLoaiDong(code: number | undefined, lyDo = ''): LyDoDong {
  if (/expired/i.test(lyDo)) return 'het-han-token'
  if (code === 4401 || code === 4403 || /jwt|jwk|jws|unauthori[sz]ed|forbidden|invalid.*token/i.test(lyDo)) return 'tu-choi'
  return 'mang'
}

/** Thời gian chờ trước lần kết nối lại thứ n (0, 1, 2…): 0,5 s → 1 s → 2 s … tối đa 20 s, cộng nhiễu ≤ 30%. */
export function choKetNoiLai(lan: number, ngauNhien = Math.random()): number {
  const goc = Math.min(20_000, 500 * 2 ** Math.max(0, lan))
  return Math.round(goc * (1 + 0.3 * ngauNhien))
}
