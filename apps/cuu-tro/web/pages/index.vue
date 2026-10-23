<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Trang điều phối: bản đồ lớn + cột tin kêu cứu thời gian thực (#60). Dữ liệu thật từ Hasura qua GraphQL
// subscription ở API Gateway (composables/useTinKeuCuu.ts); bộ lọc dùng chung cho bản đồ và danh sách;
// bấm điểm hoặc dòng → ngăn chi tiết nổi trên bản đồ (không che danh sách).
import { laCuuHo, laDieuPhoi } from '~/utils/session'
import { TRANG_THAI, boLocMacDinh, demTheoTrangThai, locTin, noiTinMoi, type BoLoc } from '~/utils/tin'

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
const laDp = computed(() => laDieuPhoi(user.value))

const KET_NOI = {
  'tat': { nhan: 'Chưa kết nối', mau: 'neutral' },
  'dang-ket-noi': { nhan: 'Đang kết nối…', mau: 'warning' },
  'da-ket-noi': { nhan: 'Trực tiếp', mau: 'success' },
  'mat-ket-noi': { nhan: 'Mất kết nối', mau: 'error' },
  'het-phien': { nhan: 'Hết phiên', mau: 'error' },
  'loi': { nhan: 'Lỗi dữ liệu', mau: 'error' },
} as const
const ketNoi = computed(() => KET_NOI[trangThai.value])
const gioCapNhat = computed(() => capNhatLuc.value
  ? new Date(capNhatLuc.value).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  : '')
const suCo = computed(() => trangThai.value === 'mat-ket-noi' || trangThai.value === 'het-phien' || trangThai.value === 'loi')
</script>

<template>
  <UDashboardPanel id="ban-do" :ui="{ body: 'relative p-0 sm:p-0 gap-0 overflow-hidden max-lg:min-h-[60svh]' }">
    <template #header>
      <UDashboardNavbar title="Bản đồ điều phối" :ui="{ right: 'gap-2' }">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UBadge :color="ketNoi.mau" variant="subtle" size="lg" class="gap-2" :title="gioCapNhat ? `Cập nhật lúc ${gioCapNhat}` : undefined">
            <span class="size-2 rounded-full bg-current" aria-hidden="true" />
            {{ ketNoi.nhan }}<span v-if="gioCapNhat" class="so font-normal max-sm:hidden"> · {{ gioCapNhat }}</span>
          </UBadge>
          <ThongBaoRealtime v-if="laDp" />
        </template>
      </UDashboardNavbar>
      <UAlert
        v-if="user && laCuuHo(user) && !laDp"
        color="info" variant="subtle" icon="i-lucide-info" class="rounded-none"
        title="Bản đồ chỉ hiện tin đang giao cho đội của bạn."
        :actions="[{ label: 'Mở nhiệm vụ của đội', to: '/phan-cong', color: 'info', variant: 'solid' }]"
      />
      <UAlert
        v-else-if="user && !laDp"
        color="warning" variant="subtle" icon="i-lucide-shield-alert" class="rounded-none"
        title="Tài khoản này không có vai trò Điều phối: chỉ thấy tin được phép xem, không phân công được."
      />
    </template>

    <template #body>
      <BanDo :ds="daLoc" :moi="moi" :chon="chon" :de-phai="tinChon ? 416 : 0" @chon="chon = $event" />

      <!-- Mất kết nối / hết phiên: băng nổi trên bản đồ, dữ liệu cũ vẫn hiện nhưng có thể đã lỗi thời -->
      <UAlert
        v-if="suCo"
        role="alert" color="error" variant="solid" icon="i-lucide-wifi-off"
        class="absolute left-1/2 top-3 z-10 w-[min(92%,560px)] -translate-x-1/2 shadow-lg"
        :title="trangThai === 'het-phien' ? 'Phiên đăng nhập đã hết' : trangThai === 'loi' ? 'Không nhận được dữ liệu' : 'Mất kết nối tới máy chủ'"
        :description="trangThai === 'het-phien' ? 'Đăng nhập lại để tiếp tục nhận tin.' : loi || 'Đang tự kết nối lại. Bản đồ đang hiện dữ liệu cũ' + (gioCapNhat ? ` (lúc ${gioCapNhat})` : '') + '.'"
        :actions="trangThai === 'het-phien'
          ? [{ label: 'Đăng nhập lại', color: 'neutral', variant: 'solid', onClick: () => dangNhap('/') }]
          : [{ label: 'Thử lại', color: 'neutral', variant: 'solid', onClick: () => tin.thuLai() }]"
      />

      <ChuThichBanDo class="absolute bottom-3 left-3 z-10 max-sm:hidden" />

      <ChiTietTin
        v-if="tinChon" :tin="tinChon"
        class="absolute inset-x-3 bottom-3 z-20 max-h-[70%] lg:inset-x-auto lg:bottom-auto lg:right-3 lg:top-3 lg:max-h-[calc(100%-1.5rem)] lg:w-[400px]"
        @dong="chon = null"
      />
    </template>
  </UDashboardPanel>

  <UDashboardPanel id="tin-keu-cuu" :default-size="27" :min-size="22" :max-size="36" resizable :ui="{ body: 'p-0 sm:p-0 gap-0' }">
    <template #header>
      <UDashboardNavbar :toggle="false">
        <template #title>
          <h1 id="tieu-de-ds" class="text-base font-semibold text-highlighted">Tin kêu cứu</h1>
        </template>
        <template #trailing>
          <UBadge color="neutral" variant="subtle" class="so">{{ dsHienThi.length }}/{{ ds.length }}</UBadge>
        </template>
      </UDashboardNavbar>
      <div class="space-y-4 border-b border-default px-4 py-4 sm:px-5">
        <dl class="grid grid-cols-4 gap-2">
          <div
            v-for="s in hienThi" :key="s"
            class="flex flex-col justify-between rounded-md px-1.5 py-2 text-center ring ring-inset"
            :class="s === 'tiep_nhan' ? 'bg-cam-50 ring-cam-200 dark:bg-cam-950/40 dark:ring-cam-900' : 'bg-elevated/50 ring-default'"
          >
            <dt class="text-xs leading-tight text-muted">{{ TRANG_THAI[s] }}</dt>
            <dd class="so text-2xl font-bold leading-8" :class="s === 'tiep_nhan' ? 'text-cam-800 dark:text-cam-300' : 'text-highlighted'">{{ dem[s] }}</dd>
          </div>
        </dl>
        <BoLocTin v-model="loc" :ds="ds" />
      </div>
    </template>
    <template #body>
      <DanhSachTin :ds="dsHienThi" :moi="moi" :chon="chon" aria-labelledby="tieu-de-ds" @chon="chon = $event" />
      <UEmpty
        v-if="dsHienThi.length === 0"
        :icon="trangThai === 'da-ket-noi' ? 'i-lucide-filter-x' : 'i-lucide-loader'"
        :title="trangThai === 'da-ket-noi' ? (ds.length ? 'Không có tin nào khớp bộ lọc' : 'Chưa có tin kêu cứu nào') : 'Đang chờ dữ liệu…'"
        variant="naked" class="py-10"
      />
      <p class="mt-auto border-t border-default px-5 py-2.5 text-xs text-muted">DTU_DZ_1 · OLP PMNM 2026 · dữ liệu minh họa là dữ liệu giả</p>
    </template>
  </UDashboardPanel>
</template>
