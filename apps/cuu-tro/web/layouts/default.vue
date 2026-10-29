<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Khung web điều phối (theo template nuxt-ui-templates/dashboard): thanh bên thu gọn được, trên điện
// thoại thành ngăn kéo. Mục điều hướng theo vai (#61): bản đồ ↔ phân công (điều phối) / nhiệm vụ (cứu hộ);
// điều phối có thêm hàng chờ duyệt tin AI (#104).
import type { NavigationMenuItem } from '@nuxt/ui'
import { vaiPhanCong } from '~/utils/phan-cong'

const { user } = useAuth()
const mo = ref(false)
const dong = () => { mo.value = false }

const menu = computed<NavigationMenuItem[]>(() => {
  const vai = vaiPhanCong(user.value)
  const ds: NavigationMenuItem[] = [{ label: 'Bản đồ điều phối', icon: 'i-lucide-map', to: '/', exact: true, onSelect: dong }]
  if (vai) {
    ds.push({
      label: vai === 'cuu-ho' ? 'Nhiệm vụ của đội' : 'Phân công cứu hộ',
      icon: vai === 'cuu-ho' ? 'i-lucide-life-buoy' : 'i-lucide-square-kanban',
      to: '/phan-cong',
      onSelect: dong,
    })
  }
  // Hàng chờ duyệt tin do AI bóc tách (#104): chỉ điều phối (Hasura chỉ cho vai này đọc văn bản gốc)
  if (vai === 'dieu-phoi') {
    ds.push({ label: 'Duyệt tin AI', icon: 'i-lucide-sparkles', to: '/hang-cho', onSelect: dong })
  }
  return ds
})
const phu: NavigationMenuItem[] = [
  { label: 'Minh bạch cứu trợ', icon: 'i-lucide-shield-check', to: '/minh-bach', target: '_blank' },
]
</script>

<template>
  <UDashboardGroup unit="rem" storage="local" storage-key="dxos-khung">
    <UDashboardSidebar
      id="dieu-phoi"
      v-model:open="mo"
      collapsible
      :default-size="15"
      :min-size="13"
      :max-size="20"
      class="bg-elevated/40"
      :ui="{ footer: 'border-t border-default py-3' }"
    >
      <template #header="{ collapsed }">
        <NuxtLink to="/" class="flex min-w-0 items-center gap-2.5" aria-label="Trang chính Disaster DX-OS">
          <span class="grid size-9 shrink-0 place-items-center rounded-md bg-white ring ring-default">
            <img src="/logo/mark-64.png" alt="" width="28" height="28" class="size-7">
          </span>
          <span v-if="!collapsed" class="min-w-0 leading-tight">
            <span class="block truncate text-sm font-bold text-highlighted">Disaster DX-OS</span>
            <span class="block truncate text-xs text-muted">Điều phối cứu trợ</span>
          </span>
        </NuxtLink>
      </template>

      <template #default="{ collapsed }">
        <UNavigationMenu :collapsed="collapsed" :items="menu" orientation="vertical" tooltip :ui="{ link: 'min-h-10 text-sm' }" />
        <UNavigationMenu :collapsed="collapsed" :items="phu" orientation="vertical" tooltip class="mt-auto" :ui="{ link: 'min-h-10 text-sm' }" />
      </template>

      <template #footer="{ collapsed }">
        <MenuNguoiDung :collapsed="collapsed" />
      </template>
    </UDashboardSidebar>

    <slot />
  </UDashboardGroup>
</template>
