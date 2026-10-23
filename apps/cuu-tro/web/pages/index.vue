<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Trang điều phối: bản đồ lớn + danh sách tin kêu cứu. Dữ liệu GIẢ (utils/tin-gia.ts) tới khi #60
// nối GraphQL subscription qua /graphql của API Gateway.
import { laDieuPhoi } from '~/utils/session'
import { MUC_KHAN, TRANG_THAI, demTheoTrangThai, sapXepTin, tinGia, type MucKhan, type TrangThai } from '~/utils/tin-gia'

const { user } = useAuth()
// Thông báo realtime (#68) chỉ cho người điều phối: tin mới, cần xử lý, cảnh báo mực nước
const thongBao = useThongBao()
onMounted(() => { if (laDieuPhoi(user.value)) thongBao.batDau() })
onBeforeUnmount(() => thongBao.dung())
const ds = ref(sapXepTin(tinGia()))
const chon = ref<string | null>(null)
const dem = computed(() => demTheoTrangThai(ds.value))
const hienThi: TrangThai[] = ['tiep_nhan', 'phan_cong', 'dang_cuu', 'da_cuu']
const mucKhan = Object.entries(MUC_KHAN) as [MucKhan, (typeof MUC_KHAN)[MucKhan]][]
</script>

<template>
  <div class="flex h-full flex-col">
    <AppHeader />
    <p v-if="user && !laDieuPhoi(user)" class="bg-amber-100 px-4 py-2 text-sm text-amber-900" role="alert">
      Tài khoản này không có vai trò Điều phối: chỉ xem được, không phân công được.
    </p>
    <div class="flex min-h-0 flex-1 flex-col lg:flex-row">
      <section class="relative min-h-[50vh] flex-1 lg:min-h-0">
        <BanDo :ds="ds" :chon="chon" @chon="chon = $event" />
        <div class="pointer-events-none absolute bottom-8 right-2 rounded-lg bg-white/95 p-3 text-xs shadow">
          <p class="mb-1 font-bold text-navy">Mức khẩn</p>
          <p v-for="[k, v] in mucKhan" :key="k" class="flex items-center gap-2">
            <span class="h-3 w-3 rounded-full" :style="{ background: v.mau }" aria-hidden="true" />{{ v.nhan }}
          </p>
        </div>
      </section>
      <aside class="flex min-h-0 w-full flex-col border-l border-slate-200 bg-white lg:w-[400px]" aria-labelledby="tieu-de-ds">
        <div class="border-b border-slate-200 px-4 py-3">
          <div class="flex items-baseline justify-between">
            <h1 id="tieu-de-ds" class="text-base font-bold text-navy">Tin kêu cứu</h1>
            <span class="rounded bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-800">Dữ liệu giả</span>
          </div>
          <dl class="mt-2 grid grid-cols-4 gap-2 text-center">
            <div v-for="s in hienThi" :key="s" class="rounded-lg bg-slate-100 py-1.5">
              <dt class="text-[11px] text-slate-600">{{ TRANG_THAI[s] }}</dt>
              <dd class="text-lg font-bold" :class="s === 'tiep_nhan' ? 'text-cam' : 'text-navy'">{{ dem[s] }}</dd>
            </div>
          </dl>
        </div>
        <div class="min-h-0 flex-1 overflow-y-auto">
          <DanhSachTin :ds="ds" :chon="chon" @chon="chon = $event" />
        </div>
        <p class="border-t border-slate-200 px-4 py-2 text-[11px] text-slate-500">DTU_DZ_1 · OLP PMNM 2026</p>
      </aside>
    </div>
  </div>
</template>
