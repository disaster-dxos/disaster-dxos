<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Hàng đợi phân công (#61).
//  - dieu-phoi: Cần xử lý (thông báo Centrifugo, #68) · Chờ phân công · Đang phân công · Đang cứu;
//  - cuu-ho: nhiệm vụ đang giao cho đội mình (Hasura lọc theo thành viên đội, #26).
// Tải lại khi subscription bản đồ (#60) báo tin đổi trạng thái, sau mỗi 15 giây (đội đổi, hạn nhận) và khi
// người dùng bấm "Tải lại". Bấm thẻ → /phan-cong/<id>.
import { NHOM, NHOM_CUU_HO, NHOM_THEO_VAI, nhomTin, type Nhom, type TinPhanCong } from '~/utils/phan-cong'
import type { ComputedRef, Ref } from 'vue'

const { vai, taiHang } = usePhanCong()
const tinRt = useTinKeuCuu()
const thongBao = useThongBao()
const ds: Ref<TinPhanCong[]> = ref([])
const dangTai = ref(false)
const daTai = ref(false)
const loi = ref('')
const now = useNow(1_000)

const canXuLy = computed(() => new Set(
  thongBao.ds.value.filter((tb) => tb.loai === 'can_xu_ly' && tb.incidentId).map((tb) => tb.incidentId!),
))
const nhom: ComputedRef<Record<Nhom, TinPhanCong[]>> = computed(() => nhomTin(ds.value, canXuLy.value))
const dsNhom: ComputedRef<Nhom[]> = computed(() => (vai.value ? NHOM_THEO_VAI[vai.value] : []))
const tieuDe = computed(() => (vai.value === 'cuu-ho' ? 'Nhiệm vụ của đội' : 'Phân công cứu hộ'))
const ICON: Record<Nhom, string> = {
  can_xu_ly: 'i-lucide-siren',
  cho_phan_cong: 'i-lucide-inbox',
  cho_doi_nhan: 'i-lucide-timer',
  dang_cuu: 'i-lucide-life-buoy',
}

async function tai() {
  if (!vai.value || dangTai.value) return
  dangTai.value = true
  try {
    ds.value = await taiHang()
    loi.value = ''
  } catch (e) {
    loi.value = e instanceof Error ? e.message : String(e)
  } finally {
    dangTai.value = false
    daTai.value = true
  }
}

// Subscription chỉ mang id + trạng thái: đổi là đủ biết cần tải lại hàng đợi
const chuKy = computed(() => tinRt.ds.value.map((t) => `${t.id}:${t.status}`).join(','))
watch(chuKy, () => { void tai() })

let hen: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  if (!vai.value) return
  if (vai.value === 'dieu-phoi') thongBao.batDau()
  tinRt.batDau()
  void tai()
  hen = setInterval(() => { void tai() }, 15_000)
})
onBeforeUnmount(() => {
  clearInterval(hen)
  thongBao.dung()
  tinRt.dung()
})
useHead({ title: () => `${tieuDe.value} · Disaster DX-OS` })
</script>

<template>
  <UDashboardPanel id="phan-cong" :ui="{ body: 'gap-4' }">
    <template #header>
      <UDashboardNavbar :title="tieuDe" :ui="{ right: 'gap-2' }">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #trailing>
          <UBadge color="neutral" variant="subtle" class="so">{{ ds.length }} tin</UBadge>
        </template>
        <template #right>
          <UButton
            color="neutral" variant="outline" icon="i-lucide-refresh-cw" class="min-h-10"
            :loading="dangTai" :disabled="dangTai || !vai" @click="tai"
          >
            <span class="max-sm:sr-only">{{ dangTai ? 'Đang tải…' : 'Tải lại' }}</span>
          </UButton>
          <ThongBaoRealtime v-if="vai === 'dieu-phoi'" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <UAlert
        v-if="!vai" role="alert" color="warning" variant="subtle" icon="i-lucide-shield-alert"
        title="Màn phân công dành cho vai Điều phối và Cứu hộ. Tài khoản này không có vai đó."
      />
      <template v-else>
        <UAlert v-if="loi" role="alert" color="error" variant="subtle" icon="i-lucide-circle-alert" title="Không tải được hàng đợi" :description="loi" />
        <UEmpty
          v-if="daTai && !loi && ds.length === 0" icon="i-lucide-inbox"
          :title="vai === 'cuu-ho' ? 'Đội của bạn chưa được giao nhiệm vụ nào.' : 'Không có tin nào đang chờ phân công.'"
        />
        <div class="grid min-h-0 flex-1 gap-4" :class="vai === 'dieu-phoi' ? 'lg:grid-cols-4 md:grid-cols-2' : 'md:grid-cols-2'">
          <section
            v-for="n in dsNhom" :key="n" :aria-labelledby="`nhom-${n}`"
            class="flex min-w-0 flex-col rounded-lg p-3 ring ring-inset"
            :class="n === 'can_xu_ly' && nhom[n].length ? 'bg-error/5 ring-error/30 dark:bg-error/10' : 'bg-muted ring-default'"
          >
            <header class="mb-3 px-0.5">
              <h2 :id="`nhom-${n}`" class="flex items-center gap-2 text-base font-semibold" :class="n === 'can_xu_ly' && nhom[n].length ? 'text-error' : 'text-highlighted'">
                <UIcon :name="ICON[n]" class="size-5 shrink-0" />
                {{ (vai === 'cuu-ho' && NHOM_CUU_HO[n]) || NHOM[n].tieuDe }}
                <UBadge
                  :color="n === 'can_xu_ly' && nhom[n].length ? 'error' : 'neutral'" :variant="n === 'can_xu_ly' && nhom[n].length ? 'solid' : 'subtle'"
                  class="so ms-auto rounded-full"
                >
                  {{ nhom[n].length }}
                </UBadge>
              </h2>
              <p class="mt-1 text-xs leading-snug text-muted">{{ NHOM[n].moTa }}</p>
            </header>
            <ul class="space-y-2.5">
              <li v-for="t in nhom[n]" :key="t.id">
                <TheTinPhanCong :tin="t" :now="now" :can-xu-ly="n === 'can_xu_ly'" />
              </li>
            </ul>
            <p v-if="nhom[n].length === 0" class="rounded-md border border-dashed border-accented px-3 py-6 text-center text-sm text-muted">Trống</p>
          </section>
        </div>
      </template>
    </template>
  </UDashboardPanel>
</template>
