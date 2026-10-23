// SPDX-License-Identifier: Apache-2.0
// Hàm thuần cho bản đồ MapLibre: chuyển tin kêu cứu sang GeoJSON, biểu thức màu, gom cụm, nhãn tiếng
// Việt, kiểu dự phòng. Có test (tests/ban-do.test.ts).
import type { FeatureCollection, Point } from 'geojson'
import type { StyleSpecification } from 'maplibre-gl'
import { MAU_TRANG_THAI, MUC_KHAN, type MucKhan, type TinKeuCuu, type TrangThai } from './tin'

/** Trung tâm mặc định: vùng dữ liệu mẫu (Đà Nẵng – Quảng Nam), [kinh độ, vĩ độ] */
export const TAM_MAC_DINH: [number, number] = [108.2, 15.92]
export const ZOOM_MAC_DINH = 10.5

/** Ghi chú địa danh chủ quyền hiển thị trên mọi kiểu bản đồ nền */
export const QUAN_DAO: FeatureCollection<Point> = {
  type: 'FeatureCollection',
  features: [
    { type: 'Feature', properties: { ten: 'Quần đảo Hoàng Sa\n(Việt Nam)' }, geometry: { type: 'Point', coordinates: [112.0, 16.5] } },
    { type: 'Feature', properties: { ten: 'Quần đảo Trường Sa\n(Việt Nam)' }, geometry: { type: 'Point', coordinates: [114.3, 10.0] } },
  ],
}

export interface ThuocTinhDiem {
  id: string
  urgency: MucKhan
  status: TrangThai
  /** 1 nếu khẩn cấp: cụm cộng dồn để tô cụm màu đỏ khi có tin khẩn cấp bên trong */
  khan: 0 | 1
  /** Tin vừa đến (nhấp nháy) */
  moi: boolean
}

/** Tin → GeoJSON cho nguồn MapLibre. Chỉ mang id, mức khẩn, trạng thái: không có dữ liệu cá nhân. */
export function tinSangGeoJson(ds: TinKeuCuu[], moi: ReadonlyMap<string, number> | ReadonlySet<string> = new Set()): FeatureCollection<Point, ThuocTinhDiem> {
  return {
    type: 'FeatureCollection',
    features: ds.map((t) => ({
      type: 'Feature',
      id: t.id,
      properties: { id: t.id, urgency: t.urgency, status: t.status, khan: t.urgency === 'khan_cap' ? 1 : 0, moi: moi.has(t.id) },
      geometry: { type: 'Point', coordinates: t.location },
    })),
  }
}

/** Biểu thức MapLibre tô màu điểm theo mức khẩn (match trên thuộc tính urgency). */
export function bieuThucMauKhan(): unknown[] {
  const cap: unknown[] = []
  for (const [k, v] of Object.entries(MUC_KHAN)) cap.push(k, v.mau)
  return ['match', ['get', 'urgency'], ...cap, '#64748B']
}

/** Biểu thức màu viền điểm theo trạng thái. */
export function bieuThucMauTrangThai(): unknown[] {
  const cap: unknown[] = []
  for (const [k, v] of Object.entries(MAU_TRANG_THAI)) cap.push(k, v)
  return ['match', ['get', 'status'], ...cap, '#FFFFFF']
}

/** Gom cụm: tách cụm từ mức zoom này trở lên; bán kính gom (px). */
export const CUM_ZOOM_TOI_DA = 13
export const CUM_BAN_KINH = 50

/** Thuộc tính cộng dồn cho cụm (clusterProperties của nguồn GeoJSON). */
export const THUOC_TINH_CUM = { khan: ['+', ['get', 'khan']] }

/** Màu cụm: đỏ nếu có tin khẩn cấp, cam cứu hộ nếu ≥ 10 tin, navy nếu ít. */
export function bieuThucMauCum(): unknown[] {
  return ['case', ['>', ['get', 'khan'], 0], MUC_KHAN.khan_cap.mau, ['>=', ['get', 'point_count'], 10], '#F07B1D', '#12355B']
}

/** Zoom để tách một điểm ra khỏi cụm khi chọn từ danh sách. */
export function zoomChon(zoomHienTai: number): number {
  return Math.max(zoomHienTai, CUM_ZOOM_TOI_DA + 1)
}

/** Nhãn bản đồ ưu tiên tên tiếng Việt, rồi tên Latin, rồi tên gốc (lược đồ OpenMapTiles). */
export const NHAN_TIENG_VIET = ['coalesce', ['get', 'name:vi'], ['get', 'name:latin'], ['get', 'name']]

/** Đổi text-field của mọi lớp nhãn có tên địa danh sang NHAN_TIENG_VIET. Không sửa object gốc. */
export function nhanTiengViet(style: StyleSpecification): StyleSpecification {
  const coTen = (v: unknown): boolean => JSON.stringify(v ?? '').includes('name')
  return {
    ...style,
    layers: style.layers.map((l) => {
      if (l.type !== 'symbol') return l
      const tf = l.layout?.['text-field']
      // Biển số đường (ref) và nhãn không dựa trên tên thì giữ nguyên
      if (!tf || !coTen(tf)) return l
      return { ...l, layout: { ...l.layout, 'text-field': NHAN_TIENG_VIET } } as typeof l
    }),
  }
}

/** Kiểu nền dự phòng khi không tải được kiểu vector: ô ảnh OpenStreetMap (dữ liệu ODbL). */
export function kieuDuPhongOsm(): StyleSpecification {
  return {
    version: 8,
    sources: {
      osm: {
        type: 'raster',
        tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
        tileSize: 256,
        maxzoom: 19,
        attribution: '© <a href="https://www.openstreetmap.org/copyright">Những người đóng góp OpenStreetMap</a>',
      },
    },
    layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
  }
}

/** Trả về null nếu tọa độ hỏng; dùng trước khi flyTo. */
export function toaDoHopLe(c: [number, number] | undefined): c is [number, number] {
  return !!c && Number.isFinite(c[0]) && Number.isFinite(c[1])
    && c[0] >= -180 && c[0] <= 180 && c[1] >= -90 && c[1] <= 90
}
