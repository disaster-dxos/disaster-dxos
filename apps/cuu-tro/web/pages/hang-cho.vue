<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Hàng chờ duyệt tin do AI bóc tách (#104, Human-in-the-loop), chỉ vai Điều phối.
//  - Dán tin SMS/Zalo → POST /workflow/ai/boc-tach {"vao_hang_cho": true}: API bóc tách và lưu đề xuất, chưa tạo tin.
//  - Chọn một tin: văn bản gốc nằm cạnh form đề xuất; trường đã sửa được đánh dấu kèm giá trị AI; tin thiếu tọa
//    độ thì bấm bản đồ đặt ghim. "Duyệt và tạo tin" → POST /workflow/hang-cho/{id}/duyet (API kiểm lại bằng
//    Poka-yoke của /keu-cuu, chặn trùng, lưu vết người duyệt + trường sửa). "Hủy tin" → không tạo tin.
//  - Tab Đã duyệt / Đã hủy: xem lại vết (ai duyệt, lúc nào, sửa gì so với AI).
// Hàng chờ tải lại mỗi 15 giây (tình nguyện viên có thể chuyển tin vào từ điện thoại) và sau mỗi thao tác.
import {
  DS_NGUON_VAN_BAN, LY_DO_HUY_NHANH, LY_DO_TOI_DA, NGUON_VAN_BAN, NHAN_TRUONG, NHU_CAU, TRANG_THAI_HANG_CHO,
  VAN_BAN_TOI_DA, bodyTuForm, formTuBody, hienGiaTri, loiTheoTruong, oToaDo, phanTichLoi, sapXepHangCho, toaDoForm,
  truongDaSua, MO_TA_TOI_DA, type FormTin, type LoiTruong, type MucHangCho, type NguonVanBan, type TrangThaiHangCho,
  type TruongTin,
} from '~/utils/hang-cho'
import { MUC_KHAN, NGUON, maNgan, thoiGianTruoc, type MucKhan } from '~/utils/tin'
import type { ComputedRef, Ref } from 'vue'

const route = useRoute()
const router = useRouter()
const { laDieuPhoi, taiHang, bocTach, duyet, huy } = useHangCho()
const now = useNow(30_000)

const tab: Ref<TrangThaiHangCho> = ref('cho_duyet')
const ds: Ref<MucHangCho[]> = ref([])
const soChoDuyet = ref(0)
const dangTai = ref(false)
const daTai = ref(false)
const loiTai = ref('')
const chonId: Ref<string | null> = ref(typeof route.query.muc === 'string' ? route.query.muc : null)
const dsSapXep: ComputedRef<MucHangCho[]> = computed(() => sapXepHangCho(ds.value))
const muc: ComputedRef<MucHangCho | null> = computed(() => ds.value.find((m) => m.id === chonId.value) ?? null)

// ---------- Dán tin mới ----------
const vanBan = ref('')
const nguon: Ref<NguonVanBan> = ref('zalo')
const dangBocTach = ref(false)
const loiBocTach = ref('')
const DS_NGUON = DS_NGUON_VAN_BAN.map((k) => ({ label: NGUON_VAN_BAN[k], value: k }))

// ---------- Form duyệt ----------
const goc: Ref<FormTin> = ref(formTuBody({}))
const form: Ref<FormTin> = ref(formTuBody({}))
const formCua: Ref<string | null> = ref(null)
const loiForm: Ref<Record<string, string>> = ref({})
// Lỗi của một trường chỉ hiện khi trường chưa đổi kể từ lúc báo lỗi
const formLucLoi: Ref<FormTin | null> = ref(null)
const dangGui: Ref<'duyet' | 'huy' | null> = ref(null)
const moHuy = ref(false)
const lyDo = ref('')
const ketQua: Ref<{ ok: boolean; thongBao: string; incidentId?: string | null } | null> = ref(null)

const daSua: ComputedRef<Set<TruongTin>> = computed(() => new Set(truongDaSua(form.value, goc.value)))
const diem: ComputedRef<[number, number] | null> = computed(() => toaDoForm(form.value))
const DS_MUC: Array<{ label: string; value: string }> = (Object.keys(MUC_KHAN) as MucKhan[]).map((k) => ({ label: MUC_KHAN[k].nhan, value: k }))
const DS_NGUON_TIN = Object.entries(NGUON).map(([value, label]) => ({ label, value }))

function loiCua(k: TruongTin): string | undefined {
  const l = loiForm.value[k]
  if (!l) return undefined
  return formLucLoi.value && formLucLoi.value[k] !== form.value[k] ? undefined : l
}

function datLoi(loi: LoiTruong[]) {
  loiForm.value = loiTheoTruong(loi)
  formLucLoi.value = { ...form.value }
}

function napForm(m: MucHangCho) {
  goc.value = formTuBody(m.deXuat)
  form.value = { ...goc.value }
  formCua.value = m.id
  moHuy.value = false
  lyDo.value = ''
  // Lỗi Poka-yoke lúc bóc tách (vd thiếu tọa độ) hiện ngay dưới trường
  datLoi(m.loi)
}

watch(muc, (m) => {
  if (m && m.id !== formCua.value) napForm(m)
}, { immediate: true })

watch(chonId, (id) => {
  void router.replace({ query: id ? { muc: id } : {} })
})

async function tai() {
  if (!laDieuPhoi.value || dangTai.value) return
  dangTai.value = true
  try {
    const kq = await taiHang(tab.value)
    ds.value = kq.ds
    soChoDuyet.value = kq.soChoDuyet
    loiTai.value = ''
    if (!chonId.value || !ds.value.some((m) => m.id === chonId.value)) {
      chonId.value = sapXepHangCho(ds.value)[0]?.id ?? null
    }
  } catch (e) {
    loiTai.value = e instanceof Error ? e.message : String(e)
  } finally {
    dangTai.value = false
    daTai.value = true
  }
}

async function doiTab(t: TrangThaiHangCho) {
  if (tab.value === t) return
  tab.value = t
  chonId.value = null
  ketQua.value = null
  ds.value = []
  await tai()
}

async function guiBocTach() {
  loiBocTach.value = ''
  if (!vanBan.value.trim()) {
    loiBocTach.value = 'Dán nội dung tin nhắn kêu cứu vào ô trên.'
    return
  }
  dangBocTach.value = true
  try {
    const kq = await bocTach(vanBan.value, nguon.value)
    if (!kq.ok) {
      loiBocTach.value = phanTichLoi(kq, 'boc_tach').thongBao
      return
    }
    vanBan.value = ''
    tab.value = 'cho_duyet'
    chonId.value = kq.data.hang_cho.id
    ketQua.value = null
    await tai()
  } finally {
    dangBocTach.value = false
  }
}

function chonViTri(ll: { lng: number; lat: number }) {
  const o = oToaDo(ll)
  form.value = { ...form.value, lat: o.lat, lon: o.lon }
}

function khoiPhuc() {
  form.value = { ...goc.value }
}

async function sauXuLy(thongBao: string, incidentId: string | null) {
  const id = chonId.value
  const conLai = sapXepHangCho(ds.value).filter((m) => m.id !== id)
  chonId.value = conLai[0]?.id ?? null
  ketQua.value = { ok: true, thongBao, incidentId }
  await tai()
}

async function guiDuyet() {
  const m = muc.value
  if (!m || dangGui.value) return
  ketQua.value = null
  const { body, loi } = bodyTuForm(form.value)
  if (loi.length) {
    datLoi(loi)
    ketQua.value = { ok: false, thongBao: 'Chưa duyệt được: sửa các trường được đánh dấu.' }
    return
  }
  dangGui.value = 'duyet'
  try {
    const kq = await duyet(m.id, body)
    if (kq.ok) {
      const sua = kq.data.truong_da_sua.length ? `, sửa ${kq.data.truong_da_sua.length} trường so với AI` : ', giữ nguyên đề xuất của AI'
      await sauXuLy(`Đã tạo tin kêu cứu ${maNgan(kq.data.incident_id)}${sua}. Tin tự vào hàng phân công.`, kq.data.incident_id)
      return
    }
    const p = phanTichLoi(kq, 'duyet')
    if (p.loi.length) datLoi(p.loi)
    ketQua.value = { ok: false, thongBao: p.thongBao, incidentId: p.tinTrungId }
    if (p.daXuLy) await tai()
  } finally {
    dangGui.value = null
  }
}

async function guiHuy() {
  const m = muc.value
  if (!m || dangGui.value) return
  dangGui.value = 'huy'
  try {
    const kq = await huy(m.id, lyDo.value)
    if (kq.ok) {
      await sauXuLy('Đã hủy tin trong hàng chờ, không tạo tin kêu cứu.', null)
      return
    }
    const p = phanTichLoi(kq, 'huy')
    ketQua.value = { ok: false, thongBao: p.thongBao }
    if (p.daXuLy) await tai()
  } finally {
    dangGui.value = null
  }
}

let hen: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  if (!laDieuPhoi.value) return
  void tai()
  hen = setInterval(() => { void tai() }, 15_000)
})
onBeforeUnmount(() => clearInterval(hen))
useHead({ title: 'Duyệt tin AI · Disaster DX-OS' })

const TAB: TrangThaiHangCho[] = ['cho_duyet', 'da_duyet', 'da_huy']
const TRUONG_FORM: Array<{ k: TruongTin; kieu: 'input' | 'textarea' | 'muc' | 'nguon'; cot?: string; goiY?: string; toiDa?: number }> = [
  { k: 'reporter_phone', kieu: 'input', goiY: '09xx xxx xxx' },
  { k: 'reporter_name', kieu: 'input', goiY: 'Không bắt buộc', toiDa: 100 },
  { k: 'lat', kieu: 'input', goiY: 'vd 16.0712' },
  { k: 'lon', kieu: 'input', goiY: 'vd 108.1503' },
  { k: 'people_count', kieu: 'input', goiY: '1' },
  { k: 'urgency', kieu: 'muc' },
  { k: 'address_text', kieu: 'input', cot: 'sm:col-span-2', goiY: 'Thôn, xã…', toiDa: 300 },
  { k: 'description', kieu: 'textarea', cot: 'sm:col-span-2', toiDa: MO_TA_TOI_DA },
  { k: 'source', kieu: 'nguon', cot: 'sm:col-span-2' },
]
</script>

<template>
  <UDashboardPanel id="hang-cho" :ui="{ body: 'gap-4' }">
    <template #header>
      <UDashboardNavbar title="Duyệt tin AI" :ui="{ right: 'gap-2' }">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #trailing>
          <UBadge :color="soChoDuyet ? 'warning' : 'neutral'" variant="subtle" class="so">{{ soChoDuyet }} chờ duyệt</UBadge>
        </template>
        <template #right>
          <UButton
            color="neutral" variant="outline" icon="i-lucide-refresh-cw" class="min-h-10"
            :loading="dangTai" :disabled="dangTai || !laDieuPhoi" @click="tai"
          >
            <span class="max-sm:sr-only">{{ dangTai ? 'Đang tải…' : 'Tải lại' }}</span>
          </UButton>
          <ThongBaoRealtime v-if="laDieuPhoi" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <UAlert
        v-if="!laDieuPhoi" role="alert" color="warning" variant="subtle" icon="i-lucide-shield-alert"
        title="Hàng chờ duyệt tin AI dành cho vai Điều phối. Tài khoản này không có vai đó."
      />
      <template v-else>
        <!-- Dán tin mới -->
        <UCard :ui="{ body: 'p-4 sm:p-4' }">
          <form class="grid gap-3 lg:grid-cols-[1fr_auto]" @submit.prevent="guiBocTach">
            <UFormField
              label="Dán tin nhắn kêu cứu (SMS, Zalo, ghi lại cuộc gọi)" name="van-ban" :error="loiBocTach || undefined"
              :help="`AI đề xuất các trường; tin chỉ được tạo khi bạn duyệt. Tối đa ${VAN_BAN_TOI_DA} ký tự.`"
              :ui="{ label: 'text-sm font-semibold' }"
            >
              <UTextarea
                id="van-ban" v-model="vanBan" :rows="3" :maxlength="VAN_BAN_TOI_DA" autoresize class="w-full"
                placeholder="vd: Cuu voi, nha toi o thon 3 xa Hoa Phu ngap toi mai, 4 nguoi. SDT 0905 xxx xxx"
              />
            </UFormField>
            <div class="flex flex-col justify-end gap-2 lg:w-56">
              <UFormField label="Nguồn" name="nguon" :ui="{ label: 'text-sm font-semibold' }">
                <USelect id="nguon" v-model="nguon" :items="DS_NGUON" class="w-full" />
              </UFormField>
              <UButton type="submit" icon="i-lucide-sparkles" block class="min-h-10" :loading="dangBocTach" :disabled="dangBocTach">
                {{ dangBocTach ? 'Đang bóc tách…' : 'Bóc tách bằng AI' }}
              </UButton>
            </div>
          </form>
        </UCard>

        <div class="flex flex-wrap items-center gap-2" role="group" aria-label="Lọc hàng chờ theo trạng thái">
          <UButton
            v-for="t in TAB" :key="t" :color="tab === t ? 'primary' : 'neutral'" :variant="tab === t ? 'solid' : 'outline'"
            class="min-h-10" :aria-pressed="tab === t" @click="doiTab(t)"
          >
            {{ TRANG_THAI_HANG_CHO[t] }}
            <UBadge v-if="t === 'cho_duyet'" :color="tab === t ? 'neutral' : 'warning'" variant="subtle" class="so rounded-full">{{ soChoDuyet }}</UBadge>
          </UButton>
        </div>

        <UAlert v-if="loiTai" role="alert" color="error" variant="subtle" icon="i-lucide-circle-alert" title="Không tải được hàng chờ" :description="loiTai" />
        <UAlert
          v-if="ketQua" role="status" :color="ketQua.ok ? 'success' : 'error'" variant="subtle"
          :icon="ketQua.ok ? 'i-lucide-circle-check' : 'i-lucide-circle-alert'" :title="ketQua.thongBao"
          :actions="ketQua.incidentId ? [{ label: ketQua.ok ? 'Xem trên bản đồ' : 'Xem tin đang mở', to: `/?tin=${ketQua.incidentId}`, color: 'neutral', variant: 'outline' }] : undefined"
          close @update:open="ketQua = null"
        />
        <UEmpty
          v-if="daTai && !loiTai && ds.length === 0" icon="i-lucide-inbox"
          :title="tab === 'cho_duyet' ? 'Không có tin nào chờ duyệt.' : `Chưa có tin nào ${TRANG_THAI_HANG_CHO[tab].toLowerCase()}.`"
        />

        <div v-if="ds.length" class="grid min-h-0 flex-1 gap-4 lg:grid-cols-[20rem_1fr]">
          <!-- Danh sách -->
          <ul class="space-y-2 lg:max-h-[calc(100dvh-20rem)] lg:overflow-y-auto lg:pe-1" aria-label="Tin trong hàng chờ">
            <li v-for="m in dsSapXep" :key="m.id">
              <button
                type="button"
                class="w-full rounded-lg p-3 text-start ring ring-inset transition-colors focus-visible:outline-2 focus-visible:outline-primary"
                :class="m.id === chonId ? 'bg-primary/10 ring-primary' : 'bg-default ring-default hover:bg-elevated'"
                :aria-current="m.id === chonId ? 'true' : undefined" @click="chonId = m.id"
              >
                <span class="flex items-center gap-2">
                  <NhanMucKhan :muc="m.urgency" size="sm" />
                  <UBadge color="neutral" variant="subtle" size="sm">{{ NGUON_VAN_BAN[m.nguon] }}</UBadge>
                  <span class="ms-auto text-xs text-muted">{{ thoiGianTruoc(m.duyetLuc ?? m.taoLuc, now) }}</span>
                </span>
                <span class="mt-2 line-clamp-2 block text-sm text-highlighted">{{ m.vanBan }}</span>
                <span v-if="m.trangThai === 'cho_duyet'" class="mt-2 flex flex-wrap gap-1.5 text-xs">
                  <span v-if="m.tinTrung" class="inline-flex items-center gap-1 text-error"><UIcon name="i-lucide-copy" class="size-3.5" />Có thể trùng</span>
                  <span v-else-if="!m.hopLe" class="inline-flex items-center gap-1 text-warning"><UIcon name="i-lucide-map-pin-off" class="size-3.5" />Cần bổ sung</span>
                  <span v-else class="inline-flex items-center gap-1 text-success"><UIcon name="i-lucide-check" class="size-3.5" />Đủ thông tin</span>
                  <span v-if="m.ai.duPhong" class="inline-flex items-center gap-1 text-muted"><UIcon name="i-lucide-triangle-alert" class="size-3.5" />Bộ luật dự phòng</span>
                </span>
                <span v-else class="mt-2 block text-xs text-muted">
                  {{ m.trangThai === 'da_duyet' ? 'Duyệt' : 'Hủy' }} bởi {{ m.nguoiDuyet ?? '—' }}
                </span>
              </button>
            </li>
          </ul>

          <!-- Chi tiết -->
          <section v-if="muc" class="min-w-0 space-y-4" aria-labelledby="muc-tieu-de">
            <header class="flex flex-wrap items-center gap-2">
              <h2 id="muc-tieu-de" class="text-lg font-semibold text-highlighted">Tin {{ maNgan(muc.id) }}</h2>
              <UBadge color="neutral" variant="subtle">{{ NGUON_VAN_BAN[muc.nguon] }}</UBadge>
              <span class="text-sm text-muted">
                gửi {{ thoiGianTruoc(muc.taoLuc, now) }} bởi {{ muc.nguoiGui ?? '—' }}{{ muc.vaiGui === 'tinh-nguyen' ? ' (tình nguyện viên)' : '' }}
              </span>
              <span class="ms-auto text-xs text-muted">
                AI: {{ muc.ai.moHinh ?? muc.ai.nhaCungCap }} · {{ (muc.ai.thoiGianMs / 1000).toFixed(1) }} s
              </span>
            </header>

            <div class="grid gap-4 xl:grid-cols-2">
              <!-- Văn bản gốc -->
              <div class="space-y-3">
                <UCard :ui="{ header: 'p-3 sm:p-3', body: 'p-3 sm:p-3' }">
                  <template #header>
                    <h3 class="flex items-center gap-2 text-sm font-semibold"><UIcon name="i-lucide-message-square-text" class="size-4" />Văn bản gốc</h3>
                  </template>
                  <p class="whitespace-pre-wrap break-words text-base leading-relaxed text-highlighted">{{ muc.vanBan }}</p>
                </UCard>
                <div v-if="muc.nhuCau.length" class="flex flex-wrap items-center gap-1.5">
                  <span class="text-sm text-muted">Nhu cầu:</span>
                  <UBadge v-for="n in muc.nhuCau" :key="n" color="info" variant="subtle">{{ NHU_CAU[n] ?? n }}</UBadge>
                </div>
                <UAlert
                  v-if="muc.ai.duPhong" color="warning" variant="subtle" icon="i-lucide-triangle-alert"
                  title="Mô hình AI không phản hồi kịp: đề xuất do bộ luật dự phòng tạo, cần soát kỹ."
                />
                <UAlert
                  v-for="(c, i) in muc.canhBao.filter((x) => !muc!.ai.duPhong || !x.startsWith('Mô hình AI'))" :key="i"
                  color="neutral" variant="subtle" icon="i-lucide-info" :title="c"
                />
                <UAlert
                  v-if="muc.tinTrung && muc.trangThai === 'cho_duyet'" color="error" variant="subtle" icon="i-lucide-copy"
                  title="Có thể trùng tin đang mở" :description="muc.tinTrung.thong_bao"
                  :actions="[{ label: 'Xem tin đang mở', to: `/?tin=${muc.tinTrung.incident_id}`, color: 'neutral', variant: 'outline' }]"
                />
                <!-- Vị trí: cạnh văn bản gốc để người duyệt đối chiếu địa chỉ trong tin với điểm trên bản đồ -->
                <div v-if="muc.trangThai === 'cho_duyet'" class="space-y-1.5">
                  <h3 class="flex items-center gap-2 text-sm font-semibold">
                    <UIcon name="i-lucide-map-pin" class="size-4" />Vị trí
                    <UBadge v-if="!diem" color="warning" variant="subtle" size="sm">chưa có, bấm bản đồ để chọn</UBadge>
                  </h3>
                  <div class="h-72">
                    <ChonViTri :diem="diem" @chon="chonViTri" />
                  </div>
                  <p class="text-xs text-muted">Bấm vào bản đồ hoặc kéo ghim cam để đặt vị trí. AI không đoán tọa độ từ địa chỉ: tin không ghi tọa độ thì người duyệt chọn.</p>
                </div>
              </div>

              <!-- Chờ duyệt: form sửa đề xuất -->
              <form v-if="muc.trangThai === 'cho_duyet'" class="space-y-3" novalidate @submit.prevent="guiDuyet">
                <div class="flex min-h-8 flex-wrap items-center gap-2">
                  <h3 class="text-sm font-semibold">Đề xuất của AI, sửa trước khi duyệt</h3>
                  <UBadge v-if="daSua.size" color="warning" variant="subtle" class="so whitespace-nowrap">đã sửa {{ daSua.size }}</UBadge>
                  <UButton v-if="daSua.size" size="sm" color="neutral" variant="ghost" icon="i-lucide-undo-2" class="ms-auto" @click="khoiPhuc">
                    Khôi phục
                  </UButton>
                </div>
                <div class="grid gap-3 sm:grid-cols-2">
                  <UFormField
                    v-for="f in TRUONG_FORM" :key="f.k" :name="f.k" :class="f.cot" :error="loiCua(f.k)"
                    :ui="{ label: 'text-sm font-medium' }"
                  >
                    <template #label>
                      {{ NHAN_TRUONG[f.k] }}
                      <UBadge v-if="daSua.has(f.k)" color="warning" variant="subtle" size="sm" class="ms-1">đã sửa</UBadge>
                    </template>
                    <template v-if="daSua.has(f.k)" #help>
                      AI đề xuất: {{ f.k === 'urgency' ? MUC_KHAN[goc.urgency as MucKhan]?.nhan ?? goc.urgency : (f.k === 'source' ? NGUON[goc.source] ?? hienGiaTri(goc.source) : hienGiaTri(goc[f.k])) }}
                    </template>
                    <UTextarea v-if="f.kieu === 'textarea'" :id="`f-${f.k}`" v-model="form[f.k]" :rows="3" :maxlength="f.toiDa" autoresize class="w-full" />
                    <USelect v-else-if="f.kieu === 'muc'" :id="`f-${f.k}`" v-model="form.urgency" :items="DS_MUC" class="w-full" />
                    <USelect v-else-if="f.kieu === 'nguon'" :id="`f-${f.k}`" v-model="form.source" :items="DS_NGUON_TIN" class="w-full" />
                    <UInput
                      v-else :id="`f-${f.k}`" v-model="form[f.k]" :placeholder="f.goiY" :maxlength="f.toiDa" class="w-full"
                      :inputmode="f.k === 'lat' || f.k === 'lon' ? 'decimal' : (f.k === 'people_count' || f.k === 'reporter_phone' ? 'numeric' : undefined)"
                      :autocomplete="'off'"
                    />
                  </UFormField>
                </div>
                <UAlert v-if="loiForm.body && loiCua('description') === undefined" color="error" variant="subtle" icon="i-lucide-circle-alert" :title="loiForm.body" />

                <div class="flex flex-wrap gap-2 border-t border-default pt-3">
                  <UButton type="submit" size="lg" icon="i-lucide-check" class="min-h-11" :loading="dangGui === 'duyet'" :disabled="!!dangGui">
                    Duyệt và tạo tin
                  </UButton>
                  <UButton size="lg" color="error" variant="outline" icon="i-lucide-x" class="min-h-11" :disabled="!!dangGui" @click="moHuy = !moHuy">
                    Hủy tin…
                  </UButton>
                </div>
                <UCard v-if="moHuy" :ui="{ body: 'p-3 sm:p-3 space-y-2' }">
                  <UFormField label="Lý do hủy (lưu vào vết duyệt)" name="ly-do" :ui="{ label: 'text-sm font-semibold' }">
                    <UTextarea id="ly-do" v-model="lyDo" :rows="2" :maxlength="LY_DO_TOI_DA" class="w-full" />
                  </UFormField>
                  <div class="flex flex-wrap gap-1.5">
                    <UButton v-for="l in LY_DO_HUY_NHANH" :key="l" size="xs" color="neutral" variant="subtle" @click="lyDo = l">{{ l }}</UButton>
                  </div>
                  <UButton color="error" icon="i-lucide-trash-2" :loading="dangGui === 'huy'" :disabled="!!dangGui" @click="guiHuy">
                    Xác nhận hủy, không tạo tin
                  </UButton>
                </UCard>
              </form>

              <!-- Đã xử lý: vết duyệt -->
              <UCard v-else :ui="{ header: 'p-3 sm:p-3', body: 'p-3 sm:p-3 space-y-3' }">
                <template #header>
                  <h3 class="flex items-center gap-2 text-sm font-semibold">
                    <UIcon :name="muc.trangThai === 'da_duyet' ? 'i-lucide-badge-check' : 'i-lucide-ban'" class="size-4" />
                    Vết duyệt
                  </h3>
                </template>
                <dl class="grid grid-cols-[8rem_1fr] gap-x-3 gap-y-1.5 text-sm">
                  <dt class="text-muted">Kết quả</dt>
                  <dd class="font-semibold">{{ TRANG_THAI_HANG_CHO[muc.trangThai] }}</dd>
                  <dt class="text-muted">Người duyệt</dt>
                  <dd>{{ muc.nguoiDuyet ?? '—' }}</dd>
                  <dt class="text-muted">Thời điểm</dt>
                  <dd>{{ muc.duyetLuc ? new Date(muc.duyetLuc).toLocaleString('vi-VN') : '—' }}</dd>
                  <template v-if="muc.incidentId">
                    <dt class="text-muted">Tin đã tạo</dt>
                    <dd><NuxtLink :to="`/?tin=${muc.incidentId}`" class="font-mono text-primary underline">{{ maNgan(muc.incidentId) }}</NuxtLink></dd>
                  </template>
                  <template v-if="muc.trangThai === 'da_huy'">
                    <dt class="text-muted">Lý do</dt>
                    <dd>{{ muc.lyDoHuy ?? '(không ghi)' }}</dd>
                  </template>
                </dl>
                <div v-if="muc.truongDaSua">
                  <p v-if="Object.keys(muc.truongDaSua).length === 0" class="text-sm text-muted">Duyệt nguyên đề xuất của AI, không sửa trường nào.</p>
                  <table v-else class="w-full text-sm">
                    <caption class="mb-1 text-start text-sm font-semibold">Trường người duyệt đã sửa</caption>
                    <thead>
                      <tr class="text-start text-muted"><th class="py-1 text-start font-medium">Trường</th><th class="py-1 text-start font-medium">AI đề xuất</th><th class="py-1 text-start font-medium">Người duyệt</th></tr>
                    </thead>
                    <tbody>
                      <tr v-for="(v, k) in muc.truongDaSua" :key="k" class="border-t border-default align-top">
                        <td class="py-1 pe-2">{{ NHAN_TRUONG[k as TruongTin] ?? k }}</td>
                        <td class="py-1 pe-2 text-muted line-through decoration-error/60">{{ hienGiaTri(v.ai) }}</td>
                        <td class="py-1 font-medium">{{ hienGiaTri(v.nguoi) }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </UCard>
            </div>
          </section>
        </div>
      </template>
    </template>
  </UDashboardPanel>
</template>
