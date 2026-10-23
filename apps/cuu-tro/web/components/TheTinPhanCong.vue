<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Thẻ một tin trong hàng đợi phân công (#61): mức khẩn, trạng thái, mô tả ngắn, đội đang giao, đếm ngược
// hạn nhận. Bấm thẻ → màn chi tiết phân công. Không có SĐT (chỉ hiện ở màn chi tiết, theo vai).
import { demNguoc, giaoDangCho, tiLeDaQua, tomTatGiao, type TinPhanCong } from '~/utils/phan-cong'
import { MUC_KHAN, TRANG_THAI, maNgan, thoiGianTruoc } from '~/utils/tin'

const props = defineProps<{ tin: TinPhanCong; now: number; canXuLy?: boolean }>()
const cho = computed(() => giaoDangCho(props.tin))
const dem = computed(() => (cho.value ? demNguoc(cho.value.hanLuc, props.now) : null))
</script>

<template>
  <NuxtLink
    :to="`/phan-cong/${tin.id}`"
    class="block rounded-xl border border-slate-200 bg-white p-3 shadow-sm hover:border-nuoc hover:shadow focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cam"
    :class="canXuLy ? 'border-l-4 border-l-red-600' : ''"
  >
    <span class="flex flex-wrap items-center gap-1.5 text-xs">
      <span v-if="canXuLy" class="rounded bg-red-600 px-1.5 py-0.5 font-bold text-white">Cần xử lý</span>
      <span class="rounded px-1.5 py-0.5 font-bold text-white" :style="{ background: MUC_KHAN[tin.urgency].mau }">{{ MUC_KHAN[tin.urgency].nhan }}</span>
      <span class="rounded bg-slate-200 px-1.5 py-0.5 font-bold text-slate-700">{{ TRANG_THAI[tin.status] }}</span>
      <span class="font-mono text-slate-500">{{ maNgan(tin.id) }}</span>
      <time class="ml-auto text-slate-500" :datetime="tin.created_at">{{ thoiGianTruoc(tin.created_at, now) }}</time>
    </span>
    <span class="mt-1.5 line-clamp-2 block text-sm font-bold text-chu">{{ tin.description || 'Không có mô tả' }}</span>
    <span class="mt-0.5 block truncate text-xs text-slate-600">{{ tin.address_text || 'Chưa có địa chỉ' }} · {{ tin.people_count }} người</span>
    <span class="mt-2 flex items-center gap-2 text-xs">
      <span class="min-w-0 flex-1 truncate text-navy">{{ tomTatGiao(tin) }}</span>
      <span
        v-if="dem"
        class="shrink-0 rounded px-1.5 py-0.5 font-mono font-bold"
        :class="dem.gap ? 'bg-red-100 text-red-700' : 'bg-orange-100 text-cam-600'"
        :title="`Hạn nhận còn ${dem.nhan}`"
      >
        ⏱ {{ dem.nhan }}
      </span>
    </span>
    <span v-if="cho" class="mt-1.5 block h-1 overflow-hidden rounded bg-slate-100" aria-hidden="true">
      <span class="block h-full bg-cam" :style="{ width: `${Math.round(tiLeDaQua(cho, now) * 100)}%` }" />
    </span>
  </NuxtLink>
</template>
