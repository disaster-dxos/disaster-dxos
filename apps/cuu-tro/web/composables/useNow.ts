// SPDX-License-Identifier: Apache-2.0
// Đồng hồ cập nhật mỗi 30 giây cho nhãn "x phút trước".
export function useNow(intervalMs = 30_000) {
  const now = ref(Date.now())
  let h: ReturnType<typeof setInterval> | undefined
  onMounted(() => { h = setInterval(() => { now.value = Date.now() }, intervalMs) })
  onBeforeUnmount(() => clearInterval(h))
  return now
}
