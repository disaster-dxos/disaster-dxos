<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Bản đồ nền MapLibre GL JS + lớp tin kêu cứu thời gian thực (#60). Kiểu nền vector OpenFreeMap (dữ liệu
// OpenStreetMap), nhãn đổi sang tiếng Việt; không tải được thì dùng ô ảnh OpenStreetMap. Nguồn: DEPENDENCIES.md.
// Điểm: màu nền theo mức khẩn, màu viền theo trạng thái; nhiều điểm gần nhau thì gom cụm (cụm đỏ nếu có tin
// khẩn cấp); tin vừa đến có vòng nhấp nháy. Bấm điểm → chọn (danh sách và ngăn chi tiết đồng bộ).
// Giao diện tối → kiểu nền tối của OpenFreeMap; đổi kiểu nền thì thêm lại các lớp (sự kiện style.load).
// Lớp trạm đo mực nước (#62): hình thoi màu theo cấp báo động, nằm dưới lớp tin kêu cứu; bấm trạm → popup
// giá trị mới nhất + biểu đồ nhỏ 24 giờ (components/PopupTram.vue). Bật/tắt lớp bằng prop hienTram.
import 'maplibre-gl/dist/maplibre-gl.css'
import type { GeoJSONSource, Map as MlMap, Popup as MlPopup, StyleSpecification } from 'maplibre-gl'
import {
  CUM_BAN_KINH, CUM_ZOOM_TOI_DA, QUAN_DAO, TAM_MAC_DINH, THUOC_TINH_CUM, ZOOM_MAC_DINH, bieuThucMauCum,
  bieuThucMauKhan, bieuThucMauTrangThai, kieuDuPhongOsm, nhanTiengViet, tinSangGeoJson, toaDoHopLe, zoomChon,
} from '~/utils/ban-do'
import type { TinKeuCuu } from '~/utils/tin'
import { DS_MUC_TRAM, MUC_TRAM, tramSangGeoJson, type DiemDo, type TramDo } from '~/utils/tram-do'

// dePhai: bề rộng (px) ngăn chi tiết che bên phải bản đồ, để điểm được chọn bay vào giữa phần còn thấy
const props = withDefaults(defineProps<{
  ds: TinKeuCuu[]; moi: Map<string, number>; chon: string | null; dePhai?: number
  tram?: TramDo[]; hienTram?: boolean
}>(), { dePhai: 0, tram: () => [], hienTram: true })
const emit = defineEmits<{ chon: [id: string] }>()
const el = ref<HTMLDivElement>()
const popupEl = ref<HTMLDivElement>()
const { layLichSu } = useTramDo()
const tramChon = ref<string | null>(null)
const lichSu = ref<DiemDo[] | null>(null)
const loiLichSu = ref('')
const tramDangMo = computed(() => props.tram.find((t) => t.ma === tramChon.value) ?? null)
let popup: MlPopup | undefined
const loiNen = ref(false)
const colorMode = useColorMode()
const toi = computed(() => colorMode.value === 'dark')
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

/** Biểu tượng hình thoi cho từng cấp báo động (vẽ bằng canvas; đổi kiểu nền thì phải thêm lại). */
function themBieuTuongTram(m: MlMap, vien: string) {
  const r = window.devicePixelRatio > 1 ? 2 : 1
  const n = 22 * r
  for (const muc of DS_MUC_TRAM) {
    const ten = `tram-${muc}`
    if (m.hasImage(ten)) continue
    const c = document.createElement('canvas')
    c.width = c.height = n
    const g = c.getContext('2d')
    if (!g) return
    g.beginPath()
    g.moveTo(n / 2, 2 * r); g.lineTo(n - 2 * r, n / 2); g.lineTo(n / 2, n - 2 * r); g.lineTo(2 * r, n / 2); g.closePath()
    g.fillStyle = MUC_TRAM[muc].mau
    g.fill()
    g.lineWidth = 2.5 * r
    g.strokeStyle = vien
    g.stroke()
    // Vạch sóng nước ở giữa
    g.beginPath()
    g.moveTo(n * 0.33, n / 2); g.lineTo(n * 0.67, n / 2)
    g.strokeStyle = '#ffffff'
    g.lineWidth = 2 * r
    g.stroke()
    m.addImage(ten, g.getImageData(0, 0, n, n), { pixelRatio: r })
  }
}

function themLopTram(m: MlMap, coChu: boolean, nenDiem: string) {
  themBieuTuongTram(m, nenDiem)
  const hien = props.hienTram ? 'visible' : 'none'
  m.addSource('tram', { type: 'geojson', data: tramSangGeoJson(props.tram) as never })
  m.addLayer({
    id: 'tram', type: 'symbol', source: 'tram',
    layout: {
      'visibility': hien,
      'icon-image': ['concat', 'tram-', ['get', 'muc']] as never,
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
      // Nguy hiểm vẽ trên cùng
      'symbol-sort-key': ['-', 2, ['get', 'thuTu']] as never,
    },
  })
  if (coChu) {
    m.addLayer({
      id: 'tram-nhan', type: 'symbol', source: 'tram', minzoom: 11,
      layout: {
        'visibility': hien,
        'text-field': ['get', 'nhan'], 'text-font': ['Noto Sans Bold'], 'text-size': 11,
        'text-offset': [0, 1.25], 'text-anchor': 'top', 'text-optional': true,
      },
      paint: { 'text-color': toi.value ? '#C0D1E6' : '#12355B', 'text-halo-color': nenDiem, 'text-halo-width': 1.5 },
    })
  }
}

function themLop(m: MlMap) {
  if (m.getSource('tin')) return
  const nenDiem = toi.value ? '#0B1626' : '#ffffff'
  // Trạm đo thêm trước: nằm dưới các điểm tin kêu cứu (tin quan trọng hơn khi chồng nhau)
  themLopTram(m, !!m.getStyle().glyphs, nenDiem)
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
      'circle-color': bieuThucMauCum(toi.value) as never,
      'circle-radius': ['step', ['get', 'point_count'], 16, 10, 21, 50, 27],
      'circle-stroke-color': nenDiem,
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
      'circle-stroke-color': bieuThucMauTrangThai(toi.value) as never,
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
      paint: { 'text-color': toi.value ? '#C0D1E6' : '#12355B', 'text-halo-color': nenDiem, 'text-halo-width': 1.5 },
    })
  }
}

/** Sự kiện gắn theo id lớp: gắn một lần, vẫn chạy sau khi đổi kiểu nền (lớp được thêm lại cùng id). */
function ganSuKien(m: MlMap) {
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
  m.on('click', 'tram', (e) => {
    // Bấm trúng cả tin kêu cứu → ưu tiên tin (handler 'tin'/'cum' đã xử lý)
    if (m.queryRenderedFeatures(e.point, { layers: ['tin', 'cum'].filter((l) => m.getLayer(l)) }).length) return
    const ma = e.features?.[0]?.properties?.ma
    if (typeof ma === 'string') void moPopupTram(m, ma)
  })
  for (const lop of ['tin', 'cum', 'tram']) {
    m.on('mouseenter', lop, () => { m.getCanvas().style.cursor = 'pointer' })
    m.on('mouseleave', lop, () => { m.getCanvas().style.cursor = '' })
  }
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

async function taiLichSu(ma: string) {
  loiLichSu.value = ''
  try {
    const ds = await layLichSu(ma)
    if (tramChon.value === ma) lichSu.value = ds
  } catch (e) {
    if (tramChon.value === ma) loiLichSu.value = e instanceof Error ? e.message : String(e)
  }
}

async function moPopupTram(m: MlMap, ma: string) {
  const t = props.tram.find((x) => x.ma === ma)
  if (!t || !popupEl.value) return
  tramChon.value = ma
  lichSu.value = null
  if (!popup) {
    const { Popup } = await import('maplibre-gl')
    popup = new Popup({ className: 'popup-tram', maxWidth: '280px', offset: 12, focusAfterOpen: false })
    popup.on('close', () => { tramChon.value = null })
  }
  popup.setLngLat(t.location).setDOMContent(popupEl.value).addTo(m)
  await taiLichSu(ma)
}

onMounted(async () => {
  const { Map, NavigationControl, ScaleControl } = await import('maplibre-gl')
  const style = await taiKieu(urlKieu())
  if (!el.value) return
  const m = new Map({
    container: el.value,
    style,
    center: TAM_MAC_DINH,
    zoom: ZOOM_MAC_DINH,
    attributionControl: { compact: false },
  })
  m.addControl(new NavigationControl({ visualizePitch: false }), 'top-left')
  m.addControl(new ScaleControl({ unit: 'metric' }), 'bottom-right')
  m.on('style.load', () => themLop(m))
  ganSuKien(m)
  batNhapNhay(m)
  map = m
})

function urlKieu() {
  const rc = useRuntimeConfig().public
  return (toi.value ? rc.mapStyleUrlToi : rc.mapStyleUrl) as string
}

watch(toi, async () => {
  if (!map) return
  loiNen.value = false
  map.setStyle(await taiKieu(urlKieu()), { diff: false })
})

onBeforeUnmount(() => {
  clearInterval(henNhapNhay)
  popup?.remove()
  map?.remove()
})

// Danh sách trạm tải lại (định kỳ hoặc do cảnh báo realtime): vẽ lại; popup đang mở thì tải lại chuỗi đo khi
// trạm có lần đo mới, trạm biến mất thì đóng popup
watch(() => props.tram, (ds, cu) => {
  (map?.getSource('tram') as GeoJSONSource | undefined)?.setData(tramSangGeoJson(ds) as never)
  if (!tramChon.value) return
  const t = ds.find((x) => x.ma === tramChon.value)
  if (!t) { popup?.remove(); return }
  const truoc = cu?.find((x) => x.ma === t.ma)
  if (truoc && (truoc.mucNuoc !== t.mucNuoc || truoc.muc !== t.muc)) void taiLichSu(t.ma)
})

watch(() => props.hienTram, (hien) => {
  for (const lop of ['tram', 'tram-nhan']) {
    if (map?.getLayer(lop)) map.setLayoutProperty(lop, 'visibility', hien ? 'visible' : 'none')
  }
  if (!hien) popup?.remove()
})

watch([() => props.ds, () => props.moi], () => {
  (map?.getSource('tin') as GeoJSONSource | undefined)?.setData(tinSangGeoJson(props.ds, props.moi))
  ;(map?.getSource('tin-chon') as GeoJSONSource | undefined)?.setData(duLieuChon(props.chon) as never)
})

watch(() => props.chon, (id: string | null) => {
  if (!map?.getSource('tin-chon')) return
  ;(map.getSource('tin-chon') as GeoJSONSource).setData(duLieuChon(id) as never)
  const t = props.ds.find((x) => x.id === id)
  if (t && toaDoHopLe(t.location)) {
    map.flyTo({ center: t.location, zoom: zoomChon(map.getZoom()), speed: 1.2, padding: { top: 0, bottom: 0, left: 0, right: props.dePhai ?? 0 } })
  }
})
</script>

<template>
  <div class="relative h-full w-full">
    <div ref="el" class="h-full w-full" role="region" aria-label="Bản đồ tin kêu cứu và trạm đo mực nước" />
    <!-- Nội dung popup trạm đo: MapLibre chuyển phần tử này vào khung popup khi mở -->
    <div class="hidden">
      <div ref="popupEl">
        <PopupTram :tram="tramDangMo" :lich-su="lichSu" :loi="loiLichSu" />
      </div>
    </div>
    <p v-if="loiNen" class="absolute bottom-16 right-3 rounded-md bg-default/95 px-2.5 py-1.5 text-xs text-muted shadow ring ring-default">
      Không tải được bản đồ nền vector, đang dùng ô ảnh OpenStreetMap
    </p>
  </div>
</template>

<style>
/* Popup trạm đo theo màu giao diện (sáng/tối) của Nuxt UI */
.popup-tram .maplibregl-popup-content {
  background: var(--ui-bg);
  color: var(--ui-text);
  border-radius: var(--ui-radius, 0.375rem);
  box-shadow: 0 4px 16px rgb(0 0 0 / 0.25);
  padding: 12px 14px;
  outline: 1px solid var(--ui-border);
}
.popup-tram .maplibregl-popup-close-button { color: var(--ui-text-muted); font-size: 18px; padding: 0 6px; }
.popup-tram.maplibregl-popup-anchor-top .maplibregl-popup-tip,
.popup-tram.maplibregl-popup-anchor-top-left .maplibregl-popup-tip,
.popup-tram.maplibregl-popup-anchor-top-right .maplibregl-popup-tip { border-bottom-color: var(--ui-bg); }
.popup-tram.maplibregl-popup-anchor-bottom .maplibregl-popup-tip,
.popup-tram.maplibregl-popup-anchor-bottom-left .maplibregl-popup-tip,
.popup-tram.maplibregl-popup-anchor-bottom-right .maplibregl-popup-tip { border-top-color: var(--ui-bg); }
.popup-tram.maplibregl-popup-anchor-left .maplibregl-popup-tip { border-right-color: var(--ui-bg); }
.popup-tram.maplibregl-popup-anchor-right .maplibregl-popup-tip { border-left-color: var(--ui-bg); }
</style>
