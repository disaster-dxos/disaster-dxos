// SPDX-License-Identifier: Apache-2.0
// Dữ liệu GIẢ cho trang điều phối khi chưa nối GraphQL (#60 thay bằng subscription incidents).
// Trường khớp bảng cuu_tro.incidents (apps/cuu-tro/README.md). SĐT, mô tả, vị trí đều bịa.

export type MucKhan = 'khan_cap' | 'cao' | 'trung_binh' | 'thap'
export type TrangThai = 'tiep_nhan' | 'phan_cong' | 'dang_cuu' | 'da_cuu' | 'dong'

export interface TinKeuCuu {
  id: string
  description: string
  /** [kinh độ, vĩ độ] (WGS 84), giống GeoJSON */
  location: [number, number]
  people_count: number
  urgency: MucKhan
  status: TrangThai
  reporter_phone: string
  source: string
  created_at: string
  dia_chi: string
}

export const MUC_KHAN: Record<MucKhan, { nhan: string; mau: string; thuTu: number }> = {
  khan_cap: { nhan: 'Khẩn cấp', mau: '#DC2626', thuTu: 0 },
  cao: { nhan: 'Cao', mau: '#F07B1D', thuTu: 1 },
  trung_binh: { nhan: 'Trung bình', mau: '#1FA2C9', thuTu: 2 },
  thap: { nhan: 'Thấp', mau: '#64748B', thuTu: 3 },
}

export const TRANG_THAI: Record<TrangThai, string> = {
  tiep_nhan: 'Tiếp nhận',
  phan_cong: 'Đã phân công',
  dang_cuu: 'Đang cứu',
  da_cuu: 'Đã cứu',
  dong: 'Đóng',
}

function phutTruoc(phut: number, now: number): string {
  return new Date(now - phut * 60_000).toISOString()
}

export function tinGia(now = Date.now()): TinKeuCuu[] {
  const t = (
    n: number, description: string, location: [number, number], people_count: number,
    urgency: MucKhan, status: TrangThai, phut: number, dia_chi: string, source = 'hotline',
  ): TinKeuCuu => ({
    id: `d0000000-0000-4000-8000-${String(n).padStart(12, '0')}`,
    description, location, people_count, urgency, status,
    reporter_phone: `09000000${String(n).padStart(2, '0')}`,
    source, created_at: phutTruoc(phut, now), dia_chi,
  })
  return [
    t(1, 'Nước ngập tới mái, 2 người già và 1 trẻ nhỏ mắc kẹt trên gác', [108.2212, 15.9785], 3, 'khan_cap', 'tiep_nhan', 4, 'Thôn Mẫu 1, xã Mẫu A'),
    t(2, 'Gia đình 5 người cần thuyền đưa ra điểm sơ tán', [108.1903, 15.9431], 5, 'cao', 'tiep_nhan', 11, 'Thôn Mẫu 2, xã Mẫu A', 'zalo'),
    t(3, 'Người bị thương ở chân, cần sơ cứu', [108.2487, 15.9122], 1, 'khan_cap', 'phan_cong', 18, 'Tổ Mẫu 3, phường Mẫu B'),
    t(4, 'Hết nước uống và thức ăn từ hôm qua', [108.1452, 15.8833], 7, 'trung_binh', 'tiep_nhan', 26, 'Thôn Mẫu 4, xã Mẫu C', 'tinh-nguyen'),
    t(5, 'Đội cứu hộ đang tiếp cận bằng xuồng', [108.3011, 15.8806], 4, 'cao', 'dang_cuu', 35, 'Thôn Mẫu 5, xã Mẫu D'),
    t(6, 'Cần sạc điện thoại và thông tin dự báo', [108.1135, 15.9520], 2, 'thap', 'tiep_nhan', 47, 'Thôn Mẫu 6, xã Mẫu E', 'zalo'),
    t(7, 'Đã đưa 6 người tới nhà văn hóa', [108.2654, 15.8501], 6, 'trung_binh', 'da_cuu', 72, 'Thôn Mẫu 7, xã Mẫu F'),
  ]
}

/** Thứ tự danh sách cho người điều phối: tin chưa xong trước, khẩn hơn trước, cũ hơn trước. */
export function sapXepTin(ds: TinKeuCuu[]): TinKeuCuu[] {
  const xong = (s: TrangThai) => (s === 'da_cuu' || s === 'dong' ? 1 : 0)
  return [...ds].sort((a, b) =>
    xong(a.status) - xong(b.status)
    || MUC_KHAN[a.urgency].thuTu - MUC_KHAN[b.urgency].thuTu
    || a.created_at.localeCompare(b.created_at))
}

export function demTheoTrangThai(ds: TinKeuCuu[]): Record<TrangThai, number> {
  const kq = { tiep_nhan: 0, phan_cong: 0, dang_cuu: 0, da_cuu: 0, dong: 0 }
  for (const t of ds) kq[t.status]++
  return kq
}

/** "4 phút trước", "2 giờ trước"… */
export function thoiGianTruoc(iso: string, now = Date.now()): string {
  const phut = Math.max(0, Math.floor((now - Date.parse(iso)) / 60_000))
  if (phut < 1) return 'vừa xong'
  if (phut < 60) return `${phut} phút trước`
  const gio = Math.floor(phut / 60)
  if (gio < 24) return `${gio} giờ trước`
  return `${Math.floor(gio / 24)} ngày trước`
}

/** Che giữa SĐT khi hiển thị danh sách: 0900***001 */
export function cheSdt(sdt: string): string {
  return sdt.length >= 7 ? `${sdt.slice(0, 4)}***${sdt.slice(-3)}` : sdt
}
