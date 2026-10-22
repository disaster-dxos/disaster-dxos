<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
import { MUC_KHAN, TRANG_THAI, cheSdt, thoiGianTruoc, type TinKeuCuu } from '~/utils/tin-gia'

defineProps<{ ds: TinKeuCuu[]; chon: string | null }>()
const emit = defineEmits<{ chon: [id: string] }>()
const now = useNow()
</script>

<template>
  <ul class="divide-y divide-slate-200" aria-label="Danh sách tin kêu cứu">
    <li v-for="t in ds" :key="t.id">
      <button
        type="button"
        :aria-current="t.id === chon ? 'true' : undefined"
        class="flex w-full gap-3 px-4 py-3 text-left hover:bg-slate-50 focus-visible:bg-slate-50 focus-visible:outline-none"
        :class="t.id === chon ? 'bg-sky-50 ring-2 ring-inset ring-nuoc' : ''"
        @click="emit('chon', t.id)"
      >
        <span class="mt-1.5 h-3 w-3 shrink-0 rounded-full" :style="{ background: MUC_KHAN[t.urgency].mau }" aria-hidden="true" />
        <span class="min-w-0 flex-1">
          <span class="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
            <span class="rounded px-1.5 py-0.5 font-bold text-white" :style="{ background: MUC_KHAN[t.urgency].mau }">{{ MUC_KHAN[t.urgency].nhan }}</span>
            <span class="rounded bg-slate-200 px-1.5 py-0.5 font-bold text-slate-700">{{ TRANG_THAI[t.status] }}</span>
            <span class="text-slate-500">{{ thoiGianTruoc(t.created_at, now) }}</span>
          </span>
          <span class="mt-1 block text-sm font-bold text-navy">{{ t.description }}</span>
          <span class="mt-0.5 block text-xs text-slate-600">
            {{ t.dia_chi }} · {{ t.people_count }} người · {{ cheSdt(t.reporter_phone) }}
          </span>
        </span>
      </button>
    </li>
  </ul>
</template>
