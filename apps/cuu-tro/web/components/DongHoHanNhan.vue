<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Đồng hồ hạn nhận: số đều, nền cam nhạt chữ cam đậm (6,79:1); dưới 1 phút đổi hẳn nền đỏ chữ trắng.
// lon = true: khối lớn cho màn chi tiết (điện thoại, đọc từ xa, ngoài nắng).
import { demNguoc, tiLeDaQua, type LanGiao } from '~/utils/phan-cong'

const props = defineProps<{ giao: Pick<LanGiao, 'giaoLuc' | 'hanLuc'>; now: number; lon?: boolean }>()
const dem = computed(() => demNguoc(props.giao.hanLuc, props.now))
const tiLe = computed(() => Math.round(tiLeDaQua(props.giao, props.now) * 100))
</script>

<template>
  <div
    v-if="lon"
    class="rounded-lg p-4 ring ring-inset"
    :class="dem.gap ? 'bg-khan-500 text-white ring-khan-500' : 'bg-cam-50 text-cam-800 ring-cam-200 dark:bg-cam-950/50 dark:text-cam-200 dark:ring-cam-900'"
  >
    <div class="flex items-center justify-between gap-3">
      <p class="flex items-center gap-2 text-base font-semibold">
        <UIcon name="i-lucide-timer" class="size-6" />Hạn nhận còn
      </p>
      <p class="so text-5xl font-bold leading-none tracking-tight" role="timer" :aria-label="`Hạn nhận còn ${dem.nhan}`">{{ dem.nhan }}</p>
    </div>
    <div class="mt-3 h-2.5 overflow-hidden rounded-full" :class="dem.gap ? 'bg-white/30' : 'bg-cam-200 dark:bg-cam-900'" aria-hidden="true">
      <div class="h-full rounded-full" :class="dem.gap ? 'bg-white' : 'bg-cam-500'" :style="{ width: `${tiLe}%` }" />
    </div>
  </div>
  <span
    v-else
    class="so inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-base font-bold leading-none"
    :class="dem.gap ? 'bg-khan-500 text-white' : 'bg-cam-50 text-cam-800 ring ring-inset ring-cam-200 dark:bg-cam-950/50 dark:text-cam-200 dark:ring-cam-900'"
    :title="`Hạn nhận còn ${dem.nhan}`"
  >
    <UIcon name="i-lucide-timer" class="size-4" />{{ dem.nhan }}
  </span>
</template>
