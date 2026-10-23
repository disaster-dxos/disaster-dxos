<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Trang lỗi tiếng Việt (thay trang 404/500 mặc định tiếng Anh của Nuxt)
import { vi } from '@nuxt/ui/locale'
import type { NuxtError } from '#app'

const props = defineProps<{ error: NuxtError }>()
const khongThay = computed(() => props.error.statusCode === 404)
</script>

<template>
  <UApp :locale="vi">
    <main class="flex min-h-full flex-col items-center justify-center gap-6 p-6 text-center">
      <img src="/logo/logo-ngang.png" alt="Disaster DX-OS – Ứng phó Thiên tai & Cứu trợ Cộng đồng" class="w-72 max-w-full rounded-lg bg-white p-2">
      <div class="max-w-md space-y-2">
        <p class="text-sm font-semibold text-muted">Lỗi {{ error.statusCode }}</p>
        <h1 class="text-2xl font-bold text-highlighted">{{ khongThay ? 'Không tìm thấy trang này' : 'Có lỗi khi mở trang' }}</h1>
        <p class="text-muted">{{ khongThay ? 'Đường dẫn có thể đã sai hoặc trang đã chuyển chỗ.' : 'Thử tải lại trang. Nếu vẫn lỗi, báo cho người quản trị.' }}</p>
      </div>
      <div class="flex flex-wrap justify-center gap-3">
        <UButton size="lg" color="secondary" label="Về trang chính" @click="clearError({ redirect: '/' })" />
        <UButton size="lg" color="neutral" variant="outline" label="Tra phiếu cứu trợ" to="/minh-bach" />
      </div>
    </main>
  </UApp>
</template>
