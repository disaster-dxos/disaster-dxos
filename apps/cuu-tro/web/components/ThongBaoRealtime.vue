<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Nút thông báo realtime trên thanh đầu (#68): chấm trạng thái kết nối, số tin chưa đọc; bấm mở ngăn
// bên phải (USlideover: đóng bằng Esc hoặc bấm ra ngoài, trả focus về nút). Thông báo mới được đọc lên
// cho trình đọc màn hình (aria-live).
import { thoiGianTruoc } from '~/utils/tin'
import type { MucDo } from '~/utils/thong-bao'

const { ds, chuaDoc, trangThai, daDoc } = useThongBao()
const mo = ref(false)
const now = useNow()

const NHAN_KET_NOI = {
  'tat': { nhan: 'Chưa kết nối', mau: 'neutral' },
  'dang-ket-noi': { nhan: 'Đang kết nối', mau: 'warning' },
  'da-ket-noi': { nhan: 'Đang nhận thông báo', mau: 'success' },
  'mat-ket-noi': { nhan: 'Mất kết nối, đang thử lại', mau: 'warning' },
  'bi-tu-choi': { nhan: 'Không có quyền nhận thông báo', mau: 'error' },
} as const
const MUC: Record<MucDo, { icon: string; lop: string }> = {
  'khan': { icon: 'i-lucide-siren', lop: 'bg-error/10 text-error' },
  'canh-bao': { icon: 'i-lucide-triangle-alert', lop: 'bg-warning/10 text-warning' },
  'thong-tin': { icon: 'i-lucide-info', lop: 'bg-info/10 text-info' },
}
const ketNoi = computed(() => NHAN_KET_NOI[trangThai.value])
const moiNhat = computed(() => ds.value[0])

watch(mo, (v) => { if (v) daDoc() })
</script>

<template>
  <USlideover v-model:open="mo" title="Thông báo" :description="ketNoi.nhan" :ui="{ content: 'max-w-md', body: 'p-0 sm:p-0' }">
    <UTooltip :text="ketNoi.nhan">
      <UButton color="neutral" variant="outline" class="min-h-10 gap-2" :aria-label="`Thông báo, ${chuaDoc} chưa đọc, ${ketNoi.nhan}`">
        <UChip :color="ketNoi.mau" size="md" position="bottom-right" inset>
          <UIcon name="i-lucide-bell" class="size-5" />
        </UChip>
        <span class="max-sm:hidden">Thông báo</span>
        <UBadge v-if="chuaDoc > 0" color="error" size="sm" class="so rounded-full">{{ chuaDoc > 9 ? '9+' : chuaDoc }}</UBadge>
      </UButton>
    </UTooltip>

    <template #body>
      <UEmpty v-if="ds.length === 0" icon="i-lucide-bell-off" title="Chưa có thông báo nào" description="Tin mới, tin cần xử lý và cảnh báo mực nước sẽ hiện ở đây." class="py-12" />
      <ol v-else class="divide-y divide-default">
        <li v-for="tb in ds" :key="tb.id" class="flex gap-3 px-4 py-3 sm:px-6">
          <span class="grid size-9 shrink-0 place-items-center rounded-full" :class="MUC[tb.mucDo].lop">
            <UIcon :name="MUC[tb.mucDo].icon" class="size-5" />
          </span>
          <div class="min-w-0">
            <p class="font-semibold text-highlighted">{{ tb.tieuDe }}</p>
            <p class="text-sm text-default">{{ tb.noiDung }}</p>
            <p class="mt-0.5 text-xs text-muted"><time :datetime="tb.luc">{{ thoiGianTruoc(tb.luc, now) }}</time></p>
          </div>
        </li>
      </ol>
    </template>
  </USlideover>
  <p class="sr-only" aria-live="polite">{{ moiNhat ? `${moiNhat.tieuDe}. ${moiNhat.noiDung}` : '' }}</p>
</template>
