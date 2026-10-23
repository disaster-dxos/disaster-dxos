<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Bộ lọc tin theo trạng thái và mức khẩn (#60): áp cùng lúc cho bản đồ và danh sách. Số bên cạnh mỗi nút
// đếm trên toàn bộ tin nhận được (trước khi lọc).
import {
  DS_MUC_KHAN, DS_TRANG_THAI, MAU_TRANG_THAI, MUC_KHAN, TRANG_THAI, batTat, boLocMacDinh, demTheoMucKhan,
  demTheoTrangThai, type BoLoc, type TinKeuCuu,
} from '~/utils/tin'

const props = defineProps<{ ds: TinKeuCuu[] }>()
const loc = defineModel<BoLoc>({ required: true })
const demTT = computed(() => demTheoTrangThai(props.ds))
const demMK = computed(() => demTheoMucKhan(props.ds))
const macDinh = computed(() => JSON.stringify(loc.value) === JSON.stringify(boLocMacDinh()))
</script>

<template>
  <div class="space-y-2" role="group" aria-label="Lọc tin kêu cứu">
    <fieldset>
      <legend class="mb-1 text-[11px] font-bold uppercase tracking-wide text-slate-500">Trạng thái</legend>
      <div class="flex flex-wrap gap-1.5">
        <button
          v-for="s in DS_TRANG_THAI" :key="s" type="button"
          class="flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-bold focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-cam"
          :class="loc.trangThai.includes(s) ? 'border-navy bg-navy text-white' : 'border-slate-300 bg-white text-slate-500'"
          :aria-pressed="loc.trangThai.includes(s)"
          @click="loc = { ...loc, trangThai: batTat(loc.trangThai, s, DS_TRANG_THAI) }"
        >
          <span class="h-2.5 w-2.5 rounded-full border border-slate-400" :style="{ background: MAU_TRANG_THAI[s] }" aria-hidden="true" />
          {{ TRANG_THAI[s] }} <span class="font-normal opacity-80">{{ demTT[s] }}</span>
        </button>
      </div>
    </fieldset>
    <fieldset>
      <legend class="mb-1 text-[11px] font-bold uppercase tracking-wide text-slate-500">Mức khẩn</legend>
      <div class="flex flex-wrap items-center gap-1.5">
        <button
          v-for="k in DS_MUC_KHAN" :key="k" type="button"
          class="flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-bold focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-cam"
          :class="loc.mucKhan.includes(k) ? 'border-transparent text-white' : 'border-slate-300 bg-white text-slate-500'"
          :style="loc.mucKhan.includes(k) ? { background: MUC_KHAN[k].mau } : undefined"
          :aria-pressed="loc.mucKhan.includes(k)"
          @click="loc = { ...loc, mucKhan: batTat(loc.mucKhan, k, DS_MUC_KHAN) }"
        >
          {{ MUC_KHAN[k].nhan }} <span class="font-normal opacity-80">{{ demMK[k] }}</span>
        </button>
        <button
          v-if="!macDinh" type="button"
          class="ml-auto text-xs font-bold text-nuoc underline-offset-2 hover:underline"
          @click="loc = boLocMacDinh()"
        >
          Bỏ lọc
        </button>
      </div>
    </fieldset>
  </div>
</template>
