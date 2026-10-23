<!-- SPDX-License-Identifier: Apache-2.0 -->
<script setup lang="ts">
// Chi tiết một tin khi bấm điểm/dòng (#60), dạng ngăn nổi trên bản đồ (không che cột danh sách). Mã, mức
// khẩn, trạng thái lấy từ subscription (luôn mới); mô tả, địa chỉ, số người, nguồn tải bằng query HTTP qua
// gateway, tải lại khi trạng thái đổi. SĐT, tên người gọi, đội phụ trách chỉ có với vai được Hasura cho
// đọc (dieu-phoi, cuu-ho); SĐT che giữa, bấm "Hiện số" mới hiện đủ.
import { NGUON, cheSdt, maNgan, thoiGianTruoc, type ChiTietTin, type TinKeuCuu } from '~/utils/tin'
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
  <section
    class="flex flex-col overflow-hidden rounded-lg bg-default shadow-xl ring ring-default"
    aria-labelledby="tieu-de-ct" @keydown.esc="emit('dong')"
  >
    <header class="flex items-start gap-2 border-b border-default px-4 py-3">
      <div class="min-w-0 flex-1">
        <div class="flex flex-wrap items-center gap-1.5">
          <NhanMucKhan :muc="tin.urgency" />
          <NhanTrangThai :tt="tin.status" />
        </div>
        <h2 id="tieu-de-ct" class="mt-1.5 text-sm font-semibold text-muted">Tin <span class="font-mono">{{ maNgan(tin.id) }}</span></h2>
      </div>
      <UButton icon="i-lucide-x" color="neutral" variant="ghost" size="lg" square aria-label="Đóng chi tiết" class="-me-1.5 -mt-1" @click="emit('dong')" />
    </header>

    <div class="min-h-0 flex-1 overflow-y-auto px-4 py-3">
      <div v-if="dangTai && !ct" class="space-y-2" role="status" aria-label="Đang tải chi tiết">
        <USkeleton class="h-5 w-4/5" /><USkeleton class="h-4 w-3/5" /><USkeleton class="h-4 w-2/5" />
      </div>
      <UAlert v-else-if="loi" role="alert" color="error" variant="subtle" icon="i-lucide-circle-alert" :title="loi" />
      <template v-if="ct">
        <p class="text-pretty text-base font-semibold leading-snug text-highlighted">{{ ct.description }}</p>
        <dl class="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
          <dt class="text-muted">Địa chỉ</dt><dd>{{ ct.address_text || 'Chưa có' }}</dd>
          <dt class="text-muted">Tọa độ</dt><dd class="so font-mono text-xs leading-5">{{ tin.location[1].toFixed(5) }}, {{ tin.location[0].toFixed(5) }}</dd>
          <dt class="text-muted">Số người</dt><dd class="so font-semibold">{{ ct.people_count }}</dd>
          <dt class="text-muted">Nguồn</dt><dd>{{ NGUON[ct.source] ?? ct.source }}</dd>
          <dt class="text-muted">Tiếp nhận</dt><dd><time :datetime="tin.created_at">{{ thoiGianTruoc(tin.created_at, now) }}</time></dd>
          <dt class="text-muted">Cập nhật</dt><dd><time :datetime="ct.updated_at">{{ thoiGianTruoc(ct.updated_at, now) }}</time></dd>
          <template v-if="'team_name' in ct">
            <dt class="text-muted">Đội</dt><dd>{{ ct.team_name || 'Chưa phân công' }}</dd>
          </template>
          <template v-if="ct.reporter_phone !== undefined">
            <dt class="self-center text-muted">Người báo</dt>
            <dd class="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span>{{ ct.reporter_name || 'Không rõ tên' }}</span>
              <span class="so font-mono">{{ hienSo ? ct.reporter_phone : cheSdt(ct.reporter_phone) }}</span>
              <UButton v-if="!hienSo" size="sm" color="info" variant="outline" icon="i-lucide-eye" class="min-h-8" @click="hienSo = true">Hiện số</UButton>
            </dd>
          </template>
        </dl>
      </template>
    </div>

    <footer v-if="coPhanCong" class="border-t border-default p-3">
      <UButton :to="`/phan-cong/${tin.id}`" color="secondary" size="lg" block trailing-icon="i-lucide-arrow-right" class="min-h-11 font-semibold">
        Mở phân công
      </UButton>
    </footer>
  </section>
</template>
