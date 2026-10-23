<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Người đang đăng nhập (tên, vai) + chọn giao diện sáng/tối + đăng xuất, ở chân thanh bên.
import type { DropdownMenuItem } from '@nuxt/ui'
import { VAI_TRO } from '~/utils/session'

defineProps<{ collapsed?: boolean }>()
const { user, dangXuat } = useAuth()
const colorMode = useColorMode()
const vaiTro = computed(() => (user.value?.roles ?? []).map((r: string) => VAI_TRO[r as keyof typeof VAI_TRO] ?? r).join(', '))

const GIAO_DIEN = [
  { gt: 'light', nhan: 'Sáng', icon: 'i-lucide-sun' },
  { gt: 'dark', nhan: 'Tối', icon: 'i-lucide-moon' },
  { gt: 'system', nhan: 'Theo máy', icon: 'i-lucide-monitor' },
] as const

const items = computed<DropdownMenuItem[][]>(() => [
  [{ type: 'label', label: user.value?.displayName ?? 'Chưa đăng nhập', description: vaiTro.value || 'Chưa có vai trò' }],
  [{
    label: 'Giao diện',
    icon: 'i-lucide-palette',
    children: GIAO_DIEN.map((g) => ({
      label: g.nhan,
      icon: g.icon,
      type: 'checkbox' as const,
      checked: colorMode.preference === g.gt,
      onSelect: (e: Event) => { e.preventDefault(); colorMode.preference = g.gt },
    })),
  }],
  [{ label: 'Đăng xuất', icon: 'i-lucide-log-out', onSelect: () => { void dangXuat() } }],
])
</script>

<template>
  <UDropdownMenu :items="items" :content="{ align: 'center', collisionPadding: 12 }" :ui="{ content: collapsed ? 'w-56' : 'w-(--reka-dropdown-menu-trigger-width)' }">
    <UButton
      color="neutral" variant="ghost" block :square="collapsed"
      class="min-h-11 data-[state=open]:bg-elevated"
      :aria-label="collapsed ? `Tài khoản ${user?.displayName ?? ''}` : undefined"
      :ui="{ trailingIcon: 'text-dimmed' }"
      :trailing-icon="collapsed ? undefined : 'i-lucide-chevrons-up-down'"
    >
      <UAvatar icon="i-lucide-user-round" size="sm" :ui="{ root: 'bg-primary', icon: 'text-inverted' }" />
      <span v-if="!collapsed" class="min-w-0 flex-1 text-left leading-tight">
        <span class="block truncate text-sm font-semibold text-highlighted">{{ user?.displayName }}</span>
        <span class="block truncate text-xs text-muted">{{ vaiTro || 'Chưa có vai trò' }}</span>
      </span>
    </UButton>
  </UDropdownMenu>
</template>
