<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Danh sách tin kêu cứu bên cạnh bản đồ (#60): cùng bộ lọc với bản đồ, tin mới nổi lên đầu và có nhãn
// "Mới". Chỉ có trường của subscription (mã, mức khẩn, trạng thái, thời gian, tọa độ): mô tả, SĐT nằm ở
// ô chi tiết khi bấm. Chọn dòng ↔ chọn điểm trên bản đồ.
import { MUC_KHAN, TRANG_THAI, maNgan, thoiGianTruoc, type TinKeuCuu } from '~/utils/tin'

const props = defineProps<{ ds: TinKeuCuu[]; moi: Map<string, number>; chon: string | null }>()
const emit = defineEmits<{ chon: [id: string] }>()
const now = useNow()
const nut = ref<Record<string, HTMLElement | null>>({})

// Chọn từ bản đồ → cuộn dòng tương ứng vào tầm nhìn
watch(() => props.chon, (id: string | null) => {
  if (id) nextTick(() => nut.value[id]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }))
})
</script>

<template>
  <ul class="divide-y divide-slate-200" aria-label="Danh sách tin kêu cứu">
    <li v-for="t in ds" :key="t.id" :class="moi.has(t.id) ? 'tin-moi-dong' : ''">
      <button
        :ref="(e) => { nut[t.id] = e as HTMLElement | null }"
        type="button"
        :aria-current="t.id === chon ? 'true' : undefined"
        class="flex w-full gap-3 px-4 py-2.5 text-left hover:bg-slate-50 focus-visible:bg-slate-50 focus-visible:outline-none"
        :class="t.id === chon ? 'bg-sky-50 ring-2 ring-inset ring-nuoc' : ''"
        @click="emit('chon', t.id)"
      >
        <span class="mt-1 h-3.5 w-3.5 shrink-0 rounded-full border-2" :style="{ background: MUC_KHAN[t.urgency].mau, borderColor: t.status === 'tiep_nhan' ? '#CBD5E1' : undefined }" aria-hidden="true" />
        <span class="min-w-0 flex-1">
          <span class="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
            <span v-if="moi.has(t.id)" class="rounded bg-cam px-1.5 py-0.5 font-bold text-white">Mới</span>
            <span class="rounded px-1.5 py-0.5 font-bold text-white" :style="{ background: MUC_KHAN[t.urgency].mau }">{{ MUC_KHAN[t.urgency].nhan }}</span>
            <span class="rounded bg-slate-200 px-1.5 py-0.5 font-bold text-slate-700">{{ TRANG_THAI[t.status] }}</span>
            <time class="text-slate-500" :datetime="t.created_at">{{ thoiGianTruoc(t.created_at, now) }}</time>
          </span>
          <span class="mt-1 block text-sm font-bold text-navy">Tin <span class="font-mono">{{ maNgan(t.id) }}</span></span>
          <span class="block text-xs text-slate-600">{{ t.location[1].toFixed(4) }}, {{ t.location[0].toFixed(4) }}</span>
        </span>
      </button>
    </li>
  </ul>
</template>

<style scoped>
/* Dòng tin mới: nền cam nhạt rồi nhạt dần (tắt khi người dùng giảm chuyển động) */
.tin-moi-dong { background: #FFF4EA; }
@media (prefers-reduced-motion: no-preference) {
  .tin-moi-dong { animation: noi-len 2s ease-out 2; }
}
@keyframes noi-len {
  from { background: #FCD9B8; }
  to { background: #FFF4EA; }
}
</style>
