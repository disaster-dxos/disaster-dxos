// SPDX-License-Identifier: Apache-2.0
// Giao diện đang ở chế độ tối (Nuxt UI / @nuxtjs/color-mode): cho màu vẽ trực tiếp (bản đồ, chấm trạng thái).
export function useToi() {
  const colorMode = useColorMode()
  return computed(() => colorMode.value === 'dark')
}
