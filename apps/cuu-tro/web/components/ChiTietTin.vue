<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Chi tiết một tin khi bấm điểm/dòng (#60). Mã, mức khẩn, trạng thái lấy từ subscription (luôn mới);
// mô tả, địa chỉ, số người, nguồn tải bằng query HTTP qua gateway, tải lại khi trạng thái đổi.
// SĐT, tên người gọi, đội phụ trách chỉ có với vai được Hasura cho đọc (dieu-phoi, cuu-ho); SĐT che
// giữa, bấm "Hiện số" mới hiện đủ.
import { MUC_KHAN, NGUON, TRANG_THAI, cheSdt, maNgan, thoiGianTruoc, type ChiTietTin, type TinKeuCuu } from '~/utils/tin'
import { vaiPhanCong } from '~/utils/phan-cong'

const props = defineProps<{ tin: TinKeuCuu }>()
const emit = defineEmits<{ dong: [] }>()
const { layChiTiet } = useTinKeuCuu()
const { user } = useAuth()
// Màn phân công (#61) chỉ cho vai điều phối, cứu hộ
const coPhanCong = computed(() => vaiPhanCong(user.value) !== null)
const ct = ref<ChiTietTin | null>(null)
const dangTai = ref(false)
const loi = ref('')
const hienSo = ref(false)
const now = useNow()

async function tai() {
  dangTai.value = true
  loi.value = ''
  try {
    ct.value = await layChiTiet(props.tin.id)
    if (!ct.value) loi.value = 'Không tìm thấy tin hoặc bạn không có quyền xem chi tiết.'
  } catch (e) {
    loi.value = e instanceof Error ? e.message : String(e)
  } finally {
    dangTai.value = false
  }
}

watch(() => props.tin.id, () => { ct.value = null; hienSo.value = false; void tai() }, { immediate: true })
watch(() => props.tin.status, () => { void tai() })
</script>

<template>
  <section class="border-b-4 border-cam bg-white px-4 py-3" aria-labelledby="tieu-de-ct" aria-live="polite">
    <div class="flex items-start gap-2">
      <h2 id="tieu-de-ct" class="text-base font-bold text-navy">Tin <span class="font-mono">{{ maNgan(tin.id) }}</span></h2>
      <span class="rounded px-1.5 py-0.5 text-xs font-bold text-white" :style="{ background: MUC_KHAN[tin.urgency].mau }">{{ MUC_KHAN[tin.urgency].nhan }}</span>
      <span class="rounded bg-slate-200 px-1.5 py-0.5 text-xs font-bold text-slate-700">{{ TRANG_THAI[tin.status] }}</span>
      <button
        type="button" class="ml-auto rounded px-2 text-lg leading-none text-slate-500 hover:bg-slate-100 hover:text-navy"
        aria-label="Đóng chi tiết" @click="emit('dong')"
      >
        ×
      </button>
    </div>
    <p v-if="dangTai && !ct" class="mt-2 text-sm text-slate-500">Đang tải chi tiết…</p>
    <p v-else-if="loi" class="mt-2 text-sm text-red-700" role="alert">{{ loi }}</p>
    <template v-if="ct">
      <p class="mt-2 text-sm font-bold text-chu">{{ ct.description }}</p>
      <dl class="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
        <dt class="text-slate-500">Địa chỉ</dt><dd>{{ ct.address_text || 'Chưa có' }}</dd>
        <dt class="text-slate-500">Tọa độ</dt><dd class="font-mono">{{ tin.location[1].toFixed(5) }}, {{ tin.location[0].toFixed(5) }}</dd>
        <dt class="text-slate-500">Số người</dt><dd>{{ ct.people_count }}</dd>
        <dt class="text-slate-500">Nguồn</dt><dd>{{ NGUON[ct.source] ?? ct.source }}</dd>
        <dt class="text-slate-500">Tiếp nhận</dt><dd><time :datetime="tin.created_at">{{ thoiGianTruoc(tin.created_at, now) }}</time></dd>
        <dt class="text-slate-500">Cập nhật</dt><dd><time :datetime="ct.updated_at">{{ thoiGianTruoc(ct.updated_at, now) }}</time></dd>
        <template v-if="'team_name' in ct">
          <dt class="text-slate-500">Đội phụ trách</dt><dd>{{ ct.team_name || 'Chưa phân công' }}</dd>
        </template>
        <template v-if="ct.reporter_phone !== undefined">
          <dt class="text-slate-500">Người báo</dt>
          <dd>
            {{ ct.reporter_name || 'Không rõ tên' }} ·
            <span class="font-mono">{{ hienSo ? ct.reporter_phone : cheSdt(ct.reporter_phone) }}</span>
            <button v-if="!hienSo" type="button" class="ml-1 font-bold text-nuoc hover:underline" @click="hienSo = true">Hiện số</button>
          </dd>
        </template>
      </dl>
    </template>
    <NuxtLink
      v-if="coPhanCong"
      :to="`/phan-cong/${tin.id}`"
      class="mt-3 flex min-h-11 items-center justify-center rounded-lg bg-cam px-4 text-sm font-bold text-white hover:bg-cam-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-navy"
    >
      Mở phân công →
    </NuxtLink>
  </section>
</template>
