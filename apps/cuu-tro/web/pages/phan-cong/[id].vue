<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Chi tiết phân công một tin (#61): thông tin tin, đội hiện tại + khoảng cách + đếm ngược hạn nhận, bước của
// workflow PhanCongCuuHo, lịch sử giao, nút theo vai. Thao tác gọi /workflow/* qua gateway; API kiểm quyền
// thật (403/409 hiện thành câu tiếng Việt). Sau thao tác: chờ workflow sang bước mới rồi tải lại.
// SĐT người báo chỉ có với vai được Hasura cho đọc (dieu-phoi, cuu-ho), che giữa tới khi bấm "Hiện số".
import {
  BUOC, GHI_CHU_TOI_DA, HANH_DONG, KET_QUA_GIAO, KET_QUA_WF, TRANG_THAI_WF, dangChay, demNguoc, giaoDangCho,
  hanhDongDuoc, khoangCach, tiLeDaQua, type HanhDong, type LienHe, type TinPhanCong, type TrangThaiWf,
} from '~/utils/phan-cong'
import { thongBaoLoi } from '~/utils/workflow-api'
import { MUC_KHAN, TRANG_THAI, cheSdt, maNgan, thoiGianTruoc, type TrangThai } from '~/utils/tin'
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
const dem = computed(() => (cho.value ? demNguoc(cho.value.hanLuc, now.value) : null))

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

const MAU_KQ: Record<string, string> = {
  cho_nhan: 'bg-orange-100 text-cam-600',
  da_nhan: 'bg-emerald-100 text-emerald-800',
  tu_choi: 'bg-red-100 text-red-800',
  qua_han: 'bg-slate-200 text-slate-700',
  huy: 'bg-slate-200 text-slate-700',
}
const gio = (iso: string | null) => (iso
  ? new Date(iso).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  : '')
</script>

<template>
  <UDashboardPanel id="chi-tiet-phan-cong">
    <template #header>
      <UDashboardNavbar>
        <template #title>
          <span class="truncate">Tin <span class="font-mono">{{ maNgan(id) }}</span></span>
        </template>
        <template #right>
          <ThongBaoRealtime v-if="vai === 'dieu-phoi'" />
        </template>
      </UDashboardNavbar>
    </template>
    <template #body>
      <main class="mx-auto w-full max-w-3xl flex-1 space-y-3 pb-28 sm:pb-0">
        <div class="flex flex-wrap items-center gap-2 text-sm">
          <NuxtLink to="/phan-cong" class="min-h-11 rounded-lg px-2 py-2.5 font-bold text-nuoc hover:underline">← {{ vai === 'cuu-ho' ? 'Nhiệm vụ của đội' : 'Hàng đợi phân công' }}</NuxtLink>
          <NuxtLink :to="`/?tin=${id}`" class="ml-auto min-h-11 rounded-lg px-2 py-2.5 font-bold text-nuoc hover:underline">Xem trên bản đồ</NuxtLink>
        </div>

        <p v-if="!vai" class="rounded-lg bg-amber-100 px-4 py-3 text-sm text-amber-900" role="alert">
          Màn phân công dành cho vai Điều phối và Cứu hộ. Tài khoản này không có vai đó.
        </p>
        <p v-else-if="!daTai" class="text-sm text-slate-500" role="status">Đang tải…</p>
        <!-- Thao tác vừa bị từ chối (vd đội cũ nhận muộn) đã có thông báo riêng: không lặp lại lỗi tải -->
        <p v-if="loiTai && ketQua?.ok !== false" class="rounded-lg border-l-4 border-red-600 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">{{ loiTai }}</p>

        <!-- Kết quả thao tác: luôn ở vùng aria-live để trình đọc màn hình đọc lên -->
        <div aria-live="assertive" class="sticky top-2 z-10">
          <p
            v-if="ketQua"
            class="flex items-start gap-2 rounded-lg border-l-4 px-4 py-3 text-sm font-bold shadow"
            :class="ketQua.ok ? 'border-emerald-600 bg-emerald-50 text-emerald-900' : 'border-red-600 bg-red-50 text-red-800'"
          >
            <span aria-hidden="true">{{ ketQua.ok ? '✓' : '!' }}</span>
            <span class="flex-1">{{ ketQua.thongBao }}</span>
            <button type="button" class="px-1 text-lg leading-none opacity-60 hover:opacity-100" aria-label="Ẩn thông báo" @click="ketQua = null">×</button>
          </p>
        </div>

        <template v-if="tin">
          <section class="rounded-xl border-t-4 border-cam bg-white p-4 shadow-sm" aria-labelledby="tieu-de-tin">
            <div class="flex flex-wrap items-center gap-1.5 text-xs">
              <span class="rounded px-1.5 py-0.5 font-bold text-white" :style="{ background: MUC_KHAN[tin.urgency].mau }">{{ MUC_KHAN[tin.urgency].nhan }}</span>
              <span class="rounded bg-slate-200 px-1.5 py-0.5 font-bold text-slate-700">{{ TRANG_THAI[tin.status] }}</span>
              <time class="ml-auto text-slate-500" :datetime="tin.created_at">Tiếp nhận {{ thoiGianTruoc(tin.created_at, now) }}</time>
            </div>
            <h1 id="tieu-de-tin" class="mt-2 text-base font-bold text-navy">Tin <span class="font-mono">{{ maNgan(tin.id) }}</span></h1>
            <p class="mt-1 text-sm font-bold text-chu">{{ tin.description || 'Không có mô tả' }}</p>
            <dl class="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm">
              <dt class="text-slate-500">Địa chỉ</dt><dd>{{ tin.address_text || 'Chưa có' }}</dd>
              <dt class="text-slate-500">Tọa độ</dt><dd class="font-mono text-xs leading-5">{{ tin.location[1].toFixed(5) }}, {{ tin.location[0].toFixed(5) }}</dd>
              <dt class="text-slate-500">Số người</dt><dd>{{ tin.people_count }}</dd>
              <template v-if="tin.reporter_phone !== undefined">
                <dt class="text-slate-500">Người báo</dt>
                <dd>
                  {{ tin.reporter_name || 'Không rõ tên' }} ·
                  <a v-if="hienSo" :href="`tel:${tin.reporter_phone}`" class="font-mono font-bold text-nuoc underline">{{ tin.reporter_phone }}</a>
                  <span v-else class="font-mono">{{ cheSdt(tin.reporter_phone) }}</span>
                  <button v-if="!hienSo" type="button" class="ml-1 font-bold text-nuoc hover:underline" @click="hienSo = true">Hiện số</button>
                </dd>
              </template>
            </dl>
          </section>

          <section class="rounded-xl bg-white p-4 shadow-sm" aria-labelledby="tieu-de-doi">
            <h2 id="tieu-de-doi" class="text-sm font-bold text-navy">Đội và hạn nhận</h2>
            <template v-if="cho">
              <p class="mt-2 text-base font-bold text-chu">{{ cho.doiTen ?? tin.doiTen ?? 'Đội khác' }}</p>
              <p class="text-sm text-slate-600">Cách hiện trường {{ khoangCach(cho.khoangCachM) }} · lần giao {{ cho.lan }}</p>
              <div class="mt-3 flex items-center gap-3">
                <span class="text-sm text-slate-600">Hạn nhận còn</span>
                <span class="rounded-lg px-2.5 py-1 font-mono text-xl font-bold" :class="dem?.gap ? 'bg-red-100 text-red-700' : 'bg-orange-100 text-cam-600'" role="timer" :aria-label="`Hạn nhận còn ${dem?.nhan}`">{{ dem?.nhan }}</span>
              </div>
              <div class="mt-2 h-2 overflow-hidden rounded bg-slate-100" aria-hidden="true">
                <div class="h-full bg-cam" :style="{ width: `${Math.round(tiLeDaQua(cho, now) * 100)}%` }" />
              </div>
            </template>
            <p v-else-if="tin.status === 'dang_cuu'" class="mt-2 text-sm">
              <strong class="text-chu">{{ tin.doiTen ?? wf?.doiTen ?? 'Đội được giao' }}</strong> đã nhận, đang đến / đang cứu.
            </p>
            <p v-else class="mt-2 text-sm text-slate-600">Chưa có đội nào đang được giao.</p>

            <div class="mt-3 border-t border-slate-100 pt-3 text-sm">
              <p v-if="loiWf" class="text-red-700" role="alert">{{ loiWf }}</p>
              <p v-else-if="!wf" class="text-slate-600">Chưa có luồng phân công cho tin này.</p>
              <template v-else>
                <p>
                  <span class="text-slate-500">Luồng phân công: </span>
                  <strong class="text-chu">{{ BUOC[wf.buoc] ?? wf.buoc }}</strong>
                  <span class="ml-1 rounded px-1.5 py-0.5 text-xs font-bold" :class="dangChay(wf) ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-700'">{{ TRANG_THAI_WF[wf.trangThai] ?? wf.trangThai }}</span>
                </p>
                <p v-if="wf.ketQua" class="mt-1"><span class="text-slate-500">Kết quả:</span> {{ KET_QUA_WF[wf.ketQua] ?? wf.ketQua }}<template v-if="wf.nguoiXacNhan"> ({{ wf.nguoiXacNhan }})</template></p>
                <p v-if="wf.daBaoDieuPhoi" class="mt-1 font-bold text-red-700">Đã báo điều phối: cần xử lý tay.</p>
              </template>
            </div>
          </section>

          <!-- Nút theo vai: thanh cố định dưới màn hình điện thoại để bấm bằng một tay -->
          <section
            v-if="nut.length"
            class="fixed inset-x-0 bottom-0 z-20 border-t border-slate-200 bg-white/95 p-3 shadow-[0_-4px_12px_rgba(0,0,0,0.08)] backdrop-blur sm:static sm:rounded-xl sm:border-0 sm:shadow-sm"
            aria-label="Thao tác"
          >
            <form v-if="moForm" class="mx-auto mb-3 max-w-3xl" @submit.prevent="bam(moForm)">
              <label for="ghi-chu" class="text-sm font-bold text-navy">{{ HANH_DONG[moForm].nhanGhiChu }}</label>
              <textarea
                id="ghi-chu" v-model="ghiChu" rows="2" :maxlength="GHI_CHU_TOI_DA"
                class="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-base focus:border-nuoc focus:outline-none focus:ring-2 focus:ring-nuoc/30"
                placeholder="Không bắt buộc"
              />
              <div class="mt-2 flex gap-2">
                <button
                  type="submit" :disabled="!!dangGui"
                  class="min-h-12 flex-1 rounded-lg px-4 font-bold text-white disabled:opacity-60"
                  :class="moForm === 'xac_nhan' ? 'bg-emerald-700 hover:bg-emerald-800' : 'bg-red-700 hover:bg-red-800'"
                >
                  {{ dangGui ? 'Đang gửi…' : `Xác nhận: ${HANH_DONG[moForm].nhan.toLowerCase()}` }}
                </button>
                <button type="button" class="min-h-12 rounded-lg border border-slate-300 px-4 font-bold text-slate-700 hover:bg-slate-100" @click="huyForm">Thôi</button>
              </div>
            </form>
            <div v-else class="mx-auto flex max-w-3xl gap-2">
              <button
                v-for="hd in nut" :key="hd" type="button" :disabled="!!dangGui"
                class="min-h-12 flex-1 rounded-lg px-3 text-base font-bold disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-navy"
                :class="HANH_DONG[hd].chinh ? 'bg-cam text-white hover:bg-cam-600' : 'border-2 border-navy text-navy hover:bg-navy hover:text-white'"
                @click="bam(hd)"
              >
                {{ dangGui === hd ? 'Đang gửi…' : HANH_DONG[hd].nhan }}
              </button>
            </div>
          </section>

          <section class="rounded-xl bg-white p-4 shadow-sm" aria-labelledby="tieu-de-ls">
            <h2 id="tieu-de-ls" class="text-sm font-bold text-navy">Lịch sử giao ({{ tin.giao.length }})</h2>
            <p v-if="tin.giao.length === 0" class="mt-2 text-sm text-slate-500">Chưa giao đội nào.</p>
            <ol v-else class="mt-2 space-y-2">
              <li v-for="g in [...tin.giao].reverse()" :key="`${g.lan}-${g.giaoLuc}`" class="rounded-lg border border-slate-200 px-3 py-2 text-sm">
                <p class="flex flex-wrap items-center gap-2">
                  <span class="font-bold text-chu">Lần {{ g.lan }} · {{ g.doiTen ?? 'Đội khác' }}</span>
                  <span class="rounded px-1.5 py-0.5 text-xs font-bold" :class="MAU_KQ[g.ketQua]">{{ KET_QUA_GIAO[g.ketQua] }}</span>
                </p>
                <p class="text-xs text-slate-600">
                  Cách {{ khoangCach(g.khoangCachM) }} · giao {{ gio(g.giaoLuc) }} · hạn {{ gio(g.hanLuc) }}<template v-if="g.phanHoiLuc"> · trả lời {{ gio(g.phanHoiLuc) }}</template><template v-if="g.nguoi"> · {{ g.nguoi }}</template>
                </p>
                <p v-if="g.ghiChu" class="mt-0.5 text-xs italic text-slate-700">“{{ g.ghiChu }}”</p>
              </li>
            </ol>
            <details v-if="wf?.lichSu.length" class="mt-3 text-xs text-slate-600">
              <summary class="cursor-pointer font-bold text-navy">Nhật ký luồng phân công ({{ wf.lichSu.length }})</summary>
              <ol class="mt-1 space-y-0.5 font-mono">
                <li v-for="(dong, i) in wf.lichSu" :key="i">{{ dong }}</li>
              </ol>
            </details>
          </section>
        </template>
      </main>
    </template>
  </UDashboardPanel>
</template>
