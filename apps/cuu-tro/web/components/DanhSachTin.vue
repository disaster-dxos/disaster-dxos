<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Danh sách tin kêu cứu bên cạnh bản đồ (#60): cùng bộ lọc với bản đồ, tin mới nổi lên đầu và có nhãn
// "Mới". Chỉ có trường của subscription (mã, mức khẩn, trạng thái, thời gian, tọa độ): mô tả, SĐT nằm ở
// ngăn chi tiết khi bấm. Chọn dòng ↔ chọn điểm trên bản đồ.
import { MUC_KHAN, maNgan, thoiGianTruoc, type TinKeuCuu } from '~/utils/tin'

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
  <ul class="divide-y divide-default">
    <li v-for="t in ds" :key="t.id" :class="moi.has(t.id) ? 'tin-moi-dong' : ''">
      <button
        :ref="(e) => { nut[t.id] = e as HTMLElement | null }"
        type="button"
        :aria-current="t.id === chon ? 'true' : undefined"
        class="group flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/70 sm:px-5"
        :class="t.id === chon ? 'bg-info/10 shadow-[inset_0_0_0_2px_var(--ui-info)]' : ''"
        @click="emit('chon', t.id)"
      >
        <span
          class="mt-1.5 size-3.5 shrink-0 rounded-full ring-2 ring-default"
          :style="{ background: MUC_KHAN[t.urgency].mau }" aria-hidden="true"
        />
        <span class="min-w-0 flex-1">
          <span class="flex flex-wrap items-center gap-1.5">
            <UBadge v-if="moi.has(t.id)" color="secondary" size="md" class="font-semibold">Mới</UBadge>
            <NhanMucKhan :muc="t.urgency" />
            <NhanTrangThai :tt="t.status" />
            <time class="so ms-auto text-xs font-medium text-muted" :datetime="t.created_at">{{ thoiGianTruoc(t.created_at, now) }}</time>
          </span>
          <span class="mt-2 flex items-center justify-between gap-2">
            <span class="text-sm font-bold text-highlighted">
              Mã tin <span class="rounded bg-muted px-1.5 py-0.5 font-mono text-xs font-semibold text-default ring-1 ring-inset ring-default">{{ maNgan(t.id) }}</span>
            </span>
            <span class="so flex items-center gap-1 font-mono text-xs text-muted">
              <UIcon name="i-lucide-locate-fixed" class="size-3.5 shrink-0 text-dimmed group-hover:text-info" />
              {{ t.location[1].toFixed(4) }}°B, {{ t.location[0].toFixed(4) }}°Đ
            </span>
          </span>
        </span>
      </button>
    </li>
  </ul>
</template>

<style scoped>
/* Dòng tin mới: nền cam nhạt rồi nhạt dần (tắt khi người dùng giảm chuyển động) */
.tin-moi-dong { background: color-mix(in oklab, var(--color-cam-500) 9%, transparent); }
@media (prefers-reduced-motion: no-preference) {
  .tin-moi-dong { animation: noi-len 2s ease-out 2; }
}
@keyframes noi-len {
  from { background: color-mix(in oklab, var(--color-cam-500) 28%, transparent); }
  to { background: color-mix(in oklab, var(--color-cam-500) 9%, transparent); }
}
</style>
