<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Trang Đăng nhập Hệ thống Điều phối Cứu trợ (Disaster DX-OS, #59).
// Hỗ trợ đăng nhập OIDC qua Keycloak SSO với client công khai dxos-web (PKCE).
// Liệt kê 3 tài khoản mẫu của realm disaster (điều phối, cứu hộ, tình nguyện); không hiện mật khẩu.
definePageMeta({ layout: false })

const { dangNhap, user } = useAuth()
const route = useRoute()
const ve = typeof route.query.returnTo === 'string' ? route.query.returnTo : '/'

onMounted(async () => {
  // Nếu đã có phiên hợp lệ thì điều hướng thẳng tới trang đích
  if (user.value) {
    await navigateTo(ve, { replace: true })
  }
})

const TAI_KHOAN = [
  {
    vai: 'Điều phối (dieu-phoi)',
    user: 'dieuphoi01',
    moTa: 'Web điều phối: bản đồ tin kêu cứu và trạm đo, phân công đội, duyệt tin AI bóc tách, xem đủ thông tin liên lạc. Bắt buộc mã OTP khi đăng nhập.',
    badge: 'MFA bắt buộc',
    badgeClass: 'bg-amber-100 text-amber-900 dark:bg-amber-500/20 dark:text-amber-300 ring-1 ring-amber-300/70 dark:ring-amber-500/40',
  },
  {
    vai: 'Cứu hộ (cuu-ho)',
    user: 'cuuho01',
    moTa: 'Web và app hiện trường: chỉ thấy nhiệm vụ giao cho đội mình; nhận, từ chối hoặc xác nhận đã cứu trước khi hết hạn nhận.',
    badge: 'Web + app',
    badgeClass: 'bg-sky-100 text-sky-900 dark:bg-sky-500/20 dark:text-sky-300 ring-1 ring-sky-300/70 dark:ring-sky-500/40',
  },
  {
    vai: 'Tình nguyện (tinh-nguyen)',
    user: 'tinhnguyen01',
    moTa: 'Chủ yếu dùng app hiện trường: gửi tin kêu cứu, dán tin SMS/Zalo để AI bóc tách; chỉ xem trạng thái tin mình đã gửi.',
    badge: 'App hiện trường',
    badgeClass: 'bg-slate-100 text-slate-800 dark:bg-navy-800 dark:text-navy-200 ring-1 ring-slate-300/70 dark:ring-navy-700',
  },
]
</script>

<template>
  <main class="min-h-svh bg-slate-50 px-4 py-8 text-slate-900 sm:py-12 lg:px-8 dark:bg-navy-950 dark:text-white">
    <div class="mx-auto flex max-w-4xl flex-col items-center justify-center">
      <!-- Logo và nhận diện hệ thống -->
      <header class="mb-8 text-center">
        <div class="mb-4 inline-flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-2 shadow-xs dark:border-navy-800 dark:bg-navy-900">
          <img src="/logo/mark-64.png" alt="" width="32" height="32" class="size-8">
          <span class="text-base font-bold tracking-tight text-navy-950 dark:text-white">DISASTER DX-OS</span>
        </div>
        <h1 class="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl dark:text-white">
          Cổng Xác Thực &amp; Điều Hành Cứu Trợ
        </h1>
        <p class="mt-2 text-sm text-slate-600 sm:text-base dark:text-navy-200">
          Bản demo · dữ liệu minh họa
        </p>
      </header>

      <!-- Khung đăng nhập chính -->
      <div class="w-full max-w-md rounded-xl border border-slate-200 bg-white p-6 shadow-lg sm:p-8 dark:border-navy-800 dark:bg-navy-900/90 dark:shadow-2xl">
        <h2 class="text-center text-lg font-bold text-slate-900 dark:text-white">
          Đăng nhập một lần (SSO)
        </h2>
        <p class="mt-1.5 text-center text-xs text-slate-600 dark:text-navy-300">
          Xác thực chuẩn OpenID Connect (PKCE) qua Keycloak (realm disaster)
        </p>

        <div class="mt-6 space-y-4">
          <UButton
            color="secondary"
            size="xl"
            block
            icon="i-lucide-log-in"
            class="font-bold text-navy-950 shadow-sm"
            @click="dangNhap(ve)"
          >
            Đăng nhập qua Keycloak
          </UButton>

          <div class="relative py-2">
            <div class="absolute inset-0 flex items-center">
              <span class="w-full border-t border-slate-200 dark:border-navy-800" />
            </div>
            <div class="relative flex justify-center text-xs">
              <span class="bg-white px-2 text-slate-500 dark:bg-navy-900 dark:text-navy-400">hoặc tra cứu công khai</span>
            </div>
          </div>

          <UButton
            to="/minh-bach"
            color="neutral"
            variant="outline"
            size="lg"
            block
            icon="i-lucide-shield-check"
            class="text-slate-700 hover:bg-slate-50 hover:text-slate-900 dark:text-navy-100 dark:hover:bg-navy-800 dark:hover:text-white"
          >
            Mở Cổng Tra cứu Minh bạch Sổ cái
          </UButton>
        </div>
      </div>

      <!-- Hướng dẫn tài khoản dự thi -->
      <section class="mt-10 w-full max-w-2xl" aria-labelledby="tieu-de-huong-dan">
        <h2 id="tieu-de-huong-dan" class="text-center text-xs font-semibold tracking-wider text-slate-500 uppercase dark:text-navy-300">
          Tài khoản kiểm thử chức năng (Hội thi OLP PMNM 2026)
        </h2>
        <div class="mt-4 divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white shadow-2xs dark:divide-navy-800/80 dark:border-navy-800 dark:bg-navy-900/50">
          <div
            v-for="tk in TAI_KHOAN"
            :key="tk.user"
            class="flex flex-col gap-2 p-4 text-xs sm:flex-row sm:items-center sm:justify-between sm:gap-4"
          >
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="text-sm font-bold text-slate-900 dark:text-white">{{ tk.vai }}</span>
                <span class="rounded-md px-2 py-0.5 text-xs font-semibold" :class="tk.badgeClass">
                  {{ tk.badge }}
                </span>
              </div>
              <p class="mt-1 text-xs text-slate-600 dark:text-navy-200">{{ tk.moTa }}</p>
            </div>
            <div class="shrink-0 font-mono text-xs font-medium text-slate-500 dark:text-nuoc-300">
              user: <span class="rounded bg-slate-100 px-2 py-1 font-semibold text-slate-900 ring-1 ring-slate-200 dark:bg-navy-950 dark:text-white dark:ring-navy-800">{{ tk.user }}</span>
            </div>
          </div>
        </div>
        <p class="mt-3 text-center text-xs text-slate-500 dark:text-navy-400">
          Mật khẩu tài khoản mẫu được quy định trong tệp cấu hình môi trường <code class="rounded bg-slate-200/70 px-1 py-0.5 font-mono text-slate-800 dark:bg-navy-900 dark:text-navy-300">.env</code> của hệ thống.
        </p>
      </section>
    </div>
  </main>
</template>
