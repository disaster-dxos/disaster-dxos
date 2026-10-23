<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Chú thích bản đồ gọn: màu điểm = mức khẩn, màu viền = trạng thái. Thu lại thành một nút khi không cần.
import { DS_MUC_KHAN, DS_TRANG_THAI, MUC_KHAN, TRANG_THAI, mauTrangThai } from '~/utils/tin'

const mo = ref(true)
const toi = useToi()
</script>

<template>
  <div class="rounded-md bg-default/95 text-xs shadow-md ring ring-default backdrop-blur">
    <UButton
      color="neutral" variant="ghost" size="sm" block class="justify-between px-3 font-semibold"
      :trailing-icon="mo ? 'i-lucide-chevron-down' : 'i-lucide-chevron-up'" :aria-expanded="mo" aria-controls="chu-thich"
      @click="mo = !mo"
    >
      Chú thích
    </UButton>
    <div v-show="mo" id="chu-thich" class="grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-1.5 px-3 pb-3">
      <span class="text-muted">Mức khẩn</span>
      <ul class="flex flex-wrap gap-x-3 gap-y-1">
        <li v-for="k in DS_MUC_KHAN" :key="k" class="flex items-center gap-1.5">
          <span class="size-3 rounded-full" :style="{ background: MUC_KHAN[k].mau }" aria-hidden="true" />{{ MUC_KHAN[k].nhan }}
        </li>
      </ul>
      <span class="text-muted">Viền</span>
      <ul class="flex flex-wrap gap-x-3 gap-y-1">
        <li v-for="s in DS_TRANG_THAI" :key="s" class="flex items-center gap-1.5">
          <span class="size-3.5 rounded-full border-[3px] bg-accented ring-1 ring-accented" :style="{ borderColor: mauTrangThai(s, toi) }" aria-hidden="true" />{{ TRANG_THAI[s] }}
        </li>
      </ul>
    </div>
  </div>
</template>
