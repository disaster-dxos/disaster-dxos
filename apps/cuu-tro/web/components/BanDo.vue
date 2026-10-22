<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Bản đồ nền MapLibre GL JS + lớp tin kêu cứu. Kiểu nền vector OpenFreeMap (dữ liệu OpenStreetMap),
// nhãn đổi sang tiếng Việt; không tải được thì dùng ô ảnh OpenStreetMap. Nguồn: DEPENDENCIES.md.
import 'maplibre-gl/dist/maplibre-gl.css'
import type { GeoJSONSource, Map as MlMap, StyleSpecification } from 'maplibre-gl'
import {
  QUAN_DAO, TAM_MAC_DINH, ZOOM_MAC_DINH, bieuThucMauKhan, kieuDuPhongOsm, nhanTiengViet, tinSangGeoJson, toaDoHopLe,
} from '~/utils/ban-do'
import type { TinKeuCuu } from '~/utils/tin-gia'

const props = defineProps<{ ds: TinKeuCuu[]; chon: string | null }>()
const emit = defineEmits<{ chon: [id: string] }>()
const el = ref<HTMLDivElement>()
const loiNen = ref(false)
let map: MlMap | undefined

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

function themLop(m: MlMap) {
  m.addSource('tin', { type: 'geojson', data: tinSangGeoJson(props.ds) })
  m.addLayer({
    id: 'tin-vien-chon', type: 'circle', source: 'tin',
    filter: ['==', ['get', 'id'], props.chon ?? ''],
    paint: { 'circle-radius': 16, 'circle-color': '#1FA2C9', 'circle-opacity': 0.35 },
  })
  m.addLayer({
    id: 'tin', type: 'circle', source: 'tin',
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['get', 'people_count'], 1, 7, 10, 12],
      'circle-color': bieuThucMauKhan() as never,
      'circle-stroke-color': '#ffffff',
      'circle-stroke-width': 2,
      'circle-opacity': ['match', ['get', 'status'], ['da_cuu', 'dong'], 0.45, 1],
    },
  })
  if (m.getStyle().glyphs) {
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
  m.on('mouseenter', 'tin', () => { m.getCanvas().style.cursor = 'pointer' })
  m.on('mouseleave', 'tin', () => { m.getCanvas().style.cursor = '' })
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

onBeforeUnmount(() => map?.remove())

watch(() => props.ds, (ds: TinKeuCuu[]) => {
  (map?.getSource('tin') as GeoJSONSource | undefined)?.setData(tinSangGeoJson(ds))
}, { deep: true })

watch(() => props.chon, (id: string | null) => {
  if (!map?.getLayer('tin-vien-chon')) return
  map.setFilter('tin-vien-chon', ['==', ['get', 'id'], id ?? ''])
  const t = props.ds.find((x) => x.id === id)
  if (t && toaDoHopLe(t.location)) map.flyTo({ center: t.location, zoom: Math.max(map.getZoom(), 12.5), speed: 1.2 })
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
