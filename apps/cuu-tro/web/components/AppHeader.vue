<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
import { VAI_TRO } from '~/utils/session'

const { user, dangXuat } = useAuth()
const vaiTro = computed(() => (user.value?.roles ?? []).map((r: string) => VAI_TRO[r as keyof typeof VAI_TRO] ?? r).join(', '))
</script>

<template>
  <header class="flex h-16 shrink-0 items-center gap-3 border-b-4 border-cam bg-white px-4 shadow-sm">
    <img src="/logo/mark-64.png" alt="" width="40" height="40" class="h-10 w-10">
    <div class="min-w-0 leading-tight">
      <p class="truncate text-lg font-bold text-navy">Trung tâm điều phối cứu trợ</p>
      <p class="truncate text-xs text-slate-500">Disaster DX-OS · Ứng phó Thiên tai &amp; Cứu trợ Cộng đồng</p>
    </div>
    <div class="ml-auto flex items-center gap-3">
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
