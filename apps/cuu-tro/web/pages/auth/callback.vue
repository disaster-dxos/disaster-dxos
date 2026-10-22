<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
const { xuLyCallback, dangNhap } = useAuth()
const loi = ref<string | null>(null)

onMounted(async () => {
  try {
    const ve = await xuLyCallback(window.location.search)
    await navigateTo(ve, { replace: true })
  } catch (e) {
    loi.value = e instanceof Error ? e.message : String(e)
  }
})
</script>

<template>
  <main class="flex min-h-full flex-col items-center justify-center gap-6 bg-white p-6 text-center">
    <img src="/logo/logo-ngang.png" alt="Disaster DX-OS – Ứng phó Thiên tai & Cứu trợ Cộng đồng" class="w-80 max-w-full">
    <p v-if="!loi" class="text-lg" role="status">Đang hoàn tất đăng nhập…</p>
    <div v-else class="max-w-md space-y-4" role="alert">
      <p class="text-lg font-bold text-red-700">Không đăng nhập được</p>
      <p>{{ loi }}</p>
      <button type="button" class="rounded-lg bg-cam px-5 py-2.5 font-bold text-white hover:bg-cam-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-navy" @click="dangNhap('/')">
        Đăng nhập lại
      </button>
    </div>
  </main>
</template>
