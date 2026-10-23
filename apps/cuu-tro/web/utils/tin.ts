// SPDX-License-Identifier: Apache-2.0
// Tin kêu cứu trên trang điều phối (#60): kiểu dữ liệu, nhãn tiếng Việt, sắp xếp, bộ lọc, phát hiện tin
// mới. Hàm thuần, có test (tests/tin.test.ts). Trường khớp bảng cuu_tro.incidents (apps/cuu-tro/README.md).

export type MucKhan = 'khan_cap' | 'cao' | 'trung_binh' | 'thap'
export type TrangThai = 'tiep_nhan' | 'phan_cong' | 'dang_cuu' | 'da_cuu' | 'dong'

/** Một điểm trên bản đồ: chỉ trường subscription lấy về, không có SĐT, tên, mô tả. */
export interface TinKeuCuu {
  id: string
  /** [kinh độ, vĩ độ] (WGS 84), giống GeoJSON */
  location: [number, number]
  urgency: MucKhan
  status: TrangThai
  created_at: string
}

/** Chi tiết một tin, chỉ tải khi người dùng bấm vào (query riêng, cột theo quyền của vai). */
export interface ChiTietTin extends TinKeuCuu {
  description: string
  address_text: string | null
  people_count: number
  source: string
  updated_at: string
  /** Chỉ vai có quyền đọc cột (dieu-phoi, cuu-ho); vai khác không truy vấn cột này */
  reporter_phone?: string
  reporter_name?: string | null
  team_name?: string | null
}

export const MUC_KHAN: Record<MucKhan, { nhan: string; mau: string; thuTu: number }> = {
  khan_cap: { nhan: 'Khẩn cấp', mau: '#DC2626', thuTu: 0 },
  cao: { nhan: 'Cao', mau: '#F07B1D', thuTu: 1 },
  trung_binh: { nhan: 'Trung bình', mau: '#1FA2C9', thuTu: 2 },
  thap: { nhan: 'Thấp', mau: '#64748B', thuTu: 3 },
}

/** Nhãn và màu viền điểm theo trạng thái (viền trắng = chưa ai nhận, mờ dần khi đã xong). */
export const TRANG_THAI: Record<TrangThai, string> = {
  tiep_nhan: 'Tiếp nhận',
  phan_cong: 'Đã phân công',
  dang_cuu: 'Đang cứu',
  da_cuu: 'Đã cứu',
  dong: 'Đóng',
}

export const MAU_TRANG_THAI: Record<TrangThai, string> = {
  tiep_nhan: '#FFFFFF',
  phan_cong: '#12355B',
  dang_cuu: '#7C3AED',
  da_cuu: '#16A34A',
  dong: '#94A3B8',
}

/** Màu trạng thái trên nền tối: viền navy không thấy trên bản đồ tối → navy nhạt (navy-400). */
export const NAVY_TOI = '#7A9CC6'
export function mauTrangThai(s: TrangThai, toi = false): string {
  return toi && MAU_TRANG_THAI[s] === '#12355B' ? NAVY_TOI : MAU_TRANG_THAI[s]
}

export const NGUON: Record<string, string> = {
  dien_thoai: 'Điện thoại',
  web: 'Web',
  app: 'Ứng dụng',
  telegram: 'Telegram',
  mang_xa_hoi: 'Mạng xã hội',
  khac: 'Khác',
}

export const DS_MUC_KHAN = Object.keys(MUC_KHAN) as MucKhan[]
export const DS_TRANG_THAI = Object.keys(TRANG_THAI) as TrangThai[]

export function laMucKhan(v: unknown): v is MucKhan {
  return typeof v === 'string' && v in MUC_KHAN
}

export function laTrangThai(v: unknown): v is TrangThai {
  return typeof v === 'string' && v in TRANG_THAI
}

/** Thứ tự danh sách cho người điều phối: tin chưa xong trước, khẩn hơn trước, cũ hơn trước. */
export function sapXepTin<T extends TinKeuCuu>(ds: T[]): T[] {
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

export function demTheoMucKhan(ds: TinKeuCuu[]): Record<MucKhan, number> {
  const kq = { khan_cap: 0, cao: 0, trung_binh: 0, thap: 0 }
  for (const t of ds) kq[t.urgency]++
  return kq
}

// ---------- Bộ lọc (dùng chung cho bản đồ và danh sách) ----------

export interface BoLoc {
  trangThai: TrangThai[]
  mucKhan: MucKhan[]
}

/** Mặc định: mọi mức khẩn, ẩn tin đã đóng. */
export function boLocMacDinh(): BoLoc {
  return { trangThai: DS_TRANG_THAI.filter((s) => s !== 'dong'), mucKhan: [...DS_MUC_KHAN] }
}

export function locTin<T extends TinKeuCuu>(ds: T[], loc: BoLoc): T[] {
  const tt = new Set(loc.trangThai)
  const mk = new Set(loc.mucKhan)
  return ds.filter((t) => tt.has(t.status) && mk.has(t.urgency))
}

/** Bật/tắt một giá trị trong bộ lọc, giữ thứ tự gốc; không trả mảng mới nếu giá trị lạ. */
export function batTat<K extends string>(dangChon: K[], gt: K, thuTu: readonly K[]): K[] {
  if (!thuTu.includes(gt)) return dangChon
  const co = new Set(dangChon)
  if (co.has(gt)) co.delete(gt)
  else co.add(gt)
  return thuTu.filter((x) => co.has(x))
}

// ---------- Tin mới (nhấp nháy trên bản đồ, nổi lên trong danh sách) ----------

/** Tin được coi là "mới" trong 60 giây kể từ lúc web thấy nó lần đầu. */
export const THOI_GIAN_TIN_MOI_MS = 60_000

/**
 * Cập nhật danh sách tin mới sau mỗi kết quả subscription.
 * - daBiet: id đã thấy từ trước (kể cả kết quả đầu tiên, vốn không tính là mới).
 * - moi: id → mốc thấy lần đầu (ms). Tin quá THOI_GIAN_TIN_MOI_MS hoặc không còn trong kết quả thì bỏ.
 * Kết quả đầu tiên (lanDau) chỉ ghi nhận, không đánh dấu tin nào là mới.
 */
export function capNhatTinMoi(
  daBiet: ReadonlySet<string>, moi: ReadonlyMap<string, number>, ds: TinKeuCuu[], lanDau: boolean, now = Date.now(),
): { daBiet: Set<string>; moi: Map<string, number> } {
  const biet = new Set(daBiet)
  const kq = new Map<string, number>()
  const conLai = new Set(ds.map((t) => t.id))
  for (const [id, luc] of moi) if (conLai.has(id) && now - luc < THOI_GIAN_TIN_MOI_MS) kq.set(id, luc)
  for (const t of ds) {
    if (!biet.has(t.id) && !lanDau) kq.set(t.id, now)
    biet.add(t.id)
  }
  return { daBiet: biet, moi: kq }
}

/** Đưa tin mới lên đầu danh sách (mới nhất trước), phần còn lại giữ thứ tự sapXepTin. */
export function noiTinMoi<T extends TinKeuCuu>(ds: T[], moi: ReadonlyMap<string, number>): T[] {
  const dau = ds.filter((t) => moi.has(t.id)).sort((a, b) => moi.get(b.id)! - moi.get(a.id)!)
  return [...dau, ...ds.filter((t) => !moi.has(t.id))]
}

// ---------- Hiển thị ----------

/** "4 phút trước", "2 giờ trước"… */
export function thoiGianTruoc(iso: string, now = Date.now()): string {
  const phut = Math.max(0, Math.floor((now - Date.parse(iso)) / 60_000))
  if (phut < 1) return 'vừa xong'
  if (phut < 60) return `${phut} phút trước`
  const gio = Math.floor(phut / 60)
  if (gio < 24) return `${gio} giờ trước`
  return `${Math.floor(gio / 24)} ngày trước`
}

/** Che giữa SĐT khi hiển thị: 0900***001 */
export function cheSdt(sdt: string): string {
  return sdt.length >= 7 ? `${sdt.slice(0, 4)}***${sdt.slice(-3)}` : sdt
}

/** Mã ngắn của tin để người điều phối đọc: 8 ký tự đầu của UUID */
export function maNgan(id: string): string {
  return id.slice(0, 8)
}
