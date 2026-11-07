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
    <main class="flex min-h-full flex-col items-center justify-center gap-6 bg-navy-950 p-6 text-center text-white">
      <div class="rounded-lg bg-white p-2.5 shadow-md ring-1 ring-white/20">
        <img src="/logo/logo-ngang.png" alt="Disaster DX-OS – Ứng phó Thiên tai & Cứu trợ Cộng đồng" class="w-72 max-w-full">
      </div>
      <div class="max-w-md space-y-2.5">
        <h1 class="text-2xl font-bold text-white">
          <span class="so me-2 rounded bg-navy-800 px-2 py-0.5 font-mono text-lg text-cam-400 ring-1 ring-inset ring-navy-700">{{ error.statusCode }}</span>
          {{ khongThay ? 'Không tìm thấy trang này' : 'Có lỗi khi mở trang' }}
        </h1>
        <p class="text-sm text-navy-200">{{ khongThay ? 'Đường dẫn có thể đã sai hoặc trang đã chuyển chỗ.' : 'Thử tải lại trang. Nếu vẫn lỗi, báo cho người quản trị.' }}</p>
      </div>
      <div class="flex flex-wrap justify-center gap-3">
        <UButton size="lg" color="secondary" label="Về Bản đồ điều phối" icon="i-lucide-map" class="font-bold" @click="clearError({ redirect: '/' })" />
        <UButton size="lg" color="neutral" variant="outline" label="Tra phiếu cứu trợ" icon="i-lucide-shield-check" to="/minh-bach" class="text-white ring-navy-700 hover:bg-navy-800" />
      </div>
    </main>
  </UApp>
</template>
