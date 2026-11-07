<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Chú thích bản đồ gọn: màu điểm = mức khẩn, màu viền = trạng thái; hình thoi = trạm đo mực nước theo cấp
// báo động (#62), kèm công tắc bật/tắt lớp trạm và số trạm từng cấp. Thu lại thành một nút khi không cần.
import { DS_MUC_KHAN, DS_TRANG_THAI, MUC_KHAN, TRANG_THAI, mauTrangThai } from '~/utils/tin'
import { DS_MUC_TRAM, MUC_TRAM, type MucTram } from '~/utils/tram-do'

const props = defineProps<{ demTram?: Record<MucTram, number> | null; loiTram?: string }>()
const hienTram = defineModel<boolean>('hienTram', { default: true })
const mo = ref(true)
const toi = useToi()
</script>

<template>
  <div class="overflow-hidden rounded-lg bg-elevated/95 text-xs shadow-lg ring-1 ring-default backdrop-blur">
    <UButton
      color="neutral" variant="ghost" size="sm" block class="justify-between rounded-none border-b border-default/60 px-3.5 py-2 font-bold text-highlighted"
      icon="i-lucide-layers"
      :trailing-icon="mo ? 'i-lucide-chevron-down' : 'i-lucide-chevron-up'" :aria-expanded="mo" aria-controls="chu-thich"
      @click="mo = !mo"
    >
      Chú thích ký hiệu bản đồ
    </UButton>
    <div v-show="mo" id="chu-thich" class="grid grid-cols-[auto_1fr] items-center gap-x-3.5 gap-y-2 px-3.5 py-2.5">
      <span class="font-semibold text-muted">Mức khẩn</span>
      <ul class="flex flex-wrap gap-x-3 gap-y-1">
        <li v-for="k in DS_MUC_KHAN" :key="k" class="flex items-center gap-1.5 font-medium text-default">
          <span class="size-3 rounded-full ring-1 ring-black/10" :style="{ background: MUC_KHAN[k].mau }" aria-hidden="true" />{{ MUC_KHAN[k].nhan }}
        </li>
      </ul>
      <span class="font-semibold text-muted">Trạng thái</span>
      <ul class="flex flex-wrap gap-x-3 gap-y-1">
        <li v-for="s in DS_TRANG_THAI" :key="s" class="flex items-center gap-1.5 font-medium text-default">
          <span class="size-3.5 rounded-full border-[3px] bg-elevated ring-1 ring-accented" :style="{ borderColor: mauTrangThai(s, toi) }" aria-hidden="true" />{{ TRANG_THAI[s] }}
        </li>
      </ul>
      <USwitch v-model="hienTram" size="xs" label="Trạm đo" class="col-span-1" :ui="{ label: 'text-muted font-semibold' }" />
      <ul class="flex flex-wrap gap-x-3 gap-y-1" :class="{ 'opacity-50': !hienTram }" aria-label="Cấp báo động trạm đo mực nước">
        <li v-for="m in DS_MUC_TRAM" :key="m" class="flex items-center gap-1.5 font-medium text-default">
          <span class="size-2.5 rotate-45 ring-1 ring-default" :style="{ background: MUC_TRAM[m].mau }" aria-hidden="true" />
          {{ MUC_TRAM[m].nhan }}
          <span v-if="props.demTram" class="so rounded bg-muted px-1 font-mono text-muted">{{ props.demTram[m] }}</span>
        </li>
      </ul>
      <p v-if="props.loiTram" class="col-span-2 text-error">{{ props.loiTram }}</p>
    </div>
  </div>
</template>
