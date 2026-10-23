<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Trang điều phối: bản đồ lớn + danh sách tin kêu cứu thời gian thực (#60). Dữ liệu thật từ Hasura qua
// GraphQL subscription ở API Gateway (composables/useTinKeuCuu.ts); bộ lọc dùng chung cho bản đồ và danh
// sách; bấm điểm hoặc dòng → ô chi tiết.
import { laCuuHo, laDieuPhoi } from '~/utils/session'
import {
  DS_MUC_KHAN, DS_TRANG_THAI, MAU_TRANG_THAI, MUC_KHAN, TRANG_THAI, boLocMacDinh, demTheoTrangThai, locTin, noiTinMoi,
  type BoLoc,
} from '~/utils/tin'

const { user, dangNhap } = useAuth()
// Thông báo realtime (#68) chỉ cho người điều phối: tin mới, cần xử lý, cảnh báo mực nước
const thongBao = useThongBao()
const tin = useTinKeuCuu()
const { ds, moi, trangThai, loi, capNhatLuc } = tin
onMounted(() => {
  if (laDieuPhoi(user.value)) thongBao.batDau()
  tin.batDau()
})
onBeforeUnmount(() => {
  thongBao.dung()
  tin.dung()
})

const loc = ref<BoLoc>(boLocMacDinh())
// /?tin=<id>: mở sẵn tin (từ màn phân công, #61)
const route = useRoute()
const chon = ref<string | null>(typeof route.query.tin === 'string' ? route.query.tin : null)
const daLoc = computed(() => locTin(ds.value, loc.value))
const dsHienThi = computed(() => noiTinMoi(daLoc.value, moi.value))
const tinChon = computed(() => ds.value.find((t) => t.id === chon.value) ?? null)
const dem = computed(() => demTheoTrangThai(daLoc.value))
const hienThi = ['tiep_nhan', 'phan_cong', 'dang_cuu', 'da_cuu'] as const

const KET_NOI = {
  'tat': { nhan: 'Chưa kết nối', mau: 'bg-slate-400' },
  'dang-ket-noi': { nhan: 'Đang kết nối…', mau: 'bg-amber-400' },
  'da-ket-noi': { nhan: 'Trực tiếp', mau: 'bg-emerald-500' },
  'mat-ket-noi': { nhan: 'Mất kết nối', mau: 'bg-red-600' },
  'het-phien': { nhan: 'Hết phiên', mau: 'bg-red-600' },
  'loi': { nhan: 'Lỗi dữ liệu', mau: 'bg-red-600' },
} as const
const ketNoi = computed(() => KET_NOI[trangThai.value])
const gioCapNhat = computed(() => capNhatLuc.value
  ? new Date(capNhatLuc.value).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  : '')
</script>

<template>
  <div class="flex h-full flex-col">
    <AppHeader />
    <p v-if="user && laCuuHo(user) && !laDieuPhoi(user)" class="bg-sky-50 px-4 py-2 text-sm text-navy" role="status">
      Bản đồ chỉ hiện tin đang giao cho đội của bạn.
      <NuxtLink to="/phan-cong" class="font-bold text-nuoc underline">Mở nhiệm vụ của đội</NuxtLink> để nhận, từ chối, xác nhận đã cứu.
    </p>
    <p v-else-if="user && !laDieuPhoi(user)" class="bg-amber-100 px-4 py-2 text-sm text-amber-900" role="alert">
      Tài khoản này không có vai trò Điều phối: chỉ thấy tin được phép xem, không phân công được.
    </p>
    <div class="flex min-h-0 flex-1 flex-col lg:flex-row">
      <section class="relative min-h-[50vh] flex-1 lg:min-h-0">
        <BanDo :ds="daLoc" :moi="moi" :chon="chon" @chon="chon = $event" />
        <!-- Mất kết nối / hết phiên: băng nổi trên bản đồ, dữ liệu cũ vẫn hiện nhưng có thể đã lỗi thời -->
        <div
          v-if="trangThai === 'mat-ket-noi' || trangThai === 'het-phien' || trangThai === 'loi'"
          class="absolute left-1/2 top-3 z-10 flex w-[min(92%,520px)] -translate-x-1/2 items-center gap-3 rounded-lg border-l-4 border-red-600 bg-white px-4 py-2.5 text-sm shadow-lg"
          role="alert"
        >
          <span class="h-2.5 w-2.5 shrink-0 animate-pulse rounded-full bg-red-600" aria-hidden="true" />
          <span class="min-w-0 flex-1">
            <strong class="text-red-700">{{ trangThai === 'het-phien' ? 'Phiên đăng nhập đã hết' : trangThai === 'loi' ? 'Không nhận được dữ liệu' : 'Mất kết nối tới máy chủ' }}</strong>
            <span class="block text-xs text-slate-600">
              {{ trangThai === 'het-phien' ? 'Đăng nhập lại để tiếp tục nhận tin.' : loi || 'Đang tự kết nối lại. Bản đồ đang hiện dữ liệu cũ' + (gioCapNhat ? ` (lúc ${gioCapNhat})` : '') + '.' }}
            </span>
          </span>
          <button
            v-if="trangThai === 'het-phien'" type="button"
            class="rounded-lg bg-navy px-3 py-1.5 text-xs font-bold text-white hover:bg-navy-700"
            @click="dangNhap('/')"
          >
            Đăng nhập lại
          </button>
          <button
            v-else type="button"
            class="rounded-lg border border-navy px-3 py-1.5 text-xs font-bold text-navy hover:bg-navy hover:text-white"
            @click="tin.thuLai()"
          >
            Thử lại
          </button>
        </div>
        <div class="pointer-events-none absolute bottom-8 right-2 rounded-lg bg-white/95 p-3 text-xs shadow">
          <p class="mb-1 font-bold text-navy">Mức khẩn (màu điểm)</p>
          <p v-for="k in DS_MUC_KHAN" :key="k" class="flex items-center gap-2">
            <span class="h-3 w-3 rounded-full" :style="{ background: MUC_KHAN[k].mau }" aria-hidden="true" />{{ MUC_KHAN[k].nhan }}
          </p>
          <p class="mb-1 mt-2 font-bold text-navy">Trạng thái (màu viền)</p>
          <p v-for="s in DS_TRANG_THAI" :key="s" class="flex items-center gap-2">
            <span class="h-3.5 w-3.5 rounded-full border-[3px] bg-slate-300 ring-1 ring-slate-400" :style="{ borderColor: MAU_TRANG_THAI[s] }" aria-hidden="true" />{{ TRANG_THAI[s] }}
          </p>
        </div>
      </section>
      <aside class="flex min-h-0 w-full flex-col border-l border-slate-200 bg-white lg:w-[420px]" aria-labelledby="tieu-de-ds">
        <div class="space-y-3 border-b border-slate-200 px-4 py-3">
          <div class="flex items-baseline justify-between gap-2">
            <h1 id="tieu-de-ds" class="text-base font-bold text-navy">Tin kêu cứu</h1>
            <span class="flex items-center gap-1.5 text-xs text-slate-600" :title="gioCapNhat ? `Cập nhật lúc ${gioCapNhat}` : undefined">
              <span class="h-2.5 w-2.5 rounded-full" :class="[ketNoi.mau, trangThai === 'da-ket-noi' ? 'animate-pulse' : '']" aria-hidden="true" />
              <span><strong>{{ ketNoi.nhan }}</strong><template v-if="gioCapNhat"> · {{ gioCapNhat }}</template></span>
            </span>
          </div>
          <dl class="grid grid-cols-4 gap-2 text-center">
            <div v-for="s in hienThi" :key="s" class="rounded-lg bg-slate-100 py-1.5">
              <dt class="text-[11px] text-slate-600">{{ TRANG_THAI[s] }}</dt>
              <dd class="text-lg font-bold" :class="s === 'tiep_nhan' ? 'text-cam' : 'text-navy'">{{ dem[s] }}</dd>
            </div>
          </dl>
          <BoLocTin v-model="loc" :ds="ds" />
        </div>
        <ChiTietTin v-if="tinChon" :tin="tinChon" @dong="chon = null" />
        <div class="min-h-0 flex-1 overflow-y-auto">
          <DanhSachTin :ds="dsHienThi" :moi="moi" :chon="chon" @chon="chon = $event" />
          <p v-if="dsHienThi.length === 0" class="px-4 py-8 text-center text-sm text-slate-500">
            {{ trangThai === 'da-ket-noi' ? (ds.length ? 'Không có tin nào khớp bộ lọc.' : 'Chưa có tin kêu cứu nào.') : 'Đang chờ dữ liệu…' }}
          </p>
        </div>
        <p class="border-t border-slate-200 px-4 py-2 text-[11px] text-slate-500">
          {{ dsHienThi.length }}/{{ ds.length }} tin · DTU_DZ_1 · OLP PMNM 2026
        </p>
      </aside>
    </div>
  </div>
</template>
