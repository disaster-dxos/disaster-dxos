// SPDX-License-Identifier: Apache-2.0
// Hàm thuần cho bản đồ MapLibre: chuyển tin kêu cứu sang GeoJSON, nhãn tiếng Việt, kiểu dự phòng.
import type { FeatureCollection, Point } from 'geojson'
import type { StyleSpecification } from 'maplibre-gl'
import { MUC_KHAN, type TinKeuCuu } from './tin-gia'

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

export function tinSangGeoJson(ds: TinKeuCuu[]): FeatureCollection<Point> {
  return {
    type: 'FeatureCollection',
    features: ds.map((t) => ({
      type: 'Feature',
      id: t.id,
      properties: { id: t.id, urgency: t.urgency, status: t.status, people_count: t.people_count },
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
