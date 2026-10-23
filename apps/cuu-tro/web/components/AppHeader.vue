<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
import { VAI_TRO, laDieuPhoi } from '~/utils/session'
import { vaiPhanCong } from '~/utils/phan-cong'

const { user, dangXuat } = useAuth()
const route = useRoute()
// Điều hướng (#61): bản đồ ↔ màn phân công (điều phối) / nhiệm vụ của đội (cứu hộ)
const menu = computed(() => {
  const vai = vaiPhanCong(user.value)
  const ds = [{ to: '/', nhan: 'Bản đồ' }]
  if (vai) ds.push({ to: '/phan-cong', nhan: vai === 'cuu-ho' ? 'Nhiệm vụ' : 'Phân công' })
  return ds
})
const dangO = (to: string) => (to === '/' ? route.path === '/' : route.path.startsWith(to))
const nhanThongBao = computed(() => laDieuPhoi(user.value))
const vaiTro = computed(() => (user.value?.roles ?? []).map((r: string) => VAI_TRO[r as keyof typeof VAI_TRO] ?? r).join(', '))
</script>

<template>
  <header class="flex h-16 shrink-0 items-center gap-3 border-b-4 border-cam bg-white px-4 shadow-sm">
    <img src="/logo/mark-64.png" alt="" width="40" height="40" class="h-10 w-10">
    <div class="hidden min-w-0 leading-tight md:block">
      <p class="truncate text-lg font-bold text-navy">Trung tâm điều phối cứu trợ</p>
      <p class="truncate text-xs text-slate-500">Disaster DX-OS · Ứng phó Thiên tai &amp; Cứu trợ Cộng đồng</p>
    </div>
    <nav v-if="menu.length > 1" class="flex items-center gap-1 md:ml-4" aria-label="Màn hình">
      <NuxtLink
        v-for="m in menu" :key="m.to" :to="m.to"
        class="rounded-lg px-3 py-2 text-sm font-bold"
        :class="dangO(m.to) ? 'bg-navy text-white' : 'text-navy hover:bg-slate-100'"
        :aria-current="dangO(m.to) ? 'page' : undefined"
      >
        {{ m.nhan }}
      </NuxtLink>
    </nav>
    <div class="ml-auto flex items-center gap-2 sm:gap-3">
      <ThongBaoRealtime v-if="nhanThongBao" />
      <div v-if="user" class="hidden text-right leading-tight sm:block">
        <p class="text-sm font-bold text-navy">{{ user.displayName }}</p>
        <p class="text-xs text-slate-500">{{ vaiTro || 'Chưa có vai trò' }}</p>
      </div>
      <button
        type="button"
        class="whitespace-nowrap rounded-lg border border-navy px-3 py-1.5 text-sm font-bold text-navy hover:bg-navy hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cam"
        @click="dangXuat"
      >
        Đăng xuất
      </button>
    </div>
  </header>
</template>
