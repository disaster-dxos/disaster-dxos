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
  <UDashboardPanel id="phan-cong">
    <template #header>
      <UDashboardNavbar :title="tieuDe">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <ThongBaoRealtime v-if="vai === 'dieu-phoi'" />
        </template>
      </UDashboardNavbar>
    </template>
    <template #body>
      <main class="mx-auto w-full max-w-6xl flex-1">
        <p v-if="!vai" class="rounded-lg bg-amber-100 px-4 py-3 text-sm text-amber-900" role="alert">
          Màn phân công dành cho vai Điều phối và Cứu hộ. Tài khoản này không có vai đó.
        </p>
        <template v-else>
          <div class="mb-3 flex flex-wrap items-center gap-2">
            <span class="text-xs text-slate-500">{{ ds.length }} tin</span>
            <button
              type="button"
              class="ml-auto min-h-11 rounded-lg border border-navy px-4 text-sm font-bold text-navy hover:bg-navy hover:text-white disabled:opacity-50"
              :disabled="dangTai" @click="tai"
            >
              {{ dangTai ? 'Đang tải…' : 'Tải lại' }}
            </button>
          </div>
          <p v-if="loi" class="mb-3 rounded-lg border-l-4 border-red-600 bg-red-50 px-4 py-2 text-sm text-red-800" role="alert">{{ loi }}</p>
          <p v-if="daTai && !loi && ds.length === 0" class="rounded-lg bg-white px-4 py-8 text-center text-sm text-slate-500">
            {{ vai === 'cuu-ho' ? 'Đội của bạn chưa được giao nhiệm vụ nào.' : 'Không có tin nào đang chờ phân công.' }}
          </p>
          <div class="grid gap-4" :class="vai === 'dieu-phoi' ? 'lg:grid-cols-4 md:grid-cols-2' : 'md:grid-cols-2'">
            <section v-for="n in dsNhom" :key="n" :aria-labelledby="`nhom-${n}`" class="min-w-0">
              <h2 :id="`nhom-${n}`" class="flex items-baseline gap-2 text-sm font-bold" :class="n === 'can_xu_ly' ? 'text-red-700' : 'text-navy'">
                {{ (vai === 'cuu-ho' && NHOM_CUU_HO[n]) || NHOM[n].tieuDe }}
                <span class="rounded-full px-2 text-xs" :class="n === 'can_xu_ly' && nhom[n].length ? 'bg-red-600 text-white' : 'bg-slate-200 text-slate-700'">{{ nhom[n].length }}</span>
              </h2>
              <p class="mb-2 text-[11px] text-slate-500">{{ NHOM[n].moTa }}</p>
              <ul class="space-y-2">
                <li v-for="t in nhom[n]" :key="t.id">
                  <TheTinPhanCong :tin="t" :now="now" :can-xu-ly="n === 'can_xu_ly'" />
                </li>
              </ul>
              <p v-if="nhom[n].length === 0" class="rounded-lg border border-dashed border-slate-300 px-3 py-4 text-center text-xs text-slate-400">Trống</p>
            </section>
          </div>
        </template>
      </main>
    </template>
  </UDashboardPanel>
</template>
