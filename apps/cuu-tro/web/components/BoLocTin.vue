<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Bộ lọc tin theo trạng thái và mức khẩn (#60): áp cùng lúc cho bản đồ và danh sách. Số bên cạnh mỗi nút
// đếm trên toàn bộ tin nhận được (trước khi lọc). Nút tắt: viền nét đứt + gạch chữ (không chỉ dựa vào màu).
import {
  DS_MUC_KHAN, DS_TRANG_THAI, MUC_KHAN, TRANG_THAI, batTat, boLocMacDinh, demTheoMucKhan,
  demTheoTrangThai, type BoLoc, type TinKeuCuu,
  mauTrangThai,
} from '~/utils/tin'

const props = defineProps<{ ds: TinKeuCuu[] }>()
const loc = defineModel<BoLoc>({ required: true })
const demTT = computed(() => demTheoTrangThai(props.ds))
const demMK = computed(() => demTheoMucKhan(props.ds))
const macDinh = computed(() => JSON.stringify(loc.value) === JSON.stringify(boLocMacDinh()))
const lop = (bat: boolean) => (bat
  ? 'bg-primary/10 text-highlighted ring-primary/40 dark:bg-primary/20'
  : 'text-muted ring-accented ring-dashed line-through decoration-1')
const toi = useToi()
</script>

<template>
  <div class="space-y-3" role="group" aria-label="Lọc tin kêu cứu">
    <fieldset>
      <div class="mb-1.5 flex items-center justify-between">
        <legend class="text-xs font-semibold text-muted">Trạng thái</legend>
        <UButton v-if="!macDinh" size="xs" color="info" variant="link" icon="i-lucide-rotate-ccw" class="-my-1" @click="loc = boLocMacDinh()">Bỏ lọc</UButton>
      </div>
      <div class="flex flex-wrap gap-1.5">
        <UButton
          v-for="s in DS_TRANG_THAI" :key="s"
          color="neutral" variant="outline" size="sm" class="min-h-9 rounded-full ring-1"
          :class="lop(loc.trangThai.includes(s))"
          :aria-pressed="loc.trangThai.includes(s)"
          @click="loc = { ...loc, trangThai: batTat(loc.trangThai, s, DS_TRANG_THAI) }"
        >
          <span class="size-2.5 rounded-full ring-1 ring-accented" :style="{ background: mauTrangThai(s, toi) }" aria-hidden="true" />
          {{ TRANG_THAI[s] }} <span class="so font-normal no-underline">{{ demTT[s] }}</span>
        </UButton>
      </div>
    </fieldset>
    <fieldset>
      <legend class="mb-1.5 text-xs font-semibold text-muted">Mức khẩn</legend>
      <div class="flex flex-wrap gap-1.5">
        <UButton
          v-for="k in DS_MUC_KHAN" :key="k"
          color="neutral" variant="outline" size="sm" class="min-h-9 rounded-full ring-1"
          :class="lop(loc.mucKhan.includes(k))"
          :aria-pressed="loc.mucKhan.includes(k)"
          @click="loc = { ...loc, mucKhan: batTat(loc.mucKhan, k, DS_MUC_KHAN) }"
        >
          <span class="size-2.5 rounded-full" :style="{ background: MUC_KHAN[k].mau }" aria-hidden="true" />
          {{ MUC_KHAN[k].nhan }} <span class="so font-normal">{{ demMK[k] }}</span>
        </UButton>
      </div>
    </fieldset>
  </div>
</template>
