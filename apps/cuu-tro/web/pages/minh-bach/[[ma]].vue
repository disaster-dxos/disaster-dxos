<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Trang Minh bạch cứu trợ công khai, không cần đăng nhập (#78, nâng cấp ở #63). Một ô tra cho cả phiếu nhập/xuất
// kho và bút toán tiền thu/chi: GET /workflow/minh-bach/xac-minh/{ma} qua gateway (#89) → kết luận của máy chủ,
// rồi trình duyệt TỰ kiểm lại bằng chứng (components/TuKiemChung.vue, khóa công khai từ /ledger/verifier).
// Đường dẫn chia sẻ được: /minh-bach/<mã> (mã QR trên phiếu trỏ tới đây); /minh-bach?ma=<mã> cũng tra sẵn.
// Bên cạnh: quỹ tiền cứu trợ và sổ cái gần đây (components/SoCaiGanDay.vue). Không có dữ liệu cá nhân.
import {
  CHIEU, HANG_MUC, LOAI_MA, TRANG_THAI_PHIEU, chuanHoaMa, docPhanHoi, laMaHopLe, loiKhiTra, tieuDeKetQua, urlKhoaSoCai,
  urlXacMinh, type KetQuaXacMinh,
} from '~/utils/minh-bach'
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
const kq: Ref<KetQuaXacMinh | null> = ref(null)
// vue-tsc của dự án suy ra any: ghi kiểu rõ cho giá trị dùng làm khóa trong template
const tt: ComputedRef<(typeof TRANG_THAI_PHIEU)[KetQuaXacMinh['trang_thai']] | null> = computed(() => (kq.value ? TRANG_THAI_PHIEU[kq.value.trang_thai] : null))
const tieuDe = computed(() => (kq.value ? tieuDeKetQua(kq.value) : null))
const loi = ref('')
const dangTai = ref(false)
const vkey = ref<string | null>(null)

/** Khóa công khai của sổ cái: tải một lần; lỗi thì bước kiểm chữ ký báo "không kiểm được". */
async function taiKhoa() {
  if (vkey.value) return
  try {
    const r = await fetch(urlKhoaSoCai(gw), { cache: 'no-store' })
    if (r.ok) vkey.value = (await r.text()).trim() || null
  } catch { /* để null */ }
}

async function tra() {
  const m = chuanHoaMa(ma.value)
  kq.value = null
  if (!m) { loi.value = 'Nhập mã in trên phiếu kho hoặc chứng từ thu/chi.'; return }
  if (!laMaHopLe(m)) { loi.value = 'Mã gồm 36 ký tự (chữ số, chữ a–f và dấu gạch), in dưới mã QR trên phiếu.'; return }
  ma.value = m
  // Đường dẫn chia sẻ được cho đúng mã đang xem
  if (route.params.ma !== m) void router.replace({ path: `/minh-bach/${m}` })
  dangTai.value = true
  loi.value = ''
  try {
    const [r] = await Promise.all([fetch(urlXacMinh(gw, m), { cache: 'no-store' }), taiKhoa()])
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
// Bấm một mục trong "Sổ cái gần đây" (đổi đường dẫn, cùng trang) → tra mã đó
watch(() => route.params.ma, (p) => {
  if (typeof p === 'string' && p && chuanHoaMa(p) !== chuanHoaMa(ma.value)) { ma.value = p; void tra() }
})

const gio = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' }) : '—')
const b = computed(() => kq.value?.ban_ghi_chuan_hoa ?? {})
const hd = computed(() => kq.value?.hien_thi ?? {})
useHead({ title: 'Minh bạch cứu trợ · Disaster DX-OS' })
</script>

<template>
  <div class="flex min-h-full flex-col bg-muted">
    <header class="border-b border-default bg-default">
      <div class="mx-auto flex h-16 max-w-6xl items-center gap-3 px-4">
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

    <main class="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:py-10">
      <div class="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-10">
        <section aria-labelledby="tieu-de-tra" class="space-y-6">
          <div>
            <h1 id="tieu-de-tra" class="text-balance text-2xl font-bold leading-tight text-highlighted sm:text-3xl">Mỗi phiếu, mỗi đồng cứu trợ đều kiểm chứng được</h1>
            <p class="mt-3 max-w-prose text-base text-default">
              Mọi lần nhập, xuất hàng và mọi khoản thu, chi tiền cứu trợ được ghi vào một sổ cái chỉ-thêm, có chữ ký số.
              Nhập mã in trên phiếu để xem hàng, tiền đã đi đâu và tự kiểm sổ cái ngay trên máy của bạn. Sổ cái không chứa thông tin cá nhân.
            </p>
          </div>
          <div>
            <UCard :ui="{ body: 'p-4 sm:p-5' }">
              <form @submit.prevent="tra">
                <UFormField label="Mã phiếu hoặc mã bút toán" name="ma-phieu" help="Mã gồm 36 ký tự, in dưới mã QR trên phiếu kho hoặc chứng từ thu/chi." :ui="{ label: 'text-base font-semibold' }">
                  <div class="flex gap-2 max-sm:flex-col">
                    <UInput
                      id="ma-phieu" v-model="ma" size="xl" autocomplete="off" spellcheck="false" placeholder="vd 3f6c2a10-8b4d-…"
                      icon="i-lucide-scan-line" class="min-w-0 flex-1" :ui="{ base: 'font-mono text-base' }"
                    />
                    <UButton type="submit" color="secondary" size="xl" :loading="dangTai" class="min-h-12 justify-center font-semibold">
                      {{ dangTai ? 'Đang tra…' : 'Tra và kiểm' }}
                    </UButton>
                  </div>
                </UFormField>
              </form>
            </UCard>
            <UAlert v-if="loi" role="alert" class="mt-3" color="error" variant="subtle" icon="i-lucide-circle-alert" :title="loi" />
          </div>
          <SoCaiGanDay :chon="kq?.ma" />
        </section>

        <section v-if="kq && tt && tieuDe" aria-labelledby="tieu-de-kq" class="space-y-4" data-testid="ket-qua">
          <div aria-live="polite">
            <UAlert
              :color="tt.mau" variant="solid" :icon="tt.icon"
              :ui="{ title: 'text-lg font-bold', icon: 'size-7', description: 'text-sm opacity-95' }"
              :title="tt.nhan" :description="kq.chi_tiet.join(' · ')"
            >
              <template #title><span id="tieu-de-kq">Máy chủ: {{ tt.nhan }}</span></template>
            </UAlert>
          </div>

          <UCard :ui="{ body: 'p-5' }">
            <div class="flex flex-wrap items-center gap-2">
              <UBadge color="neutral" variant="subtle" :icon="kq.loai === 'khoan_tien' ? 'i-lucide-banknote' : 'i-lucide-package'">{{ LOAI_MA[kq.loai] }}</UBadge>
              <p class="text-sm font-semibold text-muted">{{ CHIEU[b.direction ?? ''] ?? b.direction }}</p>
            </div>
            <p class="mt-2 text-2xl font-bold leading-tight text-highlighted sm:text-3xl">
              <span class="so">{{ tieuDe.so }}</span> {{ tieuDe.donVi }} {{ tieuDe.noiDung }}
            </p>

            <div v-if="kq.loai === 'phieu_kho'" class="mt-4 flex items-stretch gap-3 border-y border-default py-3 max-sm:flex-col">
              <div class="min-w-0 flex-1">
                <p class="flex items-center gap-1.5 text-xs font-semibold text-muted"><UIcon name="i-lucide-warehouse" class="size-4" />Từ kho</p>
                <p class="mt-0.5 font-medium">{{ hd.kho ?? '—' }}</p>
              </div>
              <UIcon name="i-lucide-arrow-right" class="size-5 shrink-0 self-center text-muted max-sm:rotate-90" />
              <div class="min-w-0 flex-1">
                <p class="flex items-center gap-1.5 text-xs font-semibold text-muted"><UIcon name="i-lucide-map-pin" class="size-4" />Tới điểm nhận</p>
                <p class="mt-0.5 font-medium">{{ hd.diem_nhan ?? '—' }}</p>
              </div>
            </div>
            <dl v-else class="mt-4 grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 border-y border-default py-3 text-base">
              <dt class="text-muted">Hạng mục</dt><dd>{{ HANG_MUC[b.category ?? ''] ?? b.category }}</dd>
              <template v-if="b.purpose"><dt class="text-muted">Mục đích</dt><dd>{{ b.purpose }}</dd></template>
              <template v-if="hd.diem_nhan"><dt class="text-muted">Điểm nhận</dt><dd>{{ hd.diem_nhan }}</dd></template>
              <template v-if="b.supply_movement_id">
                <dt class="text-muted">Phiếu kho kèm</dt>
                <dd><NuxtLink :to="`/minh-bach/${b.supply_movement_id}`" class="font-mono text-sm text-primary underline">{{ b.supply_movement_id }}</NuxtLink></dd>
              </template>
            </dl>

            <dl class="mt-3 grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-base">
              <dt class="text-muted">Lập lúc</dt><dd class="so">{{ gio(b.created_at) }}</dd>
              <dt class="text-muted">Ghi sổ cái</dt><dd class="so">{{ gio(kq.so_cai.logged_at) }}<template v-if="kq.so_cai.index !== null"> · lá số {{ kq.so_cai.index }}</template></dd>
              <template v-if="b.note"><dt class="text-muted">Ghi chú</dt><dd>{{ b.note }}</dd></template>
              <dt class="text-muted">Mã</dt><dd class="break-all font-mono text-sm">{{ kq.ma }}</dd>
            </dl>
          </UCard>

          <TuKiemChung :kq="kq" :vkey="vkey" />
        </section>

        <UEmpty
          v-else icon="i-lucide-receipt-text" variant="outline" class="self-start bg-default"
          title="Chưa tra mã nào"
          description="Kết quả hiện ở đây: hàng gì, bao nhiêu tiền, từ đâu tới điểm nhận nào, sổ cái có xác nhận không, và trình duyệt tự kiểm lại bằng chứng."
        />
      </div>
    </main>
    <footer class="border-t border-default px-4 py-3 text-center text-xs text-muted">DTU_DZ_1 · OLP PMNM 2026 · Dữ liệu minh họa là dữ liệu giả</footer>
  </div>
</template>
