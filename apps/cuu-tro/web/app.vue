<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
import { vi } from '@nuxt/ui/locale'
</script>

<template>
  <!-- UApp: nơi đặt tooltip, toast, slideover của Nuxt UI; nhãn mặc định (Đóng, Mở thanh bên…) tiếng Việt -->
  <UApp :locale="vi" :tooltip="{ delayDuration: 300 }">
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </UApp>
</template>
