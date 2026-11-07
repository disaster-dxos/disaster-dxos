<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Nội dung popup một trạm đo mực nước (#62): cấp báo động, giá trị mới nhất, khoảng cách tới ngưỡng và biểu
// đồ nhỏ 24 giờ (vạch ngưỡng cảnh báo/nguy hiểm). BanDo.vue gắn phần tử này vào maplibregl.Popup.
import { GIO_LICH_SU, MUC_TRAM, bieuDo, dinhDangCm, khoangCachNguong, type DiemDo, type TramDo } from '~/utils/tram-do'

const props = defineProps<{ tram: TramDo | null; lichSu: DiemDo[] | null; loi?: string }>()
const RONG = 236
const CAO = 60
const bd = computed(() => props.tram && props.lichSu
  ? bieuDo(props.lichSu, RONG, CAO, { canhBao: props.tram.nguongCanhBao, nguyHiem: props.tram.nguongNguyHiem })
  : null)
const cuoiLuc = computed(() => {
  const d = props.lichSu?.at(-1)
  return d ? new Date(d.luc).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' }) : ''
})
const moTa = computed(() => {
  const t = props.tram
  if (!t || !props.lichSu?.length) return ''
  return `Mực nước ${GIO_LICH_SU} giờ qua của trạm ${t.ma}: từ ${dinhDangCm(Math.min(...props.lichSu.map((d) => d.giaTri)))} đến ${dinhDangCm(Math.max(...props.lichSu.map((d) => d.giaTri)))}`
})
</script>

<template>
  <div v-if="tram" class="w-[252px] space-y-2.5 text-xs" data-testid="popup-tram">
    <div class="flex items-start justify-between gap-2 border-b border-default pb-2">
      <div class="min-w-0">
        <p class="truncate text-sm font-bold text-highlighted" :title="tram.ten">{{ tram.ten }}</p>
        <p class="so font-mono text-muted">Trạm {{ tram.ma }}</p>
      </div>
      <span
        class="shrink-0 rounded px-2 py-0.5 font-bold text-white shadow-2xs"
        :style="{ background: MUC_TRAM[tram.muc].mau }"
      >{{ MUC_TRAM[tram.muc].nhan }}</span>
    </div>
    <div class="flex items-baseline justify-between gap-2">
      <p class="so text-2xl font-bold leading-none text-highlighted">{{ dinhDangCm(tram.mucNuoc) }}</p>
      <p v-if="khoangCachNguong(tram)" class="font-medium text-muted">{{ khoangCachNguong(tram) }}</p>
    </div>

    <div>
      <p v-if="loi" class="text-error">{{ loi }}</p>
      <p v-else-if="lichSu === null" class="text-muted">Đang tải chuỗi đo…</p>
      <p v-else-if="lichSu.length === 0" class="text-muted">Chưa có lần đo nào trong {{ GIO_LICH_SU }} giờ qua</p>
      <figure v-else-if="bd">
        <svg :width="RONG" :height="CAO" :viewBox="`0 0 ${RONG} ${CAO}`" role="img" :aria-label="moTa" class="block rounded-md bg-muted p-1 ring-1 ring-inset ring-default">
          <line v-if="bd.yNguyHiem !== null" x1="0" :x2="RONG" :y1="bd.yNguyHiem" :y2="bd.yNguyHiem" :stroke="MUC_TRAM.nguy_hiem.mau" stroke-dasharray="3 3" stroke-width="1" />
          <line v-if="bd.yCanhBao !== null" x1="0" :x2="RONG" :y1="bd.yCanhBao" :y2="bd.yCanhBao" :stroke="MUC_TRAM.canh_bao.mau" stroke-dasharray="3 3" stroke-width="1" />
          <path :d="bd.duong" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" class="text-nuoc-400" />
          <circle v-if="bd.cuoi" :cx="bd.cuoi.x" :cy="bd.cuoi.y" r="3.5" :fill="MUC_TRAM[tram.muc].mau" />
        </svg>
        <figcaption class="mt-1 flex justify-between text-muted">
          <span>{{ GIO_LICH_SU }} giờ · {{ lichSu.length }} lần đo</span>
          <span class="so font-mono">{{ cuoiLuc }}</span>
        </figcaption>
      </figure>
    </div>
    <p class="flex justify-between gap-2 border-t border-default pt-1.5 text-muted">
      <span v-if="tram.nguongCanhBao !== null">Cảnh báo <b class="so font-semibold text-default">{{ dinhDangCm(tram.nguongCanhBao) }}</b></span>
      <span v-if="tram.nguongNguyHiem !== null">Nguy hiểm <b class="so font-semibold text-default">{{ dinhDangCm(tram.nguongNguyHiem) }}</b></span>
    </p>
  </div>
</template>
