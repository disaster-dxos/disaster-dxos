<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Nút thông báo realtime trên thanh đầu trang (#68): chấm trạng thái kết nối, số tin chưa đọc, bảng
// tin gần nhất. Thông báo mới được đọc lên cho trình đọc màn hình (aria-live).
import { thoiGianTruoc } from '~/utils/tin'
import type { MucDo } from '~/utils/thong-bao'

const { ds, chuaDoc, trangThai, daDoc } = useThongBao()
const mo = ref(false)
const now = useNow()

const NHAN_KET_NOI = {
  'tat': { nhan: 'Chưa kết nối', mau: 'bg-slate-400' },
  'dang-ket-noi': { nhan: 'Đang kết nối', mau: 'bg-amber-400' },
  'da-ket-noi': { nhan: 'Đang nhận thông báo', mau: 'bg-emerald-500' },
  'mat-ket-noi': { nhan: 'Mất kết nối, đang thử lại', mau: 'bg-amber-500' },
  'bi-tu-choi': { nhan: 'Không có quyền nhận thông báo', mau: 'bg-red-600' },
} as const
const MAU_MUC: Record<MucDo, string> = {
  'khan': 'border-l-red-600 bg-red-50',
  'canh-bao': 'border-l-cam bg-orange-50',
  'thong-tin': 'border-l-nuoc bg-sky-50',
}
const ketNoi = computed(() => NHAN_KET_NOI[trangThai.value])
const moiNhat = computed(() => ds.value[0])

function bat() {
  mo.value = !mo.value
  if (mo.value) daDoc()
}
</script>

<template>
  <div class="relative">
    <button
      type="button"
      class="relative flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-bold text-navy hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cam"
      :aria-expanded="mo"
      aria-controls="bang-thong-bao"
      :title="ketNoi.nhan"
      @click="bat"
    >
      <span class="h-2.5 w-2.5 rounded-full" :class="ketNoi.mau" aria-hidden="true" />
      <span>Thông báo</span>
      <span v-if="chuaDoc > 0" class="rounded-full bg-red-600 px-1.5 text-xs text-white">{{ chuaDoc > 9 ? '9+' : chuaDoc }}</span>
      <span class="sr-only">, {{ ketNoi.nhan }}</span>
    </button>
    <p class="sr-only" aria-live="polite">{{ moiNhat ? `${moiNhat.tieuDe}. ${moiNhat.noiDung}` : '' }}</p>
    <section
      v-if="mo"
      id="bang-thong-bao"
      class="absolute right-0 z-20 mt-2 w-[min(92vw,380px)] rounded-lg border border-slate-200 bg-white shadow-lg"
      aria-label="Thông báo realtime"
    >
      <p class="flex items-center gap-2 border-b border-slate-200 px-3 py-2 text-xs text-slate-600">
        <span class="h-2 w-2 rounded-full" :class="ketNoi.mau" aria-hidden="true" />{{ ketNoi.nhan }}
      </p>
      <p v-if="ds.length === 0" class="px-3 py-6 text-center text-sm text-slate-500">Chưa có thông báo nào.</p>
      <ol v-else class="max-h-[60vh] overflow-y-auto">
        <li v-for="tb in ds" :key="tb.id" class="border-b border-l-4 border-slate-100 px-3 py-2" :class="MAU_MUC[tb.mucDo]">
          <p class="text-sm font-bold text-navy">{{ tb.tieuDe }}</p>
          <p class="text-xs text-chu">{{ tb.noiDung }}</p>
          <p class="mt-0.5 text-[11px] text-slate-500"><time :datetime="tb.luc">{{ thoiGianTruoc(tb.luc, now) }}</time></p>
        </li>
      </ol>
    </section>
  </div>
</template>
