<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Thẻ một tin trong hàng đợi phân công (#61): mức khẩn, mô tả ngắn, đội đang giao, đồng hồ hạn nhận. Bấm
// thẻ → màn chi tiết phân công. Không có SĐT (chỉ hiện ở màn chi tiết, theo vai).
import { giaoDangCho, tiLeDaQua, tomTatGiao, type TinPhanCong } from '~/utils/phan-cong'
import { maNgan, thoiGianTruoc } from '~/utils/tin'

const props = defineProps<{ tin: TinPhanCong; now: number; canXuLy?: boolean }>()
const cho = computed(() => giaoDangCho(props.tin))
</script>

<template>
  <NuxtLink
    :to="`/phan-cong/${tin.id}`"
    class="group block rounded-lg bg-elevated p-3.5 shadow-2xs ring-1 transition hover:shadow-md hover:ring-info/60"
    :class="canXuLy ? 'ring-2 ring-error/70' : 'ring-default'"
  >
    <span class="flex flex-wrap items-center gap-1.5">
      <NhanMucKhan :muc="tin.urgency" />
      <NhanTrangThai v-if="canXuLy" :tt="tin.status" />
      <time class="so ms-auto text-xs font-medium text-muted" :datetime="tin.created_at">{{ thoiGianTruoc(tin.created_at, now) }}</time>
    </span>
    <span class="mt-2 line-clamp-2 block text-base font-bold leading-snug text-highlighted group-hover:text-primary dark:group-hover:text-nuoc-300">{{ tin.description || 'Không có mô tả' }}</span>
    <span class="mt-1.5 flex items-center gap-1.5 text-sm text-muted">
      <UIcon name="i-lucide-map-pin" class="size-4 shrink-0 text-dimmed" />
      <span class="truncate">{{ tin.address_text || 'Chưa có địa chỉ' }}</span>
      <span class="so ms-auto flex shrink-0 items-center gap-1 rounded bg-muted px-1.5 py-0.5 font-semibold text-highlighted ring-1 ring-inset ring-default">
        <UIcon name="i-lucide-users" class="size-3.5 text-info" />{{ tin.people_count }}
      </span>
    </span>
    <span class="mt-3 flex items-center gap-2 border-t border-default pt-2.5">
      <span class="min-w-0 flex-1">
        <span class="block truncate text-sm font-semibold text-default">{{ tomTatGiao(tin) }}</span>
        <span class="mt-0.5 inline-block rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-muted">{{ maNgan(tin.id) }}</span>
      </span>
      <DongHoHanNhan v-if="cho" :giao="cho" :now="now" />
    </span>
    <span v-if="cho" class="mt-2 block h-1.5 overflow-hidden rounded-full bg-cam-100 dark:bg-cam-950" aria-hidden="true">
      <span class="block h-full rounded-full bg-cam-500 transition-[width] duration-300" :style="{ width: `${Math.round(tiLeDaQua(cho, now) * 100)}%` }" />
    </span>
  </NuxtLink>
</template>
