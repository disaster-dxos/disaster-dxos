// SPDX-License-Identifier: Apache-2.0
// Màn phân công cứu hộ (#61): kiểu dữ liệu, GraphQL hàng đợi/chi tiết, nhóm tin theo việc cần làm, nút
// theo vai và bước của workflow, đếm ngược hạn nhận, nhãn tiếng Việt. Hàm thuần, có test
// (tests/phan-cong.test.ts). Gọi API /workflow: utils/workflow-api.ts; gọi mạng: composables/usePhanCong.ts.
// Nút ẩn/hiện theo vai chỉ để giao diện gọn: kiểm quyền thật nằm ở API (cuu_tro_workflow/api.py) và Hasura.
import { laMucKhan, laTrangThai, sapXepTin, type TinKeuCuu, type TrangThai } from './tin'
import { toaDoTuGeoJson } from './tin-graphql'
import type { UserInfo } from './session'

export type VaiPhanCong = 'dieu-phoi' | 'cuu-ho'

/** Vai dùng trên màn phân công: điều phối nếu có, không thì cứu hộ; vai khác không vào được màn này. */
export function vaiPhanCong(u: UserInfo | null): VaiPhanCong | null {
  if (u?.roles.includes('dieu-phoi')) return 'dieu-phoi'
  if (u?.roles.includes('cuu-ho')) return 'cuu-ho'
  return null
}

// ---------- Dữ liệu từ Hasura (bảng incidents + lịch sử giao incident_assignments, #67) ----------

export type KetQuaGiao = 'cho_nhan' | 'da_nhan' | 'tu_choi' | 'qua_han' | 'huy'

export const KET_QUA_GIAO: Record<KetQuaGiao, string> = {
  cho_nhan: 'Chờ nhận',
  da_nhan: 'Đã nhận',
  tu_choi: 'Từ chối',
  qua_han: 'Quá hạn',
  huy: 'Điều phối hủy',
}

export interface LanGiao {
  lan: number
  doiId: string
  /** null khi vai không được đọc tên đội đó */
  doiTen: string | null
  khoangCachM: number | null
  giaoLuc: string
  hanLuc: string
  ketQua: KetQuaGiao
  phanHoiLuc: string | null
  nguoi: string | null
  ghiChu: string | null
}

/** Một tin trong hàng đợi phân công: trường của bản đồ + mô tả + đội + lịch sử giao. Không có SĐT. */
export interface TinPhanCong extends TinKeuCuu {
  description: string
  address_text: string | null
  people_count: number
  updated_at: string
  doiTen: string | null
  giao: LanGiao[]
}

/** Liên hệ người báo: chỉ query của vai được Hasura cho đọc (dieu-phoi, cuu-ho) mới có. */
export interface LienHe {
  reporter_phone: string
  reporter_name: string | null
}

const TRUONG_TIN = `id location urgency status created_at updated_at description address_text people_count
    assigned_team { name }
    assignments(order_by: [{assigned_at: asc}, {attempt_no: asc}]) {
      attempt_no team_id distance_m assigned_at deadline_at result responded_at responded_by note team { name }
    }`

/** Tin còn việc phân công/cứu. Hasura lọc theo vai: cuu-ho chỉ thấy tin đang giao cho đội mình. */
export const TRANG_THAI_HANG: TrangThai[] = ['tiep_nhan', 'phan_cong', 'dang_cuu']

export const Q_HANG_PHAN_CONG = `query HangPhanCong($trangThai: [String!]!) {
  incidents(where: {status: {_in: $trangThai}}, order_by: {created_at: asc}, limit: 300) {
    ${TRUONG_TIN}
  }
}`

/** Vai được đọc SĐT và tên người báo (metadata Hasura #26); vai khác không hỏi cột này. */
const VAI_XEM_LIEN_HE: readonly string[] = ['dieu-phoi', 'cuu-ho']

export function queryTinPhanCong(vai: string | null): string {
  const lienHe = vai && VAI_XEM_LIEN_HE.includes(vai) ? ' reporter_phone reporter_name' : ''
  return `query TinPhanCong($id: uuid!) {
  incidents_by_pk(id: $id) {
    ${TRUONG_TIN}${lienHe}
  }
}`
}

const chuoi = (v: unknown): string | null => (typeof v === 'string' ? v : null)
const so = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null)
const laKetQuaGiao = (v: unknown): v is KetQuaGiao => typeof v === 'string' && v in KET_QUA_GIAO

function lanGiaoTuHang(h: unknown): LanGiao | null {
  if (!h || typeof h !== 'object') return null
  const r = h as Record<string, unknown>
  const giaoLuc = chuoi(r.assigned_at)
  const hanLuc = chuoi(r.deadline_at)
  if (typeof r.attempt_no !== 'number' || typeof r.team_id !== 'string' || !giaoLuc || !hanLuc || !laKetQuaGiao(r.result)) {
    return null
  }
  return {
    lan: r.attempt_no,
    doiId: r.team_id,
    doiTen: chuoi((r.team as { name?: unknown } | null)?.name),
    khoangCachM: so(r.distance_m),
    giaoLuc,
    hanLuc,
    ketQua: r.result,
    phanHoiLuc: chuoi(r.responded_at),
    nguoi: chuoi(r.responded_by),
    ghiChu: chuoi(r.note),
  }
}

/** Một hàng GraphQL → TinPhanCong; thiếu trường hoặc giá trị lạ thì null (bỏ qua). */
export function tinPhanCongTuHang(h: unknown): (TinPhanCong & Partial<LienHe>) | null {
  if (!h || typeof h !== 'object') return null
  const r = h as Record<string, unknown>
  const location = toaDoTuGeoJson(r.location)
  const created = chuoi(r.created_at)
  if (typeof r.id !== 'string' || !location || !laMucKhan(r.urgency) || !laTrangThai(r.status) || !created) return null
  const giao = Array.isArray(r.assignments)
    ? r.assignments.map(lanGiaoTuHang).filter((g): g is LanGiao => g !== null)
    : []
  return {
    id: r.id,
    location,
    urgency: r.urgency,
    status: r.status,
    created_at: created,
    updated_at: chuoi(r.updated_at) ?? created,
    description: chuoi(r.description) ?? '',
    address_text: chuoi(r.address_text),
    people_count: so(r.people_count) ?? 1,
    doiTen: chuoi((r.assigned_team as { name?: unknown } | null)?.name),
    giao,
    ...('reporter_phone' in r ? { reporter_phone: chuoi(r.reporter_phone) ?? '', reporter_name: chuoi(r.reporter_name) } : {}),
  }
}

export function hangTuKetQua(data: unknown): TinPhanCong[] {
  const rows = (data as { incidents?: unknown } | null)?.incidents
  if (!Array.isArray(rows)) return []
  return rows.map(tinPhanCongTuHang).filter((t): t is TinPhanCong => t !== null)
}

/** Lần giao đang chờ đội trả lời (mới nhất), nếu có. */
export function giaoDangCho(t: Pick<TinPhanCong, 'giao'>): LanGiao | null {
  for (let i = t.giao.length - 1; i >= 0; i--) if (t.giao[i]!.ketQua === 'cho_nhan') return t.giao[i]!
  return null
}

/** Lần giao gần nhất (đội hiện tại hoặc đội cuối cùng đã thử). */
export function giaoCuoi(t: Pick<TinPhanCong, 'giao'>): LanGiao | null {
  return t.giao.at(-1) ?? null
}

// ---------- Nhóm tin theo việc cần làm ----------

export type Nhom = 'can_xu_ly' | 'cho_phan_cong' | 'cho_doi_nhan' | 'dang_cuu'

export const NHOM: Record<Nhom, { tieuDe: string; moTa: string }> = {
  can_xu_ly: { tieuDe: 'Cần xử lý', moTa: 'Luồng tự động đã dừng (không đội nào nhận, không có đội, quá hạn xác nhận)' },
  cho_phan_cong: { tieuDe: 'Chờ phân công', moTa: 'Tin mới hoặc đang tìm đội' },
  cho_doi_nhan: { tieuDe: 'Đang phân công', moTa: 'Đã giao, chờ đội nhận trong hạn' },
  dang_cuu: { tieuDe: 'Đang cứu', moTa: 'Đội đã nhận, chờ xác nhận đã cứu' },
}

/** Nhóm hiện cho từng vai, theo thứ tự trên màn hình. */
export const NHOM_THEO_VAI: Record<VaiPhanCong, Nhom[]> = {
  'dieu-phoi': ['can_xu_ly', 'cho_phan_cong', 'cho_doi_nhan', 'dang_cuu'],
  'cuu-ho': ['cho_doi_nhan', 'dang_cuu'],
}

/** Tiêu đề nhóm với đội cứu hộ: nói theo góc nhìn của đội. */
export const NHOM_CUU_HO: Partial<Record<Nhom, string>> = {
  cho_doi_nhan: 'Chờ đội bạn nhận',
  dang_cuu: 'Đội bạn đang thực hiện',
}

/**
 * Chia tin vào nhóm. `canXuLy`: mã tin có thông báo "cần xử lý" từ Centrifugo (#68); tin đó vào nhóm
 * "Cần xử lý" chừng nào còn ở tiep_nhan/dang_cuu (điều phối phân công tay / liên lạc đội thì tin rời nhóm).
 * Trong mỗi nhóm: khẩn hơn trước, cũ hơn trước.
 */
export function nhomTin<T extends TinPhanCong>(ds: T[], canXuLy: ReadonlySet<string> = new Set()): Record<Nhom, T[]> {
  const kq: Record<Nhom, T[]> = { can_xu_ly: [], cho_phan_cong: [], cho_doi_nhan: [], dang_cuu: [] }
  for (const t of sapXepTin(ds)) {
    if (canXuLy.has(t.id) && (t.status === 'tiep_nhan' || t.status === 'dang_cuu')) kq.can_xu_ly.push(t)
    else if (t.status === 'tiep_nhan') kq.cho_phan_cong.push(t)
    else if (t.status === 'phan_cong') kq.cho_doi_nhan.push(t)
    else if (t.status === 'dang_cuu') kq.dang_cuu.push(t)
  }
  return kq
}

// ---------- Workflow PhanCongCuuHo (GET /workflow/phan-cong-<id>) ----------

/** Bước của workflow (TrangThaiPhanCong.buoc, cuu_tro_workflow/workflows.py) */
export const BUOC: Record<string, string> = {
  khoi_tao: 'Khởi tạo',
  doc_tin: 'Đọc tin',
  tim_doi: 'Đang tìm đội gần nhất',
  cho_nhan: 'Chờ đội nhận',
  phan_cong_lai: 'Đang giao đội kế tiếp',
  cho_xac_nhan: 'Đội đang cứu, chờ xác nhận',
  xong: 'Đã kết thúc',
}

export const KET_QUA_WF: Record<string, string> = {
  da_dong: 'Đã cứu, tin đã đóng',
  khong_co_doi: 'Không có đội sẵn sàng trong bán kính',
  qua_han_xac_nhan: 'Quá hạn chưa xác nhận đã cứu',
  bo_qua: 'Bỏ qua (tin đã được xử lý tay)',
  het_lan_giao: 'Đã giao hết số lần, không đội nào nhận',
  da_huy: 'Điều phối đã hủy',
}

export const TRANG_THAI_WF: Record<string, string> = {
  RUNNING: 'Đang chạy',
  COMPLETED: 'Đã xong',
  FAILED: 'Lỗi',
  CANCELED: 'Đã hủy',
  TERMINATED: 'Đã dừng',
  TIMED_OUT: 'Hết thời gian',
}

export interface TrangThaiWf {
  workflowId: string
  /** Trạng thái thực thi Temporal: RUNNING, COMPLETED… */
  trangThai: string
  buoc: string
  doiId: string | null
  doiTen: string | null
  khoangCachM: number | null
  hanNhanGiay: number | null
  ketQua: string | null
  daBaoDieuPhoi: boolean
  nguoiXacNhan: string | null
  lichSu: string[]
}

/** Phản hồi GET /workflow/{workflow_id} → TrangThaiWf; dạng lạ thì null. */
export function wfTuPhanHoi(body: unknown): TrangThaiWf | null {
  if (!body || typeof body !== 'object') return null
  const b = body as Record<string, unknown>
  const ct = b.chi_tiet as Record<string, unknown> | undefined
  if (typeof b.workflow_id !== 'string' || typeof b.trang_thai !== 'string' || !ct || typeof ct.buoc !== 'string') return null
  return {
    workflowId: b.workflow_id,
    trangThai: b.trang_thai,
    buoc: ct.buoc,
    doiId: chuoi(ct.doi_id),
    doiTen: chuoi(ct.doi_ten),
    khoangCachM: so(ct.khoang_cach_m),
    hanNhanGiay: so(ct.han_nhan_giay),
    ketQua: chuoi(ct.ket_qua),
    daBaoDieuPhoi: ct.da_bao_dieu_phoi === true,
    nguoiXacNhan: chuoi((ct.xac_nhan as { nguoi?: unknown } | null)?.nguoi),
    lichSu: Array.isArray(ct.lich_su) ? ct.lich_su.filter((x): x is string => typeof x === 'string') : [],
  }
}

export function dangChay(wf: TrangThaiWf | null): wf is TrangThaiWf {
  return wf?.trangThai === 'RUNNING'
}

// ---------- Thao tác theo vai ----------

export type HanhDong = 'phan_cong' | 'doi_doi' | 'huy' | 'nhan' | 'tu_choi' | 'xac_nhan'

export const HANH_DONG: Record<HanhDong, {
  nhan: string
  /** Nút chính (cam) hay phụ (viền) */
  chinh: boolean
  /** Mở ô ghi chú + bước xác nhận trước khi gửi */
  xacNhanTruoc: boolean
  nhanGhiChu?: string
  thanhCong: string
}> = {
  phan_cong: { nhan: 'Phân công tự động', chinh: true, xacNhanTruoc: false,
    thanhCong: 'Đã khởi chạy phân công: hệ thống đang tìm đội gần nhất.' },
  doi_doi: { nhan: 'Đổi đội', chinh: false, xacNhanTruoc: true, nhanGhiChu: 'Lý do đổi đội',
    thanhCong: 'Đã đổi đội: hệ thống giao cho đội gần nhất kế tiếp.' },
  huy: { nhan: 'Hủy phân công', chinh: false, xacNhanTruoc: true, nhanGhiChu: 'Lý do hủy',
    thanhCong: 'Đã hủy phân công: tin trở về Tiếp nhận, đội được giải phóng.' },
  nhan: { nhan: 'Nhận nhiệm vụ', chinh: true, xacNhanTruoc: false,
    thanhCong: 'Đã nhận nhiệm vụ: tin chuyển sang Đang cứu. Lên đường an toàn!' },
  tu_choi: { nhan: 'Từ chối', chinh: false, xacNhanTruoc: true, nhanGhiChu: 'Lý do từ chối (vd: ca nô hỏng, quá xa)',
    thanhCong: 'Đã từ chối: hệ thống giao cho đội khác.' },
  xac_nhan: { nhan: 'Xác nhận đã cứu', chinh: true, xacNhanTruoc: true, nhanGhiChu: 'Ghi chú (vd: đã đưa người lên trạm y tế)',
    thanhCong: 'Đã xác nhận cứu xong: tin được đóng, đội trở lại sẵn sàng.' },
}

/**
 * Nút hiện cho người dùng, theo vai, trạng thái tin và bước của workflow (đúng luật của API):
 * - dieu-phoi: phân công tay khi tin tiep_nhan và không có luồng đang chạy; đổi đội (= từ chối thay đội,
 *   workflow giao đội gần nhất kế tiếp) khi chờ nhận; hủy khi đội chưa nhận; xác nhận đã cứu khi đang cứu;
 * - cuu-ho: nhận / từ chối khi chờ nhận; xác nhận đã cứu khi đang cứu.
 */
export function hanhDongDuoc(vai: VaiPhanCong | null, tin: Pick<TinKeuCuu, 'status'>, wf: TrangThaiWf | null): HanhDong[] {
  const chay = dangChay(wf)
  const buoc = chay ? wf.buoc : null
  if (vai === 'dieu-phoi') {
    const kq: HanhDong[] = []
    if (tin.status === 'tiep_nhan' && !chay) kq.push('phan_cong')
    if (buoc === 'cho_nhan') kq.push('doi_doi')
    if (buoc === 'cho_xac_nhan') kq.push('xac_nhan')
    if (chay && buoc !== 'cho_xac_nhan' && buoc !== 'xong') kq.push('huy')
    return kq
  }
  if (vai === 'cuu-ho') {
    if (buoc === 'cho_nhan') return ['nhan', 'tu_choi']
    if (buoc === 'cho_xac_nhan') return ['xac_nhan']
  }
  return []
}

/** Ghi chú gửi kèm "đổi đội": workflow ghi như một lần từ chối do điều phối gửi. */
export function ghiChuDoiDoi(lyDo: string): string {
  const s = lyDo.trim()
  return (s ? `Điều phối đổi đội: ${s}` : 'Điều phối đổi đội').slice(0, GHI_CHU_TOI_DA)
}

/** API giới hạn ghi chú / lý do 500 ký tự (pydantic XacNhanVao, HuyVao). */
export const GHI_CHU_TOI_DA = 500

// ---------- Hiển thị ----------

/** Thời gian còn lại tới hạn: "4:05", "1:02:03"; hết hạn → "Quá hạn". */
export function demNguoc(hanLuc: string, now = Date.now()): { conLaiMs: number; nhan: string; gap: boolean } {
  const ms = Date.parse(hanLuc) - now
  if (!Number.isFinite(ms) || ms <= 0) return { conLaiMs: 0, nhan: 'Quá hạn', gap: true }
  const giay = Math.ceil(ms / 1000)
  const h = Math.floor(giay / 3600)
  const m = Math.floor((giay % 3600) / 60)
  const s = String(giay % 60).padStart(2, '0')
  return { conLaiMs: ms, nhan: h > 0 ? `${h}:${String(m).padStart(2, '0')}:${s}` : `${m}:${s}`, gap: ms < 60_000 }
}

/** Tỉ lệ thời gian nhận đã trôi qua (0 → 1) cho thanh tiến độ. */
export function tiLeDaQua(giao: Pick<LanGiao, 'giaoLuc' | 'hanLuc'>, now = Date.now()): number {
  const dau = Date.parse(giao.giaoLuc)
  const cuoi = Date.parse(giao.hanLuc)
  if (!(cuoi > dau)) return 1
  return Math.min(1, Math.max(0, (now - dau) / (cuoi - dau)))
}

export function khoangCach(m: number | null): string {
  if (m === null) return 'chưa rõ'
  return m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(1).replace('.', ',')} km`
}

/** Tóm tắt một dòng cho thẻ trong hàng đợi. */
export function tomTatGiao(t: Pick<TinPhanCong, 'giao' | 'doiTen' | 'status'>): string {
  const cuoi = giaoCuoi(t)
  if (!cuoi) return t.status === 'tiep_nhan' ? 'Chưa giao đội nào' : 'Chưa có lịch sử giao'
  const ten = cuoi.doiTen ?? t.doiTen ?? 'đội khác'
  const lan = t.giao.length > 1 ? ` · lần giao ${t.giao.length}` : ''
  if (cuoi.ketQua === 'cho_nhan') return `${ten} · cách ${khoangCach(cuoi.khoangCachM)}${lan}`
  if (cuoi.ketQua === 'da_nhan') return `${ten} đã nhận${lan}`
  return `${ten}: ${KET_QUA_GIAO[cuoi.ketQua].toLowerCase()}${lan}`
}
