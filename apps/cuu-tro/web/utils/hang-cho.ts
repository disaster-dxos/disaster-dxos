// SPDX-License-Identifier: Apache-2.0
// Hàng chờ duyệt tin do AI bóc tách (#104, Human-in-the-loop): kiểu dữ liệu, GraphQL đọc hàng chờ (Hasura, chỉ
// vai dieu-phoi thấy văn bản gốc và đề xuất), form sửa đề xuất ↔ body POST /workflow/keu-cuu, đánh dấu trường
// người duyệt đã sửa, lỗi Poka-yoke theo trường, câu báo lỗi tiếng Việt. Hàm thuần, có test
// (tests/hang-cho.test.ts). Gọi mạng: composables/useHangCho.ts. API: apps/cuu-tro/README.md mục
// "Hàng chờ duyệt". Kiểm tra thật nằm ở API (cùng Poka-yoke với /keu-cuu); kiểm ở đây chỉ để báo sớm.
import { laMucKhan, type MucKhan } from './tin'

export type TrangThaiHangCho = 'cho_duyet' | 'da_duyet' | 'da_huy'
export type NguonVanBan = 'sms' | 'zalo' | 'dien_thoai' | 'mang_xa_hoi' | 'van_ban'

export const TRANG_THAI_HANG_CHO: Record<TrangThaiHangCho, string> = {
  cho_duyet: 'Chờ duyệt',
  da_duyet: 'Đã duyệt',
  da_huy: 'Đã hủy',
}

export const NGUON_VAN_BAN: Record<NguonVanBan, string> = {
  sms: 'SMS',
  zalo: 'Zalo',
  dien_thoai: 'Điện thoại (ghi lại)',
  mang_xa_hoi: 'Mạng xã hội',
  van_ban: 'Văn bản khác',
}
export const DS_NGUON_VAN_BAN = Object.keys(NGUON_VAN_BAN) as NguonVanBan[]

export const NHU_CAU: Record<string, string> = {
  cuu_nguoi: 'Cứu người',
  y_te: 'Y tế',
  luong_thuc: 'Lương thực',
  nuoc_uong: 'Nước uống',
  cho_o: 'Chỗ ở',
  di_doi: 'Di dời',
  khac: 'Khác',
}

/** Trường của POST /workflow/keu-cuu, đúng thứ tự hiện trên form. */
export const TRUONG_TIN = ['reporter_phone', 'reporter_name', 'lat', 'lon', 'address_text', 'people_count', 'urgency',
  'description', 'source'] as const
export type TruongTin = typeof TRUONG_TIN[number]

export const NHAN_TRUONG: Record<TruongTin, string> = {
  reporter_phone: 'SĐT người báo',
  reporter_name: 'Tên người báo',
  lat: 'Vĩ độ',
  lon: 'Kinh độ',
  address_text: 'Địa chỉ',
  people_count: 'Số người',
  urgency: 'Mức khẩn cấp',
  description: 'Mô tả',
  source: 'Nguồn tin',
}

export const MO_TA_TOI_DA = 500
export const DIA_CHI_TOI_DA = 300
export const TEN_TOI_DA = 100
export const LY_DO_TOI_DA = 500
export const VAN_BAN_TOI_DA = 2000

/** Lý do hủy hay gặp, bấm chọn nhanh (vẫn sửa được). */
export const LY_DO_HUY_NHANH = [
  'Trùng tin kêu cứu đã có',
  'Tin rác hoặc tin thử',
  'Không đủ thông tin, đã gọi lại không được',
  'Không phải tin kêu cứu',
]

export interface LoiTruong { truong: string; thong_bao: string }

export interface TinTrung {
  incident_id: string
  khoang_cach_m: number
  thong_bao: string
}

/** Body /keu-cuu: số là số, chuỗi là chuỗi; AI không tìm thấy thì trường vắng mặt. */
export type BodyTin = Partial<Record<TruongTin, string | number>>

export interface MucHangCho {
  id: string
  trangThai: TrangThaiHangCho
  vanBan: string
  nguon: NguonVanBan
  taoLuc: string
  nguoiGui: string | null
  vaiGui: string
  urgency: MucKhan
  hopLe: boolean
  ai: { nhaCungCap: string; moHinh: string | null; duPhong: boolean; thoiGianMs: number }
  /** Đề xuất của AI dạng body /keu-cuu */
  deXuat: BodyTin
  nhuCau: string[]
  loi: LoiTruong[]
  tinTrung: TinTrung | null
  canhBao: string[]
  // Vết duyệt (khi đã xử lý)
  duyetLuc: string | null
  nguoiDuyet: string | null
  incidentId: string | null
  lyDoHuy: string | null
  truongDaSua: Record<string, { ai: unknown; nguoi: unknown }> | null
  tinCuoi: BodyTin | null
}

const COT = `id status raw_text text_source created_at submitted_by_name submitted_role ai_urgency ai_valid
    ai_provider ai_model ai_fallback ai_duration_ms ai_result reviewed_at reviewed_by_name incident_id cancel_reason
    edited_fields final_body`

/** Hàng chờ theo trạng thái. Chờ duyệt: cũ trước (sắp lại khẩn trước ở client); đã xử lý: mới duyệt trước. */
export function queryHangCho(tt: TrangThaiHangCho): string {
  const thuTu = tt === 'cho_duyet' ? '{created_at: asc}' : '{reviewed_at: desc}'
  return `query HangCho($tt: String!) {
  ai_intake_reviews(where: {status: {_eq: $tt}}, order_by: ${thuTu}, limit: 200) {
    ${COT}
  }
  cho: ai_intake_reviews_aggregate(where: {status: {_eq: "cho_duyet"}}) { aggregate { count } }
}`
}

const chuoi = (v: unknown): string | null => (typeof v === 'string' ? v : null)
const so = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null)
const doiTuong = (v: unknown): Record<string, unknown> | null =>
  v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : null
const laTrangThaiHangCho = (v: unknown): v is TrangThaiHangCho => typeof v === 'string' && v in TRANG_THAI_HANG_CHO
const laNguon = (v: unknown): v is NguonVanBan => typeof v === 'string' && v in NGUON_VAN_BAN

function bodyTin(v: unknown): BodyTin {
  const r = doiTuong(v)
  const kq: BodyTin = {}
  if (!r) return kq
  for (const k of TRUONG_TIN) {
    const x = r[k]
    if (typeof x === 'string' || (typeof x === 'number' && Number.isFinite(x))) kq[k] = x
  }
  return kq
}

function dsLoi(v: unknown): LoiTruong[] {
  if (!Array.isArray(v)) return []
  return v.flatMap((x) => {
    const r = doiTuong(x)
    const truong = chuoi(r?.truong)
    const tb = chuoi(r?.thong_bao)
    return truong && tb ? [{ truong, thong_bao: tb }] : []
  })
}

/** Một hàng GraphQL → MucHangCho; thiếu trường bắt buộc thì null (bỏ qua). */
export function mucTuHang(h: unknown): MucHangCho | null {
  const r = doiTuong(h)
  if (!r) return null
  const ai = doiTuong(r.ai_result) ?? {}
  const pk = doiTuong(ai.poka_yoke) ?? {}
  const trung = doiTuong(pk.tin_trung)
  const taoLuc = chuoi(r.created_at)
  if (typeof r.id !== 'string' || !laTrangThaiHangCho(r.status) || typeof r.raw_text !== 'string' || !taoLuc) return null
  const sua = doiTuong(r.edited_fields)
  return {
    id: r.id,
    trangThai: r.status,
    vanBan: r.raw_text,
    nguon: laNguon(r.text_source) ? r.text_source : 'van_ban',
    taoLuc,
    nguoiGui: chuoi(r.submitted_by_name),
    vaiGui: chuoi(r.submitted_role) ?? '',
    urgency: laMucKhan(r.ai_urgency) ? r.ai_urgency : 'trung_binh',
    hopLe: r.ai_valid === true,
    ai: {
      nhaCungCap: chuoi(r.ai_provider) ?? '',
      moHinh: chuoi(r.ai_model),
      duPhong: r.ai_fallback === true,
      thoiGianMs: so(r.ai_duration_ms) ?? 0,
    },
    deXuat: bodyTin(ai.tin_keu_cuu),
    nhuCau: Array.isArray(doiTuong(ai.de_xuat)?.nhu_cau)
      ? (doiTuong(ai.de_xuat)!.nhu_cau as unknown[]).filter((x): x is string => typeof x === 'string')
      : [],
    loi: dsLoi(pk.loi),
    tinTrung: trung && typeof trung.incident_id === 'string'
      ? { incident_id: trung.incident_id, khoang_cach_m: so(trung.khoang_cach_m) ?? 0, thong_bao: chuoi(trung.thong_bao) ?? '' }
      : null,
    canhBao: Array.isArray(ai.canh_bao) ? ai.canh_bao.filter((x): x is string => typeof x === 'string') : [],
    duyetLuc: chuoi(r.reviewed_at),
    nguoiDuyet: chuoi(r.reviewed_by_name),
    incidentId: chuoi(r.incident_id),
    lyDoHuy: chuoi(r.cancel_reason),
    truongDaSua: sua ? (sua as Record<string, { ai: unknown; nguoi: unknown }>) : null,
    tinCuoi: r.final_body ? bodyTin(r.final_body) : null,
  }
}

export function hangChoTuKetQua(data: unknown): { ds: MucHangCho[]; soChoDuyet: number } {
  const d = doiTuong(data)
  const rows = d?.ai_intake_reviews
  const dem = so(doiTuong(doiTuong(d?.cho)?.aggregate)?.count) ?? 0
  return { ds: Array.isArray(rows) ? rows.map(mucTuHang).filter((m): m is MucHangCho => m !== null) : [], soChoDuyet: dem }
}

const THU_TU_KHAN: Record<MucKhan, number> = { khan_cap: 0, cao: 1, trung_binh: 2, thap: 3 }

/** Hàng chờ cho người duyệt: khẩn hơn trước, cùng mức thì cũ hơn trước. Đã xử lý: giữ thứ tự (mới duyệt trước). */
export function sapXepHangCho(ds: MucHangCho[]): MucHangCho[] {
  return [...ds].sort((a, b) => {
    if (a.trangThai !== 'cho_duyet' || b.trangThai !== 'cho_duyet') return 0
    return THU_TU_KHAN[a.urgency] - THU_TU_KHAN[b.urgency] || a.taoLuc.localeCompare(b.taoLuc)
  })
}

// ---------- Form sửa đề xuất ----------

/** Form: mọi ô là chuỗi (ô nhập), trống = không có. */
export type FormTin = Record<TruongTin, string>

export function formTuBody(b: BodyTin): FormTin {
  const f = {} as FormTin
  for (const k of TRUONG_TIN) f[k] = b[k] === undefined || b[k] === null ? '' : String(b[k])
  if (!f.urgency) f.urgency = 'trung_binh'
  return f
}

/** "16,0712" (dấu phẩy thập phân kiểu Việt) hay "16.0712" → số; không phải số → NaN. Trống → null. */
export function docSo(s: string): number | null {
  const t = s.trim()
  if (!t) return null
  const chuan = /^-?\d+,\d+$/.test(t) ? t.replace(',', '.') : t
  return /^-?\d+(\.\d+)?$/.test(chuan) ? Number(chuan) : Number.NaN
}

/**
 * Form → body đầy đủ của /keu-cuu (bỏ ô trống) + lỗi phát hiện sớm (số không đọc được, thiếu tọa độ, thiếu
 * SĐT/mô tả, vượt độ dài). API vẫn kiểm lại toàn bộ (vùng phục vụ, dạng SĐT, tin trùng).
 */
export function bodyTuForm(f: FormTin): { body: BodyTin; loi: LoiTruong[] } {
  const body: BodyTin = {}
  const loi: LoiTruong[] = []
  for (const k of TRUONG_TIN) {
    const v = f[k].trim()
    if (!v) continue
    if (k === 'lat' || k === 'lon' || k === 'people_count') {
      const n = docSo(v)
      if (n === null) continue
      if (Number.isNaN(n)) loi.push({ truong: k, thong_bao: `${NHAN_TRUONG[k]} phải là số.` })
      else if (k === 'people_count' && !Number.isInteger(n)) loi.push({ truong: k, thong_bao: 'Số người phải là số nguyên.' })
      else body[k] = n
    } else {
      body[k] = v
    }
  }
  for (const [k, ten] of [['lat', 'vĩ độ'], ['lon', 'kinh độ']] as const) {
    if (f[k].trim() === '') loi.push({ truong: k, thong_bao: `Thiếu ${ten}: chọn vị trí trên bản đồ hoặc nhập tọa độ.` })
  }
  if (!f.reporter_phone.trim()) loi.push({ truong: 'reporter_phone', thong_bao: 'Thiếu số điện thoại người báo.' })
  if (!f.description.trim()) loi.push({ truong: 'description', thong_bao: 'Thiếu mô tả.' })
  const dai: Array<[TruongTin, number]> = [['description', MO_TA_TOI_DA], ['address_text', DIA_CHI_TOI_DA], ['reporter_name', TEN_TOI_DA]]
  for (const [k, toiDa] of dai) {
    if (f[k].trim().length > toiDa) loi.push({ truong: k, thong_bao: `${NHAN_TRUONG[k]} dài tối đa ${toiDa} ký tự.` })
  }
  return { body, loi }
}

/** Chuẩn hóa để so: SĐT bỏ dấu cách/chấm/gạch, +84 → 0; số so theo giá trị. */
function chuanDeSo(k: TruongTin, v: string): string {
  const t = v.trim()
  if (k === 'reporter_phone') {
    const s = t.replace(/[\s.\-()]/g, '')
    return s.startsWith('+84') ? `0${s.slice(3)}` : s
  }
  if (k === 'lat' || k === 'lon' || k === 'people_count') {
    const n = docSo(t)
    return n === null || Number.isNaN(n) ? t : String(n)
  }
  return t
}

/** Trường trên form khác đề xuất của AI (đánh dấu "đã sửa"; API tự tính lại khi lưu vết). */
export function truongDaSua(f: FormTin, deXuat: FormTin): TruongTin[] {
  return TRUONG_TIN.filter((k) => chuanDeSo(k, f[k]) !== chuanDeSo(k, deXuat[k]))
}

/** Lỗi theo trường → {trường: câu đầu tiên}; lỗi không gắn trường form nằm ở khóa "body". */
export function loiTheoTruong(loi: LoiTruong[]): Record<string, string> {
  const kq: Record<string, string> = {}
  for (const x of loi) {
    const k = (TRUONG_TIN as readonly string[]).includes(x.truong) ? x.truong : 'body'
    kq[k] ??= x.thong_bao
  }
  return kq
}

/** Giá trị trong vết duyệt để hiển thị: null/undefined → "(trống)". */
export function hienGiaTri(v: unknown): string {
  if (v === null || v === undefined || v === '') return '(trống)'
  return String(v)
}

/** Tọa độ trên form (hợp lệ cả hai) → [kinh độ, vĩ độ] cho bản đồ; không thì null. */
export function toaDoForm(f: FormTin): [number, number] | null {
  const lat = docSo(f.lat)
  const lon = docSo(f.lon)
  if (lat === null || lon === null || Number.isNaN(lat) || Number.isNaN(lon)) return null
  if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return null
  return [lon, lat]
}

/** Điểm chọn trên bản đồ → ô vĩ độ/kinh độ (6 chữ số thập phân ≈ 0,1 m). */
export function oToaDo(lngLat: { lng: number; lat: number }): { lat: string; lon: string } {
  return { lat: lngLat.lat.toFixed(6), lon: lngLat.lng.toFixed(6) }
}

// ---------- Lỗi API ----------

export interface LoiApi {
  status: number
  /** detail của FastAPI: chuỗi hoặc {ma, thong_bao, loi?, incident_id?, …} */
  detail: unknown
}

export interface KetQuaLoi {
  thongBao: string
  loi: LoiTruong[]
  /** Tin kêu cứu đang mở bị trùng (409 tin_trung) */
  tinTrungId: string | null
  /** Mục đã được người khác xử lý (409 da_xu_ly): tải lại hàng chờ */
  daXuLy: boolean
}

/** Lỗi của duyệt/hủy/bóc tách → câu tiếng Việt + lỗi theo trường. */
export function phanTichLoi(e: LoiApi, viec: 'duyet' | 'huy' | 'boc_tach'): KetQuaLoi {
  const d = doiTuong(e.detail)
  const tb = chuoi(d?.thong_bao) ?? chuoi(e.detail) ?? ''
  const kq: KetQuaLoi = { thongBao: '', loi: dsLoi(d?.loi), tinTrungId: null, daXuLy: false }
  switch (true) {
    case e.status === 0:
      kq.thongBao = 'Không kết nối được máy chủ. Kiểm tra mạng rồi thử lại.'
      break
    case e.status === 401:
      kq.thongBao = 'Phiên đăng nhập đã hết. Hãy đăng nhập lại.'
      break
    case e.status === 403:
      kq.thongBao = 'Bạn không có quyền thực hiện thao tác này (chỉ vai Điều phối duyệt tin).'
      break
    case e.status === 404:
      kq.thongBao = 'Không còn tin này trong hàng chờ.'
      break
    case e.status === 409 && d?.ma === 'tin_trung':
      kq.tinTrungId = chuoi(d.incident_id)
      kq.thongBao = `${tb} Nếu đúng là cùng một vụ, hãy hủy mục này với lý do "Trùng tin kêu cứu đã có".`
      break
    case e.status === 409 && d?.ma === 'da_xu_ly':
      kq.daXuLy = true
      kq.thongBao = tb || 'Tin này đã được người khác xử lý.'
      break
    case e.status === 422:
      kq.thongBao = kq.loi.length ? 'Chưa duyệt được: sửa các trường được đánh dấu.' : (tb || 'Dữ liệu gửi lên không hợp lệ.')
      if (viec === 'huy') kq.thongBao = 'Chưa hủy được: lý do tối đa 500 ký tự.'
      if (viec === 'boc_tach') kq.thongBao = kq.loi[0]?.thong_bao ?? 'Văn bản không hợp lệ.'
      break
    case e.status === 413:
      kq.thongBao = 'Nội dung quá dài.'
      break
    case e.status === 429:
      kq.thongBao = 'Thao tác quá nhanh. Chờ một chút rồi thử lại.'
      break
    case e.status === 503 && viec === 'boc_tach':
      kq.thongBao = 'Tính năng AI bóc tách đang tắt trên máy chủ.'
      break
    case e.status >= 500:
      kq.thongBao = `Máy chủ đang lỗi (HTTP ${e.status}). Thử lại sau ít phút.`
      break
    default:
      kq.thongBao = tb || `Thao tác không thành công (HTTP ${e.status}).`
  }
  return kq
}
