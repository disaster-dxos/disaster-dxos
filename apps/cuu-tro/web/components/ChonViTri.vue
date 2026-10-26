<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Chọn vị trí tin kêu cứu trên bản đồ khi duyệt tin AI (#104). Tin SMS/Zalo thường không có tọa độ, và AI
// không suy tọa độ từ địa chỉ (chống bịa, #102): người duyệt bấm vào bản đồ hoặc kéo ghim. Cùng kiểu nền
// với bản đồ điều phối (OpenFreeMap, nhãn tiếng Việt, dự phòng ô ảnh OpenStreetMap; chế độ tối).
import 'maplibre-gl/dist/maplibre-gl.css'
import type { Map as MlMap, Marker as MlMarker, StyleSpecification } from 'maplibre-gl'
import { QUAN_DAO, TAM_MAC_DINH, ZOOM_MAC_DINH, kieuDuPhongOsm, nhanTiengViet } from '~/utils/ban-do'

const props = defineProps<{ diem: [number, number] | null }>()
const emit = defineEmits<{ chon: [lngLat: { lng: number; lat: number }] }>()
const el = ref<HTMLDivElement>()
const colorMode = useColorMode()
let map: MlMap | undefined
let ghim: MlMarker | undefined

async function taiKieu(url: string): Promise<StyleSpecification> {
  try {
    const res = await fetch(url)
    if (!res.ok) throw new Error(String(res.status))
    return nhanTiengViet((await res.json()) as StyleSpecification)
  } catch {
    return kieuDuPhongOsm()
  }
}

function urlKieu(): string {
  const rc = useRuntimeConfig().public
  return (colorMode.value === 'dark' ? rc.mapStyleUrlToi : rc.mapStyleUrl) as string
}

async function datGhim(p: [number, number] | null, bay: boolean) {
  if (!map) return
  if (!p) {
    ghim?.remove()
    ghim = undefined
    return
  }
  if (!ghim) {
    const { Marker } = await import('maplibre-gl')
    ghim = new Marker({ color: '#F07B1D', draggable: true }).setLngLat(p).addTo(map)
    ghim.on('dragend', () => {
      const ll = ghim!.getLngLat()
      emit('chon', { lng: ll.lng, lat: ll.lat })
    })
  } else {
    ghim.setLngLat(p)
  }
  if (bay) map.flyTo({ center: p, zoom: Math.max(map.getZoom(), 14), duration: 600 })
}

onMounted(async () => {
  const { Map, NavigationControl, ScaleControl } = await import('maplibre-gl')
  const style = await taiKieu(urlKieu())
  if (!el.value) return
  const m = new Map({
    container: el.value,
    style,
    center: props.diem ?? TAM_MAC_DINH,
    zoom: props.diem ? 14 : ZOOM_MAC_DINH,
    attributionControl: { compact: true },
  })
  m.addControl(new NavigationControl({ visualizePitch: false, showCompass: false }), 'top-left')
  m.addControl(new ScaleControl({ unit: 'metric' }), 'bottom-right')
  // Ghi chú chủ quyền như bản đồ điều phối; kiểu dự phòng (ô ảnh) không có font chữ thì bỏ qua
  m.on('style.load', () => {
    if (!m.getStyle().glyphs || m.getLayer('quan-dao')) return
    const toi = colorMode.value === 'dark'
    m.addSource('quan-dao', { type: 'geojson', data: QUAN_DAO })
    m.addLayer({
      id: 'quan-dao', type: 'symbol', source: 'quan-dao',
      layout: { 'text-field': ['get', 'ten'], 'text-font': ['Noto Sans Bold'], 'text-size': 12 },
      paint: { 'text-color': toi ? '#C0D1E6' : '#12355B', 'text-halo-color': toi ? '#0B1F36' : '#ffffff', 'text-halo-width': 1.5 },
    })
  })
  m.getCanvas().style.cursor = 'crosshair'
  m.on('click', (e) => emit('chon', { lng: e.lngLat.lng, lat: e.lngLat.lat }))
  map = m
  await datGhim(props.diem, false)
})

// Ô tọa độ đổi (gõ tay, chọn tin khác) → ghim theo; bay tới khi điểm ra ngoài khung đang xem
watch(() => props.diem, (p) => {
  const ngoai = p && map ? !map.getBounds().contains(p) : false
  void datGhim(p, ngoai)
})
watch(() => colorMode.value, async () => {
  if (map) map.setStyle(await taiKieu(urlKieu()))
})

onBeforeUnmount(() => {
  ghim?.remove()
  map?.remove()
  map = undefined
})
</script>

<template>
  <!-- maplibre-gl.css đặt .maplibregl-map { position: relative } (ngoài @layer, thắng lớp tiện ích Tailwind):
       khung bản đồ dùng chiều cao cố định của phần tử cha, không dùng absolute inset-0 -->
  <div class="h-full min-h-64 overflow-hidden rounded-lg ring ring-default">
    <div ref="el" class="h-full w-full" role="application" aria-label="Bản đồ chọn vị trí tin kêu cứu: bấm để đặt ghim, kéo ghim để chỉnh" />
  </div>
</template>
