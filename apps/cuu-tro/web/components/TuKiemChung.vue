<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Trình duyệt tự kiểm chứng một mã trên sổ cái (#63): 5 bước của utils/tu-kiem.ts, độc lập với kết luận
// của máy chủ; kèm toàn bộ bằng chứng (lá, leaf hash, inclusion proof, checkpoint đã ký, khóa công khai)
// và lệnh ledger-verify để người ngoài kiểm lại bằng công cụ riêng.
import type { KetQuaXacMinh } from '~/utils/minh-bach'
import { jsonChuanTac, ketLuan, tuKiem, type BuocKiem } from '~/utils/tu-kiem'

const props = defineProps<{ kq: KetQuaXacMinh; vkey: string | null }>()
const buoc = ref<BuocKiem[] | null>(null)
const dangKiem = ref(false)
let lan = 0

async function kiem() {
  const ma = ++lan
  dangKiem.value = true
  buoc.value = null
  try {
    const b = await tuKiem({ loai: props.kq.loai, ma: props.kq.ma, ban_ghi_chuan_hoa: props.kq.ban_ghi_chuan_hoa, bang_chung: props.kq.bang_chung, la: props.kq.so_cai.la }, props.vkey)
    if (ma === lan) buoc.value = b
  } finally {
    if (ma === lan) dangKiem.value = false
  }
}
watch(() => [props.kq, props.vkey], kiem, { immediate: true })

const KET_LUAN = {
  hop_le: { nhan: 'Trình duyệt xác nhận: hợp lệ', mau: 'success', icon: 'i-lucide-badge-check' },
  khong_hop_le: { nhan: 'Trình duyệt phát hiện sai lệch', mau: 'error', icon: 'i-lucide-badge-x' },
  chua_du: { nhan: 'Chưa đủ dữ liệu để kết luận', mau: 'neutral', icon: 'i-lucide-badge-help' },
} as const
const kl = computed(() => (buoc.value ? KET_LUAN[ketLuan(buoc.value)] : null))
const iconBuoc = (ok: boolean | null) => (ok === true ? 'i-lucide-circle-check' : ok === false ? 'i-lucide-circle-x' : 'i-lucide-circle-minus')
const mauBuoc = (ok: boolean | null) => (ok === true ? 'text-success' : ok === false ? 'text-error' : 'text-muted')
const chuanTac = computed(() => {
  try { return jsonChuanTac(props.kq.ban_ghi_chuan_hoa) } catch { return '' }
})
const laDep = computed(() => {
  try { return props.kq.so_cai.la ? JSON.stringify(JSON.parse(props.kq.so_cai.la), null, 2) : '' } catch { return props.kq.so_cai.la ?? '' }
})
</script>

<template>
  <UCard :ui="{ body: 'p-0 sm:p-0' }" data-testid="tu-kiem">
    <div class="space-y-3.5 p-5">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h2 class="flex items-center gap-2 text-base font-bold text-highlighted">
          <UIcon name="i-lucide-cpu" class="size-5 text-info" />Trình duyệt của bạn tự kiểm (WebCrypto)
        </h2>
        <UBadge v-if="kl" :color="kl.mau" variant="subtle" size="lg" :icon="kl.icon" class="font-bold ring-1 ring-inset ring-current/30" data-testid="ket-luan-tu-kiem">{{ kl.nhan }}</UBadge>
        <UBadge v-else-if="dangKiem" color="neutral" variant="subtle" size="lg" icon="i-lucide-loader">Đang kiểm…</UBadge>
      </div>
      <p class="text-sm text-muted">
        Không tin lời máy chủ: trang tự băm lại bản ghi chuẩn tắc (SHA-256), dựng đường dẫn Merkle và kiểm chữ ký Ed25519 ngay trên máy bạn.
      </p>
      <ol v-if="buoc" class="divide-y divide-default border-t border-default pt-1" aria-label="Các bước tự kiểm chứng">
        <li
          v-for="(b, i) in buoc" :key="b.khoa"
          class="flex gap-3 py-2.5"
        >
          <UIcon :name="iconBuoc(b.ok)" class="mt-0.5 size-5 shrink-0" :class="mauBuoc(b.ok)" />
          <div class="min-w-0 flex-1">
            <p class="text-sm font-bold text-highlighted">
              {{ i + 1 }}. {{ b.ten }}
              <span class="sr-only">: {{ b.ok === true ? 'đạt' : b.ok === false ? 'không đạt' : 'không kiểm được' }}</span>
            </p>
            <p class="mt-0.5 break-all font-mono text-xs text-muted">{{ b.chiTiet }}</p>
          </div>
        </li>
      </ol>
    </div>

    <UCollapsible class="border-t border-default bg-muted/40">
      <UButton color="neutral" variant="ghost" block icon="i-lucide-terminal" trailing-icon="i-lucide-chevron-down" class="min-h-12 justify-between px-5 font-bold text-highlighted">
        Bằng chứng mật mã &amp; lệnh kiểm độc lập (dành cho người kỹ thuật)
      </UButton>
      <template #content>
        <div class="space-y-4 px-5 pb-5 text-xs">
          <dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 rounded-lg bg-elevated p-3.5 ring-1 ring-inset ring-default">
            <dt class="text-muted">SHA-256 bản ghi</dt><dd class="break-all font-mono text-highlighted">{{ kq.sha256 }}</dd>
            <template v-if="kq.bang_chung">
              <dt class="text-muted">Chỉ số lá</dt><dd class="so font-mono font-bold text-highlighted">{{ kq.bang_chung.leaf_index }}</dd>
              <dt class="text-muted">Leaf hash</dt><dd class="break-all font-mono">{{ kq.bang_chung.leaf_hash }}</dd>
              <dt class="text-muted">Kích thước cây</dt><dd class="so font-mono">{{ kq.bang_chung.tree_size }}</dd>
            </template>
            <template v-if="kq.so_cai.checkpoint">
              <dt class="text-muted">Sổ cái</dt><dd class="break-all font-mono">{{ kq.so_cai.checkpoint.origin }}</dd>
              <dt class="text-muted">Root hash</dt><dd class="break-all font-mono">{{ kq.so_cai.checkpoint.root_hash }}</dd>
            </template>
            <template v-if="vkey">
              <dt class="text-muted">Khóa công khai</dt><dd class="break-all font-mono">{{ vkey }}</dd>
            </template>
          </dl>
          <div v-if="kq.bang_chung">
            <p class="mb-1 font-semibold text-muted">Inclusion proof ({{ kq.bang_chung.inclusion_proof.length }} hash, từ lá lên gốc)</p>
            <ol class="list-decimal space-y-0.5 ps-5 font-mono">
              <li v-for="h in kq.bang_chung.inclusion_proof" :key="h" class="break-all">{{ h }}</li>
            </ol>
          </div>
          <div v-if="kq.bang_chung">
            <p class="mb-1 font-semibold text-muted">Checkpoint đã ký (nguyên văn)</p>
            <pre class="overflow-x-auto rounded-md bg-elevated p-3 font-mono leading-5 ring-1 ring-inset ring-default">{{ kq.bang_chung.checkpoint }}</pre>
          </div>
          <div v-if="laDep">
            <p class="mb-1 font-semibold text-muted">Lá trên sổ cái</p>
            <pre class="overflow-x-auto rounded-md bg-elevated p-3 font-mono leading-5 ring-1 ring-inset ring-default">{{ laDep }}</pre>
          </div>
          <div v-if="chuanTac">
            <p class="mb-1 font-semibold text-muted">Bản ghi chuẩn tắc (đầu vào của SHA-256)</p>
            <pre class="overflow-x-auto whitespace-pre-wrap break-all rounded-md bg-elevated p-3 font-mono leading-5 ring-1 ring-inset ring-default">{{ chuanTac }}</pre>
          </div>
          <div>
            <p class="mb-1 font-semibold text-muted">Kiểm lại bằng công cụ dòng lệnh</p>
            <pre class="overflow-x-auto rounded-md bg-navy-950 p-3 font-mono leading-5 text-white">{{ kq.tu_kiem_chung }}</pre>
          </div>
        </div>
      </template>
    </UCollapsible>
  </UCard>
</template>
