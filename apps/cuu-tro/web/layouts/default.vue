<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Khung web điều phối: cột chỉ huy nền Navy đậm (#0B1F36) tạo điểm tựa thị giác rõ ràng cho toàn bộ bàn điều hành;
// thu gọn được, trên điện thoại thành ngăn kéo. Mục điều hướng theo vai (#61): bản đồ ↔ phân công (điều phối) /
// nhiệm vụ (cứu hộ); điều phối có thêm hàng chờ duyệt tin AI (#104).
import type { NavigationMenuItem } from '@nuxt/ui'
import { vaiPhanCong } from '~/utils/phan-cong'
import { VAI_TRO } from '~/utils/session'

const { user } = useAuth()
const mo = ref(false)
const dong = () => { mo.value = false }
const vai = computed(() => vaiPhanCong(user.value))
const nhanVai = computed(() => {
  if (vai.value === 'dieu-phoi') return 'Trung tâm Điều phối'
  if (vai.value === 'cuu-ho') return 'Đội Cứu hộ hiện trường'
  const r = user.value?.roles?.[0]
  return (r && VAI_TRO[r as keyof typeof VAI_TRO]) || 'Chế độ quan sát'
})

const menu = computed<NavigationMenuItem[]>(() => {
  const v = vai.value
  const ds: NavigationMenuItem[] = [{ label: 'Bản đồ điều phối', icon: 'i-lucide-map', to: '/', exact: true, onSelect: dong }]
  if (v) {
    ds.push({
      label: v === 'cuu-ho' ? 'Nhiệm vụ của đội' : 'Phân công cứu hộ',
      icon: v === 'cuu-ho' ? 'i-lucide-life-buoy' : 'i-lucide-square-kanban',
      to: '/phan-cong',
      onSelect: dong,
    })
  }
  // Hàng chờ duyệt tin do AI bóc tách (#104): chỉ điều phối (Hasura chỉ cho vai này đọc văn bản gốc)
  if (v === 'dieu-phoi') {
    ds.push({ label: 'Duyệt tin AI', icon: 'i-lucide-sparkles', to: '/hang-cho', onSelect: dong })
  }
  return ds
})
const phu: NavigationMenuItem[] = [
  { label: 'Minh bạch cứu trợ', icon: 'i-lucide-shield-check', to: '/minh-bach', target: '_blank' },
]

const uiMenu = {
  link: 'min-h-10.5 rounded-md px-3 py-2 text-sm font-medium text-muted hover:bg-muted hover:text-highlighted data-[active]:bg-cam-500 data-[active]:text-navy-950 data-[active]:font-bold data-[active]:shadow-xs',
  linkLeadingIcon: 'size-5 text-muted group-hover:text-highlighted group-data-[active]:text-navy-950',
  linkTrailingIcon: 'text-muted group-data-[active]:text-navy-950',
}
</script>

<template>
  <UDashboardGroup unit="rem" storage="local" storage-key="dxos-khung">
    <UDashboardSidebar
      id="dieu-phoi"
      v-model:open="mo"
      collapsible
      :default-size="15.5"
      :min-size="13.5"
      :max-size="20"
      class="border-r border-default bg-elevated text-default"
      :ui="{
        header: 'h-14 border-b border-default px-3.5',
        body: 'gap-3 px-2.5 py-3',
        footer: 'border-t border-default px-2.5 py-2.5',
      }"
    >
      <template #header="{ collapsed }">
        <NuxtLink to="/" class="flex min-w-0 items-center gap-2.5" aria-label="Trang chính Disaster DX-OS">
          <span class="grid size-9 shrink-0 place-items-center rounded-md bg-navy-950 shadow-xs ring-1 ring-navy-800">
            <img src="/logo/mark-64.png" alt="" width="28" height="28" class="size-7">
          </span>
          <span v-if="!collapsed" class="min-w-0 leading-tight">
            <span class="block truncate text-sm font-bold tracking-tight text-highlighted">DISASTER DX-OS</span>
            <span class="flex items-center gap-1.5 truncate text-xs text-muted">
              <span class="size-1.5 shrink-0 rounded-full bg-nuoc-500" aria-hidden="true" />
              {{ nhanVai }}
            </span>
          </span>
        </NuxtLink>
      </template>

      <template #default="{ collapsed }">
        <UNavigationMenu :collapsed="collapsed" :items="menu" orientation="vertical" tooltip :ui="uiMenu" />

        <div class="mt-auto space-y-2 border-t border-default pt-3">
          <UNavigationMenu :collapsed="collapsed" :items="phu" orientation="vertical" tooltip :ui="uiMenu" />
          <div v-if="!collapsed" class="rounded-md bg-muted/60 px-3 py-2 text-xs text-muted ring-1 ring-inset ring-default">
            <p class="flex items-center justify-between font-semibold text-highlighted">
              <span>Sổ cái chỉ-thêm</span>
              <span class="so font-mono font-bold text-nuoc-600 dark:text-nuoc-400">Ed25519</span>
            </p>
            <p class="mt-0.5 text-xs text-muted">Kiểm chứng công khai từng phiếu kho &amp; bút toán</p>
          </div>
        </div>
      </template>

      <template #footer="{ collapsed }">
        <MenuNguoiDung :collapsed="collapsed" />
      </template>
    </UDashboardSidebar>

    <slot />
  </UDashboardGroup>
</template>
