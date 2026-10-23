// SPDX-License-Identifier: Apache-2.0
// Trang Minh bạch cứu trợ công khai (#63, #78): chuẩn hóa mã phiếu, URL tra cứu và ánh xạ phản hồi của
// GET /workflow/minh-bach/phieu/{ma} (cuu_tro_workflow/api.py) → nội dung hiển thị. Hàm thuần, có test
// (tests/minh-bach.test.ts). Không cần đăng nhập; API không trả thông tin cá nhân.

export type TrangThaiPhieu = 'da_xac_minh' | 'khong_khop' | 'chua_ghi_so' | 'khong_kiem_duoc'

export interface KetQuaPhieu {
  ma: string
  trang_thai: TrangThaiPhieu
  chi_tiet: string[]
  ban_ghi_chuan_hoa: { direction: string; quantity: string; note: string | null; created_at: string }
  sha256: string
  hien_thi: { mat_hang: string; don_vi: string; kho: string | null; diem_nhan: string | null }
  so_cai: {
    index: number | null
    logged_at: string | null
    checkpoint: { origin: string; tree_size: number; root_hash: string } | null
  }
  tu_kiem_chung: string
}

/** Nhãn, màu Nuxt UI và biểu tượng cho từng kết quả xác minh (không chỉ dựa vào màu: biểu tượng khiên khác nhau). */
export const TRANG_THAI_PHIEU = {
  da_xac_minh: { nhan: 'Đã xác minh trên sổ cái', mau: 'success', icon: 'i-lucide-shield-check' },
  khong_khop: { nhan: 'Không khớp sổ cái', mau: 'error', icon: 'i-lucide-shield-x' },
  chua_ghi_so: { nhan: 'Chưa ghi lên sổ cái', mau: 'warning', icon: 'i-lucide-shield-alert' },
  khong_kiem_duoc: { nhan: 'Tạm thời không kiểm được', mau: 'neutral', icon: 'i-lucide-shield-question' },
} as const satisfies Record<TrangThaiPhieu, { nhan: string; mau: string; icon: string }>

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/

/** Bỏ khoảng trắng (kể cả giữa mã khi gõ tay hoặc dán), chữ thường. */
export function chuanHoaMa(ma: string): string {
  return ma.replace(/\s+/g, '').toLowerCase()
}

/** Mã phiếu là UUID (in dưới mã QR trên phiếu). Kiểm trước khi gọi API để báo lỗi ngay. */
export function laMaHopLe(ma: string): boolean {
  return UUID.test(chuanHoaMa(ma))
}

export function urlTraPhieu(gatewayUrl: string, ma: string): string {
  return `${gatewayUrl.replace(/\/+$/, '')}/workflow/minh-bach/phieu/${encodeURIComponent(chuanHoaMa(ma))}`
}

export type KetQuaTra = { ok: true; kq: KetQuaPhieu } | { ok: false; loi: string }

function laKetQua(b: unknown): b is KetQuaPhieu {
  if (!b || typeof b !== 'object') return false
  const o = b as Record<string, unknown>
  return typeof o.trang_thai === 'string' && o.trang_thai in TRANG_THAI_PHIEU
    && !!o.ban_ghi_chuan_hoa && !!o.hien_thi && !!o.so_cai && Array.isArray(o.chi_tiet)
}

/** Ánh xạ mã HTTP + thân phản hồi của API → kết quả để hiển thị hoặc câu lỗi tiếng Việt. */
export function docPhanHoi(status: number, body: unknown): KetQuaTra {
  if (status === 404) return { ok: false, loi: 'Không tìm thấy phiếu có mã này. Kiểm tra lại mã trên phiếu.' }
  if (status === 429) return { ok: false, loi: 'Tra cứu quá nhanh. Chờ một phút rồi thử lại.' }
  if (status >= 500) return { ok: false, loi: `Máy chủ đang gặp lỗi (${status}). Thử lại sau ít phút.` }
  if (status !== 200) return { ok: false, loi: `Máy chủ trả lỗi ${status}.` }
  if (!laKetQua(body)) return { ok: false, loi: 'Phản hồi của máy chủ không đúng dạng. Thử lại sau.' }
  return { ok: true, kq: body }
}

/** Lỗi khi gọi fetch: mất mạng (TypeError) có câu riêng. */
export function loiKhiTra(e: unknown): string {
  if (e instanceof TypeError) return 'Không kết nối được máy chủ. Kiểm tra mạng rồi thử lại.'
  return e instanceof Error ? e.message : String(e)
}
