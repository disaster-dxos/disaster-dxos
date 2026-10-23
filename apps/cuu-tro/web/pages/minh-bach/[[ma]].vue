<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Trang Minh bạch cứu trợ công khai, không cần đăng nhập (#63, #78). Tra một phiếu nhập/xuất kho bằng mã,
// gọi GET /workflow/minh-bach/phieu/{ma} qua gateway (#28) và hiện kết quả xác minh trên sổ cái Tessera.
// Đường dẫn chia sẻ được: /minh-bach/<mã> (mã QR trên phiếu trỏ tới đây); /minh-bach?ma=<mã> cũng tra sẵn.
import { TRANG_THAI_PHIEU, chuanHoaMa, docPhanHoi, laMaHopLe, loiKhiTra, urlTraPhieu, type KetQuaPhieu } from '~/utils/minh-bach'
import type { ComputedRef, Ref } from 'vue'

definePageMeta({ layout: false })

const route = useRoute()
const router = useRouter()
const gw = useRuntimeConfig().public.gatewayUrl as string
const maTuDuong = () => {
  const p = route.params.ma
  if (typeof p === 'string' && p) return p
  return typeof route.query.ma === 'string' ? route.query.ma : ''
}
const ma = ref(maTuDuong())
const kq: Ref<KetQuaPhieu | null> = ref(null)
// vue-tsc của dự án suy ra any: ghi kiểu rõ cho giá trị dùng làm khóa trong template
const tt: ComputedRef<(typeof TRANG_THAI_PHIEU)[KetQuaPhieu['trang_thai']] | null> = computed(() => (kq.value ? TRANG_THAI_PHIEU[kq.value.trang_thai] : null))
const loi = ref('')
const dangTai = ref(false)

async function tra() {
  const m = chuanHoaMa(ma.value)
  kq.value = null
  if (!m) { loi.value = 'Nhập mã phiếu in trên phiếu nhập/xuất kho.'; return }
  if (!laMaHopLe(m)) { loi.value = 'Mã phiếu gồm 36 ký tự (chữ số, chữ a–f và dấu gạch), in dưới mã QR trên phiếu.'; return }
  ma.value = m
  // Đường dẫn chia sẻ được cho đúng phiếu đang xem
  if (route.params.ma !== m) void router.replace({ path: `/minh-bach/${m}` })
  dangTai.value = true
  loi.value = ''
  try {
    const r = await fetch(urlTraPhieu(gw, m), { cache: 'no-store' })
    const kqTra = docPhanHoi(r.status, r.status === 200 ? await r.json().catch(() => null) : null)
    if (kqTra.ok) kq.value = kqTra.kq
    else loi.value = kqTra.loi
  } catch (e) {
    loi.value = loiKhiTra(e)
  } finally {
    dangTai.value = false
  }
}
onMounted(() => { if (ma.value) void tra() })

const gio = (iso: string | null) => (iso ? new Date(iso).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' }) : '—')
const soLuong = (s: string) => Number(s).toLocaleString('vi-VN')
useHead({ title: 'Minh bạch cứu trợ · Disaster DX-OS' })
</script>

<template>
  <div class="flex min-h-full flex-col bg-muted">
    <header class="border-b border-default bg-default">
      <div class="mx-auto flex h-16 max-w-5xl items-center gap-3 px-4">
        <span class="grid size-10 shrink-0 place-items-center rounded-md bg-white ring ring-default">
          <img src="/logo/mark-64.png" alt="" width="32" height="32" class="size-8">
        </span>
        <div class="min-w-0 leading-tight">
          <p class="truncate text-base font-bold text-highlighted">Minh bạch cứu trợ</p>
          <p class="truncate text-xs text-muted">Disaster DX-OS · Ứng phó Thiên tai &amp; Cứu trợ Cộng đồng</p>
        </div>
        <UColorModeButton class="ms-auto" size="lg" />
      </div>
    </header>

    <main class="mx-auto w-full max-w-5xl flex-1 px-4 py-6 sm:py-10">
      <div class="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-10">
        <section aria-labelledby="tieu-de-tra">
          <h1 id="tieu-de-tra" class="text-balance text-2xl font-bold leading-tight text-highlighted sm:text-3xl">Mỗi phiếu cứu trợ đều kiểm chứng được</h1>
          <p class="mt-3 max-w-prose text-base text-default">
            Mọi lần nhập và xuất hàng cứu trợ được ghi vào một sổ cái chỉ-thêm, có chữ ký số. Nhập mã in trên phiếu để
            xem hàng đã đi đâu và sổ cái có khớp không. Sổ cái không chứa thông tin cá nhân.
          </p>
          <UCard class="mt-6" :ui="{ body: 'p-4 sm:p-5' }">
            <form @submit.prevent="tra">
              <UFormField label="Mã phiếu" name="ma-phieu" help="Mã gồm 36 ký tự, in dưới mã QR trên phiếu." :ui="{ label: 'text-base font-semibold' }">
                <div class="flex gap-2 max-sm:flex-col">
                  <UInput
                    id="ma-phieu" v-model="ma" size="xl" autocomplete="off" spellcheck="false" placeholder="vd 3f6c2a10-8b4d-…"
                    icon="i-lucide-scan-line" class="min-w-0 flex-1" :ui="{ base: 'font-mono text-base' }"
                  />
                  <UButton type="submit" color="secondary" size="xl" :loading="dangTai" class="min-h-12 justify-center font-semibold">
                    {{ dangTai ? 'Đang tra…' : 'Tra phiếu' }}
                  </UButton>
                </div>
              </UFormField>
            </form>
          </UCard>
          <UAlert v-if="loi" role="alert" class="mt-3" color="error" variant="subtle" icon="i-lucide-circle-alert" :title="loi" />
        </section>

        <section v-if="kq && tt" aria-labelledby="tieu-de-kq" class="space-y-4">
          <div aria-live="polite">
            <UAlert
              :color="tt.mau" variant="solid" :icon="tt.icon"
              :ui="{ title: 'text-lg font-bold', icon: 'size-7', description: 'text-sm opacity-95' }"
              :title="tt.nhan" :description="kq.chi_tiet.join(' · ')"
            >
              <template #title><span id="tieu-de-kq">{{ tt.nhan }}</span></template>
            </UAlert>
          </div>

          <UCard :ui="{ body: 'p-5' }">
            <p class="text-sm font-semibold text-muted">{{ kq.ban_ghi_chuan_hoa.direction === 'nhap' ? 'Phiếu nhập kho' : 'Phiếu xuất kho' }}</p>
            <p class="mt-1 text-2xl font-bold leading-tight text-highlighted sm:text-3xl">
              <span class="so">{{ soLuong(kq.ban_ghi_chuan_hoa.quantity) }}</span> {{ kq.hien_thi.don_vi }} {{ kq.hien_thi.mat_hang }}
            </p>
            <div class="mt-4 flex items-stretch gap-3 border-y border-default py-3 max-sm:flex-col">
              <div class="min-w-0 flex-1">
                <p class="flex items-center gap-1.5 text-xs font-semibold text-muted"><UIcon name="i-lucide-warehouse" class="size-4" />Từ kho</p>
                <p class="mt-0.5 font-medium">{{ kq.hien_thi.kho ?? '—' }}</p>
              </div>
              <UIcon name="i-lucide-arrow-right" class="size-5 shrink-0 self-center text-muted max-sm:rotate-90" />
              <div class="min-w-0 flex-1">
                <p class="flex items-center gap-1.5 text-xs font-semibold text-muted"><UIcon name="i-lucide-map-pin" class="size-4" />Tới điểm nhận</p>
                <p class="mt-0.5 font-medium">{{ kq.hien_thi.diem_nhan ?? '—' }}</p>
              </div>
            </div>
            <dl class="mt-3 grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-base">
              <dt class="text-muted">Lập phiếu</dt><dd class="so">{{ gio(kq.ban_ghi_chuan_hoa.created_at) }}</dd>
              <dt class="text-muted">Ghi sổ cái</dt><dd class="so">{{ gio(kq.so_cai.logged_at) }}<template v-if="kq.so_cai.index !== null"> · mục số {{ kq.so_cai.index }}</template></dd>
              <template v-if="kq.ban_ghi_chuan_hoa.note"><dt class="text-muted">Ghi chú</dt><dd>{{ kq.ban_ghi_chuan_hoa.note }}</dd></template>
            </dl>
          </UCard>

          <UCard :ui="{ body: 'p-0 sm:p-0' }">
            <UCollapsible>
              <UButton color="neutral" variant="ghost" block trailing-icon="i-lucide-chevron-down" class="min-h-12 justify-between px-5 font-semibold">
                Tự kiểm chứng (dành cho người kỹ thuật)
              </UButton>
              <template #content>
                <div class="space-y-3 px-5 pb-5">
                  <dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-xs">
                    <dt class="text-muted">SHA-256 bản ghi</dt><dd class="break-all font-mono">{{ kq.sha256 }}</dd>
                    <template v-if="kq.so_cai.checkpoint">
                      <dt class="text-muted">Sổ cái</dt><dd class="break-all font-mono">{{ kq.so_cai.checkpoint.origin }}</dd>
                      <dt class="text-muted">Kích thước cây</dt><dd class="so font-mono">{{ kq.so_cai.checkpoint.tree_size }}</dd>
                      <dt class="text-muted">Gốc cây</dt><dd class="break-all font-mono">{{ kq.so_cai.checkpoint.root_hash }}</dd>
                    </template>
                  </dl>
                  <pre class="overflow-x-auto rounded-md bg-navy-950 p-3 font-mono text-xs leading-5 text-white">{{ kq.tu_kiem_chung }}</pre>
                </div>
              </template>
            </UCollapsible>
          </UCard>
        </section>

        <UEmpty
          v-else icon="i-lucide-receipt-text" variant="outline" class="bg-default"
          title="Chưa tra phiếu nào"
          description="Kết quả hiện ở đây: hàng gì, bao nhiêu, từ kho nào tới điểm nhận nào, và sổ cái có xác nhận không."
        />
      </div>
    </main>
    <footer class="border-t border-default px-4 py-3 text-center text-xs text-muted">DTU_DZ_1 · OLP PMNM 2026 · Dữ liệu minh họa là dữ liệu giả</footer>
  </div>
</template>
