<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Nhãn trạng thái: nền trong, viền mảnh + chấm màu (= màu viền điểm trên bản đồ), khác hẳn nhãn mức khẩn.
import { TRANG_THAI, type TrangThai, mauTrangThai } from '~/utils/tin'

withDefaults(defineProps<{ tt: TrangThai; size?: 'sm' | 'md' | 'lg' }>(), { size: 'md' })
const toi = useToi()
</script>

<template>
  <UBadge color="neutral" variant="outline" :size="size" class="gap-1.5 whitespace-nowrap font-medium text-default">
    <span class="size-2.5 shrink-0 rounded-full ring-1 ring-accented" :style="{ background: mauTrangThai(tt, toi) }" aria-hidden="true" />
    {{ TRANG_THAI[tt] }}
  </UBadge>
</template>
