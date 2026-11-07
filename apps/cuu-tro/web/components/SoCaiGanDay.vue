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
const tiLeChi = computed(() => {
  const thu = Number(quy.value?.tong_thu ?? 0)
  const chi = Number(quy.value?.tong_chi ?? 0)
  if (!Number.isFinite(thu) || thu <= 0) return 0
  return Math.min(100, Math.round((chi / thu) * 100))
})

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
    <UCard v-if="quy" :ui="{ header: 'px-4 py-3 sm:px-5 bg-muted/60', body: 'p-4 sm:p-5' }" data-testid="quy">
      <template #header>
        <div class="flex items-center justify-between gap-2">
          <h2 class="flex items-center gap-2 text-sm font-bold text-highlighted">
            <UIcon name="i-lucide-landmark" class="size-4 text-info" />Quỹ tiền cứu trợ công khai
          </h2>
          <span class="so rounded bg-elevated px-2 py-0.5 text-xs font-semibold text-muted ring-1 ring-inset ring-default">Giải ngân {{ tiLeChi }}%</span>
        </div>
      </template>
      <dl class="grid grid-cols-1 gap-3 sm:grid-cols-3 sm:divide-x sm:divide-default">
        <div class="sm:pe-2">
          <dt class="text-xs font-medium text-muted">Tổng thu</dt>
          <dd class="so mt-0.5 text-base font-bold text-highlighted">{{ dinhDangSo(quy.tong_thu) }} đ</dd>
        </div>
        <div class="sm:px-3">
          <dt class="text-xs font-medium text-muted">Tổng chi</dt>
          <dd class="so mt-0.5 text-base font-bold text-cam-700 dark:text-cam-300">{{ dinhDangSo(quy.tong_chi) }} đ</dd>
        </div>
        <div class="sm:ps-3">
          <dt class="text-xs font-medium text-ok-700 dark:text-ok-300">Số dư hiện còn</dt>
          <dd class="so mt-0.5 text-base font-bold text-ok-700 dark:text-ok-300">{{ dinhDangSo(quy.so_du) }} đ</dd>
        </div>
      </dl>
      <div class="mt-3 h-2 overflow-hidden rounded-full bg-muted ring-1 ring-inset ring-default" aria-hidden="true">
        <div class="h-full rounded-full bg-nuoc-400" :style="{ width: `${tiLeChi}%` }" />
      </div>
    </UCard>

    <UCard :ui="{ body: 'p-0 sm:p-0', header: 'px-4 py-3 sm:px-5 bg-muted/60' }">
      <template #header>
        <div class="flex items-center justify-between gap-2">
          <h2 class="flex items-center gap-2 text-sm font-bold text-highlighted">
            <UIcon name="i-lucide-scroll-text" class="size-4 text-info" />Sổ cái gần đây
          </h2>
          <span v-if="ds" class="so font-mono text-xs text-muted">{{ ds.length }} bản ghi</span>
        </div>
      </template>
      <p v-if="loi" class="px-5 py-4 text-sm text-muted">Không tải được sổ cái. Vẫn tra được bằng mã.</p>
      <p v-else-if="ds === null" class="px-5 py-4 text-sm text-muted">Đang tải…</p>
      <p v-else-if="ds.length === 0" class="px-5 py-4 text-sm text-muted">Chưa có mục nào được niêm phong.</p>
      <ul v-else class="divide-y divide-default" aria-label="Phiếu và bút toán vừa niêm phong">
        <li v-for="m in ds" :key="m.ma">
          <NuxtLink
            :to="`/minh-bach/${m.ma}`"
            class="flex items-start gap-3 px-4 py-3 transition-colors hover:bg-muted/70 focus-visible:bg-muted sm:px-5"
            :class="chon === m.ma ? 'bg-info/10 shadow-[inset_0_0_0_2px_var(--ui-info)]' : ''" :aria-current="chon === m.ma ? 'true' : undefined"
          >
            <span class="mt-0.5 grid size-7 shrink-0 place-items-center rounded-md bg-muted text-default ring-1 ring-inset ring-default">
              <UIcon :name="m.loai === 'khoan_tien' ? 'i-lucide-banknote' : 'i-lucide-package'" class="size-4" />
            </span>
            <span class="min-w-0 flex-1">
              <span class="block truncate text-sm font-semibold text-highlighted">{{ moTaMuc(m) }}</span>
              <span class="mt-0.5 flex items-center gap-2 text-xs text-muted">
                <span class="so">{{ gio(m.thoi_diem) }}</span>
                <span>·</span>
                <span class="so rounded bg-muted px-1.5 py-0.2 font-mono text-xs font-medium text-default ring-1 ring-inset ring-default">lá số {{ m.ledger_index }}</span>
              </span>
            </span>
          </NuxtLink>
        </li>
      </ul>
    </UCard>
  </div>
</template>
