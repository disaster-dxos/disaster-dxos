<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
definePageMeta({ layout: false })
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
  <main class="flex min-h-full flex-col items-center justify-center gap-6 p-6 text-center">
    <img src="/logo/logo-ngang.png" alt="Disaster DX-OS – Ứng phó Thiên tai & Cứu trợ Cộng đồng" class="w-80 max-w-full rounded-lg bg-white p-2">
    <p v-if="!loi" class="flex items-center gap-2 text-lg" role="status">
      <UIcon name="i-lucide-loader-circle" class="size-5 motion-safe:animate-spin" />Đang hoàn tất đăng nhập…
    </p>
    <UAlert
      v-else role="alert" class="max-w-md text-left" color="error" variant="subtle" icon="i-lucide-circle-alert"
      title="Không đăng nhập được" :description="loi"
      :actions="[{ label: 'Đăng nhập lại', color: 'secondary', size: 'lg', onClick: () => dangNhap('/') }]"
    />
  </main>
</template>
