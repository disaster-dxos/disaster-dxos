<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Bản đồ nền MapLibre GL JS + lớp tin kêu cứu thời gian thực (#60). Kiểu nền vector OpenFreeMap (dữ liệu
// OpenStreetMap), nhãn đổi sang tiếng Việt; không tải được thì dùng ô ảnh OpenStreetMap. Nguồn: DEPENDENCIES.md.
// Điểm: màu nền theo mức khẩn, màu viền theo trạng thái; nhiều điểm gần nhau thì gom cụm (cụm đỏ nếu có tin
// khẩn cấp); tin vừa đến có vòng nhấp nháy. Bấm điểm → chọn (danh sách và ô chi tiết bên cạnh đồng bộ).
import 'maplibre-gl/dist/maplibre-gl.css'
import type { GeoJSONSource, Map as MlMap, StyleSpecification } from 'maplibre-gl'
import {
  CUM_BAN_KINH, CUM_ZOOM_TOI_DA, QUAN_DAO, TAM_MAC_DINH, THUOC_TINH_CUM, ZOOM_MAC_DINH, bieuThucMauCum,
  bieuThucMauKhan, bieuThucMauTrangThai, kieuDuPhongOsm, nhanTiengViet, tinSangGeoJson, toaDoHopLe, zoomChon,
} from '~/utils/ban-do'
import type { TinKeuCuu } from '~/utils/tin'

const props = defineProps<{ ds: TinKeuCuu[]; moi: Map<string, number>; chon: string | null }>()
const emit = defineEmits<{ chon: [id: string] }>()
const el = ref<HTMLDivElement>()
const loiNen = ref(false)
let map: MlMap | undefined
let henNhapNhay: ReturnType<typeof setInterval> | undefined

const KHONG_CO_DIEM = { type: 'FeatureCollection', features: [] } as const
const LA_DIEM = ['!', ['has', 'point_count']]

async function taiKieu(url: string): Promise<StyleSpecification> {
  try {
    const res = await fetch(url)
    if (!res.ok) throw new Error(String(res.status))
    return nhanTiengViet((await res.json()) as StyleSpecification)
  } catch {
    loiNen.value = true
    return kieuDuPhongOsm()
  }
}

function duLieuChon(id: string | null) {
  const t = id ? props.ds.find((x) => x.id === id) : undefined
  return t ? tinSangGeoJson([t]) : KHONG_CO_DIEM
}

function themLop(m: MlMap) {
  m.addSource('tin', {
    type: 'geojson',
    data: tinSangGeoJson(props.ds, props.moi),
    cluster: true,
    clusterMaxZoom: CUM_ZOOM_TOI_DA,
    clusterRadius: CUM_BAN_KINH,
    clusterProperties: THUOC_TINH_CUM as never,
  })
  // Nguồn riêng (không gom cụm) cho vòng đánh dấu điểm đang chọn
  m.addSource('tin-chon', { type: 'geojson', data: duLieuChon(props.chon) as never })
  m.addLayer({
    id: 'cum', type: 'circle', source: 'tin', filter: ['has', 'point_count'],
    paint: {
      'circle-color': bieuThucMauCum() as never,
      'circle-radius': ['step', ['get', 'point_count'], 16, 10, 21, 50, 27],
      'circle-stroke-color': '#ffffff',
      'circle-stroke-width': 3,
      'circle-opacity': 0.9,
    },
  })
  const coChu = !!m.getStyle().glyphs
  if (coChu) {
    m.addLayer({
      id: 'cum-so', type: 'symbol', source: 'tin', filter: ['has', 'point_count'],
      layout: { 'text-field': ['get', 'point_count_abbreviated'], 'text-font': ['Noto Sans Bold'], 'text-size': 13, 'text-allow-overlap': true },
      paint: { 'text-color': '#ffffff' },
    })
  }
  m.addLayer({
    id: 'tin-vien-chon', type: 'circle', source: 'tin-chon',
    paint: { 'circle-radius': 20, 'circle-color': '#1FA2C9', 'circle-opacity': 0.3, 'circle-stroke-color': '#1FA2C9', 'circle-stroke-width': 2 },
  })
  m.addLayer({
    id: 'tin-moi', type: 'circle', source: 'tin',
    filter: ['all', LA_DIEM, ['==', ['get', 'moi'], true]] as never,
    paint: { 'circle-radius': 16, 'circle-color': bieuThucMauKhan() as never, 'circle-opacity': 0.4 },
  })
  m.addLayer({
    id: 'tin', type: 'circle', source: 'tin', filter: LA_DIEM as never,
    paint: {
      'circle-radius': ['match', ['get', 'urgency'], 'khan_cap', 10, 'cao', 9, 8],
      'circle-color': bieuThucMauKhan() as never,
      'circle-stroke-color': bieuThucMauTrangThai() as never,
      'circle-stroke-width': 3,
      'circle-opacity': ['match', ['get', 'status'], ['da_cuu', 'dong'], 0.5, 1],
      'circle-stroke-opacity': ['match', ['get', 'status'], ['da_cuu', 'dong'], 0.6, 1],
    },
  })
  if (coChu) {
    m.addSource('quan-dao', { type: 'geojson', data: QUAN_DAO })
    m.addLayer({
      id: 'quan-dao', type: 'symbol', source: 'quan-dao',
      layout: { 'text-field': ['get', 'ten'], 'text-font': ['Noto Sans Bold'], 'text-size': 12 },
      paint: { 'text-color': '#12355B', 'text-halo-color': '#ffffff', 'text-halo-width': 1.5 },
    })
  }
  m.on('click', 'tin', (e) => {
    const id = e.features?.[0]?.properties?.id
    if (typeof id === 'string') emit('chon', id)
  })
  // Bấm cụm → phóng to tới mức cụm tách ra
  m.on('click', 'cum', async (e) => {
    const f = e.features?.[0]
    const cid = f?.properties?.cluster_id
    if (!f || typeof cid !== 'number') return
    const z = await (m.getSource('tin') as GeoJSONSource).getClusterExpansionZoom(cid)
    m.easeTo({ center: (f.geometry as GeoJSON.Point).coordinates as [number, number], zoom: z })
  })
  for (const lop of ['tin', 'cum']) {
    m.on('mouseenter', lop, () => { m.getCanvas().style.cursor = 'pointer' })
    m.on('mouseleave', lop, () => { m.getCanvas().style.cursor = '' })
  }
  batNhapNhay(m)
}

/** Vòng quanh tin mới phóng to và mờ dần (chu kỳ 1,6 giây); người dùng giảm chuyển động thì để vòng tĩnh. */
function batNhapNhay(m: MlMap) {
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return
  const batDau = performance.now()
  // setInterval thay vì requestAnimationFrame: rAF dừng khi tab ẩn, còn ở đây chỉ đổi 2 thuộc tính
  henNhapNhay = setInterval(() => {
    if (props.moi.size === 0 || !m.getLayer('tin-moi')) return
    const p = ((performance.now() - batDau) % 1600) / 1600
    m.setPaintProperty('tin-moi', 'circle-radius', 10 + 16 * p)
    m.setPaintProperty('tin-moi', 'circle-opacity', 0.55 * (1 - p))
  }, 80)
}

onMounted(async () => {
  const { Map, NavigationControl, ScaleControl } = await import('maplibre-gl')
  const style = await taiKieu(useRuntimeConfig().public.mapStyleUrl as string)
  if (!el.value) return
  const m = new Map({
    container: el.value,
    style,
    center: TAM_MAC_DINH,
    zoom: ZOOM_MAC_DINH,
    attributionControl: { compact: false },
  })
  m.addControl(new NavigationControl({ visualizePitch: false }), 'top-left')
  m.addControl(new ScaleControl({ unit: 'metric' }), 'bottom-left')
  m.on('load', () => themLop(m))
  map = m
})

onBeforeUnmount(() => {
  clearInterval(henNhapNhay)
  map?.remove()
})

watch([() => props.ds, () => props.moi], () => {
  (map?.getSource('tin') as GeoJSONSource | undefined)?.setData(tinSangGeoJson(props.ds, props.moi))
  ;(map?.getSource('tin-chon') as GeoJSONSource | undefined)?.setData(duLieuChon(props.chon) as never)
})

watch(() => props.chon, (id: string | null) => {
  if (!map?.getSource('tin-chon')) return
  ;(map.getSource('tin-chon') as GeoJSONSource).setData(duLieuChon(id) as never)
  const t = props.ds.find((x) => x.id === id)
  if (t && toaDoHopLe(t.location)) map.flyTo({ center: t.location, zoom: zoomChon(map.getZoom()), speed: 1.2 })
})
</script>

<template>
  <div class="relative h-full w-full">
    <div ref="el" class="h-full w-full" role="region" aria-label="Bản đồ tin kêu cứu" />
    <p v-if="loiNen" class="absolute right-2 top-2 rounded bg-white/90 px-2 py-1 text-xs shadow">
      Không tải được bản đồ nền vector, đang dùng ô ảnh OpenStreetMap
    </p>
  </div>
</template>
