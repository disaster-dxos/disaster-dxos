<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Chi tiết phân công một tin (#61): thông tin tin, đội hiện tại + khoảng cách + đếm ngược hạn nhận, bước của
// workflow PhanCongCuuHo, lịch sử giao, nút theo vai. Thao tác gọi /workflow/* qua gateway; API kiểm quyền
// thật (403/409 hiện thành câu tiếng Việt). Sau thao tác: chờ workflow sang bước mới rồi tải lại.
// SĐT người báo chỉ có với vai được Hasura cho đọc (dieu-phoi, cuu-ho), che giữa tới khi bấm "Hiện số".
import {
  BUOC, GHI_CHU_TOI_DA, HANH_DONG, KET_QUA_GIAO, KET_QUA_WF, TRANG_THAI_WF, dangChay, giaoDangCho,
  hanhDongDuoc, khoangCach, type HanhDong, type LienHe, type TinPhanCong, type TrangThaiWf,
} from '~/utils/phan-cong'
import { thongBaoLoi } from '~/utils/workflow-api'
import { cheSdt, maNgan, thoiGianTruoc, type TrangThai } from '~/utils/tin'
import type { ButtonProps } from '@nuxt/ui'
import type { ComputedRef, Ref } from 'vue'

// vue-tsc của dự án suy ra ref/computed là any: ghi kiểu rõ cho mọi giá trị dùng làm khóa trong template

const route = useRoute()
const id = computed(() => String(route.params.id))
const { vai, taiTin, taiWorkflow, thucHien, choWorkflowDoi } = usePhanCong()
const tinRt = useTinKeuCuu()
const thongBao = useThongBao()
const now = useNow(1_000)

const tin: Ref<(TinPhanCong & Partial<LienHe>) | null> = ref(null)
const wf: Ref<TrangThaiWf | null> = ref(null)
const daTai = ref(false)
const loiTai = ref('')
const loiWf = ref('')
const hienSo = ref(false)
const dangGui: Ref<HanhDong | null> = ref(null)
const moForm: Ref<HanhDong | null> = ref(null)
const ghiChu = ref('')
const ketQua = ref<{ ok: boolean; thongBao: string } | null>(null)

const nut: ComputedRef<HanhDong[]> = computed(() => (tin.value ? hanhDongDuoc(vai.value, tin.value, wf.value) : []))
const cho = computed(() => (tin.value ? giaoDangCho(tin.value) : null))

async function tai() {
  loiTai.value = ''
  try {
    const [t, w] = await Promise.all([taiTin(id.value), taiWorkflow(id.value)])
    tin.value = t
    if (!t) loiTai.value = vai.value === 'cuu-ho'
      ? 'Tin này không (còn) giao cho đội của bạn: có thể đã quá hạn nhận hoặc đã giao cho đội khác.'
      : 'Không tìm thấy tin kêu cứu này.'
    if (w.ok) {
      wf.value = w.data
      loiWf.value = ''
    } else {
      wf.value = null
      loiWf.value = thongBaoLoi(w.status, w.chiTiet, 'xem', vai.value)
    }
  } catch (e) {
    loiTai.value = e instanceof Error ? e.message : String(e)
  } finally {
    daTai.value = true
  }
}

async function bam(hd: HanhDong) {
  if (HANH_DONG[hd].xacNhanTruoc && moForm.value !== hd) {
    moForm.value = hd
    ghiChu.value = ''
    ketQua.value = null
    return
  }
  dangGui.value = hd
  ketQua.value = null
  const truoc = wf.value
  const kq = await thucHien(hd, id.value, ghiChu.value)
  ketQua.value = kq
  if (kq.ok) {
    moForm.value = null
    ghiChu.value = ''
    wf.value = await choWorkflowDoi(id.value, truoc)
  }
  // Thành công hay bị từ chối (409: đã sang bước khác) đều tải lại để thấy trạng thái thật
  await tai()
  dangGui.value = null
}

function huyForm() {
  moForm.value = null
  ghiChu.value = ''
}

// Bản đồ/subscription báo tin này đổi trạng thái → tải lại (vd đội vừa nhận ở máy khác)
const trangThaiRt: ComputedRef<TrangThai | undefined> = computed(() => tinRt.ds.value.find((t) => t.id === id.value)?.status)
watch(trangThaiRt, (s: TrangThai | undefined, cu: TrangThai | undefined) => { if (s && cu && s !== cu && !dangGui.value) void tai() })
let hen: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  if (vai.value === 'dieu-phoi') thongBao.batDau()
  tinRt.batDau()
  void tai()
  hen = setInterval(() => { if (!dangGui.value) void tai() }, 10_000)
})
onBeforeUnmount(() => {
  clearInterval(hen)
  thongBao.dung()
  tinRt.dung()
})
watch(id, () => { tin.value = null; wf.value = null; hienSo.value = false; void tai() })
useHead({ title: () => `Phân công tin ${maNgan(id.value)} · Disaster DX-OS` })

const MAU_KQ = {
  cho_nhan: 'warning',
  da_nhan: 'success',
  tu_choi: 'error',
  qua_han: 'neutral',
  huy: 'neutral',
} as const
// Nút hành động: nút chính màu cam, xác nhận đã cứu màu xanh, từ chối/hủy viền đỏ, còn lại viền navy
const kieuNut = (hd: HanhDong): Pick<ButtonProps, 'color' | 'variant'> => (HANH_DONG[hd].chinh
  ? { color: hd === 'xac_nhan' ? 'success' : 'secondary', variant: 'solid' }
  : { color: hd === 'tu_choi' || hd === 'huy' ? 'error' : 'primary', variant: 'outline' })
const gio = (iso: string | null) => (iso
  ? new Date(iso).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  : '')
</script>

<template>
  <UDashboardPanel id="chi-tiet-phan-cong" :ui="{ body: 'gap-3 sm:gap-4 pb-40 sm:pb-6' }">
    <template #header>
      <UDashboardNavbar :ui="{ right: 'gap-2' }">
        <template #leading>
          <UButton
            to="/phan-cong" icon="i-lucide-arrow-left" color="neutral" variant="ghost" size="lg" square class="-ms-1.5"
            :aria-label="vai === 'cuu-ho' ? 'Về nhiệm vụ của đội' : 'Về hàng đợi phân công'"
          />
        </template>
        <template #title>
          <span class="truncate">Tin <span class="font-mono">{{ maNgan(id) }}</span></span>
        </template>
        <template #right>
          <UButton :to="`/?tin=${id}`" color="neutral" variant="outline" icon="i-lucide-map" class="min-h-10">
            <span class="max-sm:sr-only">Xem trên bản đồ</span>
          </UButton>
          <ThongBaoRealtime v-if="vai === 'dieu-phoi'" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="mx-auto w-full max-w-2xl space-y-3 sm:space-y-4">
        <UAlert
          v-if="!vai" role="alert" color="warning" variant="subtle" icon="i-lucide-shield-alert"
          title="Màn phân công dành cho vai Điều phối và Cứu hộ. Tài khoản này không có vai đó."
        />
        <div v-else-if="!daTai" class="space-y-3" role="status" aria-label="Đang tải">
          <USkeleton class="h-28 w-full" /><USkeleton class="h-48 w-full" />
        </div>
        <!-- Thao tác vừa bị từ chối (vd đội cũ nhận muộn) đã có thông báo riêng: không lặp lại lỗi tải -->
        <UAlert v-if="loiTai && ketQua?.ok !== false" role="alert" color="error" variant="subtle" icon="i-lucide-circle-alert" :title="loiTai" />

        <!-- Kết quả thao tác: luôn ở vùng aria-live để trình đọc màn hình đọc lên -->
        <div aria-live="assertive" class="sticky top-2 z-10 empty:hidden">
          <UAlert
            v-if="ketQua"
            :color="ketQua.ok ? 'success' : 'error'" variant="solid" class="shadow-lg"
            :icon="ketQua.ok ? 'i-lucide-circle-check' : 'i-lucide-circle-alert'"
            :title="ketQua.thongBao" close
            @update:open="ketQua = null"
          />
        </div>

        <template v-if="tin">
          <!-- Hạn nhận: thứ đội cần thấy đầu tiên -->
          <section v-if="cho" aria-labelledby="tieu-de-doi" class="space-y-2">
            <h2 id="tieu-de-doi" class="sr-only">Đội và hạn nhận</h2>
            <DongHoHanNhan :giao="cho" :now="now" lon />
            <p class="flex flex-wrap items-baseline gap-x-2 px-1 text-base">
              <strong class="text-highlighted">{{ cho.doiTen ?? tin.doiTen ?? 'Đội khác' }}</strong>
              <span class="text-muted">cách hiện trường {{ khoangCach(cho.khoangCachM) }} · lần giao {{ cho.lan }}</span>
            </p>
          </section>

          <UCard :ui="{ body: 'p-4 sm:p-5' }" aria-labelledby="tieu-de-tin" as="section">
            <div class="flex flex-wrap items-center gap-1.5">
              <NhanMucKhan :muc="tin.urgency" size="lg" />
              <NhanTrangThai :tt="tin.status" size="lg" />
            </div>
            <h1 id="tieu-de-tin" class="mt-3 text-xl font-bold leading-snug text-highlighted">{{ tin.description || 'Không có mô tả' }}</h1>
            <p class="mt-1 text-sm text-muted">
              Tin <span class="font-mono">{{ maNgan(tin.id) }}</span> · tiếp nhận <time :datetime="tin.created_at">{{ thoiGianTruoc(tin.created_at, now) }}</time>
            </p>
            <dl class="mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2.5 border-t border-default pt-4 text-base">
              <dt class="flex items-center gap-1.5 text-muted"><UIcon name="i-lucide-map-pin" class="size-4" />Địa chỉ</dt><dd class="font-medium">{{ tin.address_text || 'Chưa có' }}</dd>
              <dt class="flex items-center gap-1.5 text-muted"><UIcon name="i-lucide-users" class="size-4" />Số người</dt><dd class="so font-semibold">{{ tin.people_count }}</dd>
              <dt class="flex items-center gap-1.5 text-muted"><UIcon name="i-lucide-locate" class="size-4" />Tọa độ</dt><dd class="so font-mono text-sm leading-6">{{ tin.location[1].toFixed(5) }}, {{ tin.location[0].toFixed(5) }}</dd>
              <template v-if="tin.reporter_phone !== undefined">
                <dt class="flex items-center gap-1.5 text-muted"><UIcon name="i-lucide-user" class="size-4" />Người báo</dt><dd class="font-medium">{{ tin.reporter_name || 'Không rõ tên' }}</dd>
              </template>
            </dl>
            <div v-if="tin.reporter_phone !== undefined" class="mt-4">
              <UButton
                v-if="hienSo" :to="`tel:${tin.reporter_phone}`" color="info" variant="soft" size="xl" block
                icon="i-lucide-phone" class="so min-h-12 font-mono text-lg font-semibold"
              >
                Gọi {{ tin.reporter_phone }}
              </UButton>
              <UButton v-else color="info" variant="outline" size="xl" block icon="i-lucide-eye" class="min-h-12" @click="hienSo = true">
                Hiện số <span class="so font-mono">{{ cheSdt(tin.reporter_phone) }}</span>
              </UButton>
            </div>
          </UCard>

          <UCard :ui="{ body: 'p-4 sm:p-5' }" as="section" aria-labelledby="tieu-de-luong">
            <h2 id="tieu-de-luong" class="text-sm font-semibold text-muted">Luồng phân công</h2>
            <p v-if="!cho && tin.status === 'dang_cuu'" class="mt-2 text-base">
              <strong class="text-highlighted">{{ tin.doiTen ?? wf?.doiTen ?? 'Đội được giao' }}</strong> đã nhận, đang đến / đang cứu.
            </p>
            <p v-else-if="!cho" class="mt-2 text-base text-muted">Chưa có đội nào đang được giao.</p>
            <UAlert v-if="loiWf" role="alert" class="mt-3" color="error" variant="subtle" icon="i-lucide-circle-alert" :title="loiWf" />
            <p v-else-if="!wf" class="mt-2 text-base text-muted">Chưa có luồng phân công cho tin này.</p>
            <template v-else>
              <p class="mt-2 flex flex-wrap items-center gap-2 text-base">
                <strong class="text-highlighted">{{ BUOC[wf.buoc] ?? wf.buoc }}</strong>
                <UBadge :color="dangChay(wf) ? 'success' : 'neutral'" variant="subtle">{{ TRANG_THAI_WF[wf.trangThai] ?? wf.trangThai }}</UBadge>
              </p>
              <p v-if="wf.ketQua" class="mt-1 text-sm"><span class="text-muted">Kết quả:</span> {{ KET_QUA_WF[wf.ketQua] ?? wf.ketQua }}<template v-if="wf.nguoiXacNhan"> ({{ wf.nguoiXacNhan }})</template></p>
              <UAlert v-if="wf.daBaoDieuPhoi" class="mt-3" color="error" variant="subtle" icon="i-lucide-siren" title="Đã báo điều phối: cần xử lý tay." />
            </template>
          </UCard>

          <UCard :ui="{ body: 'p-4 sm:p-5' }" as="section" aria-labelledby="tieu-de-ls">
            <h2 id="tieu-de-ls" class="text-sm font-semibold text-muted">Lịch sử giao ({{ tin.giao.length }})</h2>
            <p v-if="tin.giao.length === 0" class="mt-2 text-base text-muted">Chưa giao đội nào.</p>
            <ol v-else class="mt-3 space-y-3">
              <li v-for="g in [...tin.giao].reverse()" :key="`${g.lan}-${g.giaoLuc}`" class="rounded-md bg-elevated/50 px-3 py-2.5 ring ring-inset ring-default">
                <p class="flex flex-wrap items-center gap-2">
                  <span class="font-semibold text-highlighted">Lần {{ g.lan }} · {{ g.doiTen ?? 'Đội khác' }}</span>
                  <UBadge :color="MAU_KQ[g.ketQua]" variant="subtle">{{ KET_QUA_GIAO[g.ketQua] }}</UBadge>
                </p>
                <p class="so mt-0.5 text-sm text-muted">
                  Cách {{ khoangCach(g.khoangCachM) }} · giao {{ gio(g.giaoLuc) }} · hạn {{ gio(g.hanLuc) }}<template v-if="g.phanHoiLuc"> · trả lời {{ gio(g.phanHoiLuc) }}</template><template v-if="g.nguoi"> · {{ g.nguoi }}</template>
                </p>
                <p v-if="g.ghiChu" class="mt-1 text-sm text-default">“{{ g.ghiChu }}”</p>
              </li>
            </ol>
            <UCollapsible v-if="wf?.lichSu.length" class="mt-3">
              <UButton color="neutral" variant="link" trailing-icon="i-lucide-chevron-down" class="px-0 font-semibold">
                Nhật ký luồng phân công ({{ wf.lichSu.length }})
              </UButton>
              <template #content>
                <ol class="mt-1 space-y-0.5 font-mono text-xs text-muted">
                  <li v-for="(dong, i) in wf.lichSu" :key="i">{{ dong }}</li>
                </ol>
              </template>
            </UCollapsible>
          </UCard>

          <!-- Nút theo vai: thanh cố định dưới màn hình điện thoại để bấm bằng một tay -->
          <section
            v-if="nut.length"
            class="fixed inset-x-0 bottom-0 z-20 border-t border-default bg-default/95 p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] shadow-[0_-6px_16px_rgb(11_31_54/0.10)] backdrop-blur sm:static sm:rounded-lg sm:p-4 sm:shadow-none sm:ring sm:ring-default"
            aria-label="Thao tác"
          >
            <form v-if="moForm" class="mx-auto max-w-2xl space-y-3" @submit.prevent="bam(moForm)">
              <UFormField :label="HANH_DONG[moForm].nhanGhiChu" name="ghi-chu" :ui="{ label: 'text-base font-semibold' }">
                <UTextarea id="ghi-chu" v-model="ghiChu" :rows="2" :maxlength="GHI_CHU_TOI_DA" placeholder="Không bắt buộc" size="xl" class="w-full" />
              </UFormField>
              <div class="flex gap-2">
                <UButton
                  type="submit" size="xl" block :loading="!!dangGui" :disabled="!!dangGui"
                  :color="moForm === 'xac_nhan' ? 'success' : 'error'" class="min-h-14 flex-1 text-lg font-semibold"
                >
                  {{ dangGui ? 'Đang gửi…' : `Xác nhận: ${HANH_DONG[moForm].nhan.toLowerCase()}` }}
                </UButton>
                <UButton type="button" size="xl" color="neutral" variant="outline" class="min-h-14 text-lg" @click="huyForm">Thôi</UButton>
              </div>
            </form>
            <div v-else class="mx-auto flex max-w-2xl gap-2">
              <UButton
                v-for="hd in nut" :key="hd" size="xl" block :disabled="!!dangGui" :loading="dangGui === hd"
                v-bind="kieuNut(hd)" class="min-h-14 flex-1 text-lg font-semibold" :class="HANH_DONG[hd].chinh ? '' : 'ring-2 ring-current'"
                @click="bam(hd)"
              >
                {{ dangGui === hd ? 'Đang gửi…' : HANH_DONG[hd].nhan }}
              </UButton>
            </div>
          </section>
        </template>
      </div>
    </template>
  </UDashboardPanel>
</template>
