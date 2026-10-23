<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Nhãn mức khẩn: nền đặc, chữ trắng đạt AA. "Khẩn cấp" có thêm biểu tượng (không chỉ dựa vào màu).
import { MUC_KHAN, type MucKhan } from '~/utils/tin'

const props = withDefaults(defineProps<{ muc: MucKhan; size?: 'sm' | 'md' | 'lg' }>(), { size: 'md' })
const MAU = { khan_cap: 'error', cao: 'warning', trung_binh: 'info', thap: 'neutral' } as const
const lop = computed(() => (props.muc === 'thap' ? 'bg-thap text-white' : ''))
</script>

<template>
  <UBadge
    :color="MAU[muc]" variant="solid" :size="size" :class="lop" class="whitespace-nowrap font-semibold"
    :icon="muc === 'khan_cap' ? 'i-lucide-triangle-alert' : undefined"
  >
    {{ MUC_KHAN[muc].nhan }}
  </UBadge>
</template>
