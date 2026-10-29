<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Quỹ cứu trợ và sổ cái gần đây trên trang Minh bạch công khai (#63): tổng thu, chi, số dư (GET /minh-bach/quy)
// và các phiếu/bút toán vừa niêm phong (GET /minh-bach/so-cai). Bấm một mục → tra và tự kiểm mã đó.
import { dinhDangSo, moTaMuc, mucSoCaiTuPhanHoi, quyTuPhanHoi, urlQuy, urlSoCai, type MucSoCai, type TongQuy } from '~/utils/minh-bach'

defineProps<{ chon?: string }>()
const gw = useRuntimeConfig().public.gatewayUrl as string
const quy = ref<TongQuy | null>(null)
const ds = ref<MucSoCai[] | null>(null)
const loi = ref(false)

onMounted(async () => {
  try {
    const [rq, rs] = await Promise.all([fetch(urlQuy(gw), { cache: 'no-store' }), fetch(urlSoCai(gw), { cache: 'no-store' })])
    quy.value = rq.ok ? quyTuPhanHoi(await rq.json()) : null
    ds.value = rs.ok ? mucSoCaiTuPhanHoi(await rs.json()) : []
    loi.value = !rq.ok && !rs.ok
  } catch {
    loi.value = true
    ds.value = []
  }
})
const gio = (iso: string) => new Date(iso).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' })
</script>

<template>
  <div class="space-y-4">
    <UCard v-if="quy" :ui="{ body: 'p-4 sm:p-5' }" data-testid="quy">
      <h2 class="text-sm font-semibold text-muted">Quỹ tiền cứu trợ (đã niêm phong và chờ niêm phong)</h2>
      <dl class="mt-2 grid grid-cols-3 gap-2">
        <div><dt class="text-xs text-muted">Tổng thu</dt><dd class="so font-bold text-highlighted">{{ dinhDangSo(quy.tong_thu) }} đ</dd></div>
        <div><dt class="text-xs text-muted">Tổng chi</dt><dd class="so font-bold text-highlighted">{{ dinhDangSo(quy.tong_chi) }} đ</dd></div>
        <div><dt class="text-xs text-muted">Số dư</dt><dd class="so font-bold text-highlighted">{{ dinhDangSo(quy.so_du) }} đ</dd></div>
      </dl>
    </UCard>

    <UCard :ui="{ body: 'p-0 sm:p-0', header: 'px-4 py-3 sm:px-5' }">
      <template #header>
        <h2 class="text-sm font-semibold text-highlighted">Sổ cái gần đây</h2>
      </template>
      <p v-if="loi" class="px-5 py-4 text-sm text-muted">Không tải được sổ cái. Vẫn tra được bằng mã.</p>
      <p v-else-if="ds === null" class="px-5 py-4 text-sm text-muted">Đang tải…</p>
      <p v-else-if="ds.length === 0" class="px-5 py-4 text-sm text-muted">Chưa có mục nào được niêm phong.</p>
      <ul v-else class="divide-y divide-default" aria-label="Phiếu và bút toán vừa niêm phong">
        <li v-for="m in ds" :key="m.ma">
          <NuxtLink
            :to="`/minh-bach/${m.ma}`"
            class="flex items-start gap-3 px-4 py-2.5 hover:bg-elevated/60 focus-visible:bg-elevated sm:px-5"
            :class="{ 'bg-elevated/60': chon === m.ma }" :aria-current="chon === m.ma ? 'true' : undefined"
          >
            <UIcon :name="m.loai === 'khoan_tien' ? 'i-lucide-banknote' : 'i-lucide-package'" class="mt-0.5 size-4 shrink-0 text-muted" />
            <span class="min-w-0 flex-1">
              <span class="block truncate text-sm text-highlighted">{{ moTaMuc(m) }}</span>
              <span class="block text-xs text-muted"><span class="so">{{ gio(m.thoi_diem) }}</span> · lá số <span class="so">{{ m.ledger_index }}</span></span>
            </span>
          </NuxtLink>
        </li>
      </ul>
    </UCard>
  </div>
</template>
