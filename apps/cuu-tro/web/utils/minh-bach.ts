// SPDX-License-Identifier: Apache-2.0
// Trang Minh bạch cứu trợ công khai (#63, #78): chuẩn hóa mã, URL tra cứu và ánh xạ phản hồi của API công
// khai (cuu_tro_workflow/api.py, không cần đăng nhập, không trả thông tin cá nhân) → nội dung hiển thị:
//   GET /workflow/minh-bach/xac-minh/{ma}   mã phiếu kho HOẶC mã bút toán tiền → hợp lệ hay không + bằng chứng
//   GET /workflow/minh-bach/so-cai          phiếu/bút toán đã niêm phong, mới nhất trước
//   GET /workflow/minh-bach/quy             tổng thu, tổng chi, số dư quỹ tiền cứu trợ
//   GET /ledger/verifier                    khóa công khai của sổ cái (để trình duyệt tự kiểm, utils/tu-kiem.ts)
// Hàm thuần, có test (tests/minh-bach.test.ts).

export type TrangThaiPhieu = 'da_xac_minh' | 'khong_khop' | 'chua_ghi_so' | 'khong_kiem_duoc'
export type LoaiMa = 'phieu_kho' | 'khoan_tien'

export interface BangChung {
  leaf_index: number
  leaf_hash: string
  tree_size: number
  inclusion_proof: string[]
  /** Checkpoint đã ký nguyên văn (signed note) */
  checkpoint: string
}

export interface KetQuaXacMinh {
  hop_le: boolean
  loai: LoaiMa
  ma: string
  trang_thai: TrangThaiPhieu
  chi_tiet: string[]
  /** Bản ghi công khai đã băm: chỉ chuỗi hoặc null, không có người lập */
  ban_ghi_chuan_hoa: Record<string, string | null>
  sha256: string
  /** Tên hàng, kho, điểm nhận… hiện kèm, KHÔNG nằm trong bản ghi đã băm */
  hien_thi: Record<string, string | null>
  so_cai: {
    index: number | null
    leaf_hash: string | null
    logged_at: string | null
    checkpoint: { origin: string; tree_size: number; root_hash: string } | null
    la: string | null
  }
  bang_chung: BangChung | null
  tu_kiem_chung: string
}

/** Kết quả máy chủ: nhãn, màu Nuxt UI và biểu tượng (không chỉ dựa vào màu: biểu tượng khiên khác nhau). */
export const TRANG_THAI_PHIEU = {
  da_xac_minh: { nhan: 'Đã xác minh trên sổ cái', mau: 'success', icon: 'i-lucide-shield-check' },
  khong_khop: { nhan: 'Không khớp sổ cái', mau: 'error', icon: 'i-lucide-shield-x' },
  chua_ghi_so: { nhan: 'Chưa ghi lên sổ cái', mau: 'warning', icon: 'i-lucide-shield-alert' },
  khong_kiem_duoc: { nhan: 'Tạm thời không kiểm được', mau: 'neutral', icon: 'i-lucide-shield-question' },
} as const satisfies Record<TrangThaiPhieu, { nhan: string; mau: string; icon: string }>

export const LOAI_MA: Record<LoaiMa, string> = { phieu_kho: 'Phiếu kho', khoan_tien: 'Bút toán tiền' }

export const CHIEU: Record<string, string> = {
  nhap: 'Phiếu nhập kho', xuat: 'Phiếu xuất kho', thu: 'Khoản thu', chi: 'Khoản chi',
}

export const HANG_MUC: Record<string, string> = {
  ung_ho: 'Ủng hộ', ngan_sach: 'Ngân sách', mua_hang: 'Mua hàng cứu trợ', ho_tro_ho_dan: 'Hỗ trợ hộ dân',
  van_chuyen: 'Vận chuyển', khac: 'Khác',
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/

/** Bỏ khoảng trắng (kể cả giữa mã khi gõ tay hoặc dán), chữ thường. */
export function chuanHoaMa(ma: string): string {
  return ma.replace(/\s+/g, '').toLowerCase()
}

/** Mã phiếu/bút toán là UUID (in dưới mã QR). Kiểm trước khi gọi API để báo lỗi ngay. */
export function laMaHopLe(ma: string): boolean {
  return UUID.test(chuanHoaMa(ma))
}

const goc = (gatewayUrl: string) => gatewayUrl.replace(/\/+$/, '')

export function urlXacMinh(gatewayUrl: string, ma: string): string {
  return `${goc(gatewayUrl)}/workflow/minh-bach/xac-minh/${encodeURIComponent(chuanHoaMa(ma))}`
}

export function urlKhoaSoCai(gatewayUrl: string): string {
  return `${goc(gatewayUrl)}/ledger/verifier`
}

export function urlSoCai(gatewayUrl: string, gioiHan = 8): string {
  return `${goc(gatewayUrl)}/workflow/minh-bach/so-cai?gioi_han=${gioiHan}`
}

export function urlQuy(gatewayUrl: string): string {
  return `${goc(gatewayUrl)}/workflow/minh-bach/quy`
}

export type KetQuaTra = { ok: true; kq: KetQuaXacMinh } | { ok: false; loi: string }

function laBangChung(b: unknown): b is BangChung {
  const o = b as Record<string, unknown> | null
  return !!o && Number.isInteger(o.leaf_index) && typeof o.leaf_hash === 'string' && Number.isInteger(o.tree_size)
    && Array.isArray(o.inclusion_proof) && o.inclusion_proof.every((h) => typeof h === 'string') && typeof o.checkpoint === 'string'
}

function laKetQua(b: unknown): b is KetQuaXacMinh {
  if (!b || typeof b !== 'object') return false
  const o = b as Record<string, unknown>
  return typeof o.trang_thai === 'string' && o.trang_thai in TRANG_THAI_PHIEU
    && (o.loai === 'phieu_kho' || o.loai === 'khoan_tien') && typeof o.ma === 'string'
    && !!o.ban_ghi_chuan_hoa && typeof o.ban_ghi_chuan_hoa === 'object' && !!o.hien_thi && !!o.so_cai
    && Array.isArray(o.chi_tiet) && (o.bang_chung === null || o.bang_chung === undefined || laBangChung(o.bang_chung))
}

/** Ánh xạ mã HTTP + thân phản hồi của API → kết quả để hiển thị hoặc câu lỗi tiếng Việt. */
export function docPhanHoi(status: number, body: unknown): KetQuaTra {
  if (status === 404) return { ok: false, loi: 'Không tìm thấy phiếu hay bút toán có mã này. Kiểm tra lại mã trên phiếu.' }
  if (status === 429) return { ok: false, loi: 'Tra cứu quá nhanh. Chờ một phút rồi thử lại.' }
  if (status >= 500) return { ok: false, loi: `Máy chủ đang gặp lỗi (${status}). Thử lại sau ít phút.` }
  if (status !== 200) return { ok: false, loi: `Máy chủ trả lỗi ${status}.` }
  if (!laKetQua(body)) return { ok: false, loi: 'Phản hồi của máy chủ không đúng dạng. Thử lại sau.' }
  return { ok: true, kq: { ...body, bang_chung: body.bang_chung ?? null } }
}

/** Lỗi khi gọi fetch: mất mạng (TypeError) có câu riêng. */
export function loiKhiTra(e: unknown): string {
  if (e instanceof TypeError) return 'Không kết nối được máy chủ. Kiểm tra mạng rồi thử lại.'
  return e instanceof Error ? e.message : String(e)
}

/** Dòng tiêu đề lớn của kết quả: "250 thùng Nước uống" hoặc "50.000.000 đ". */
export function tieuDeKetQua(kq: KetQuaXacMinh): { so: string; donVi: string; noiDung: string } {
  const b = kq.ban_ghi_chuan_hoa
  if (kq.loai === 'khoan_tien') {
    return { so: dinhDangSo(b.amount), donVi: kq.hien_thi.don_vi === 'VND' || !kq.hien_thi.don_vi ? 'đ' : kq.hien_thi.don_vi, noiDung: '' }
  }
  return { so: dinhDangSo(b.quantity), donVi: kq.hien_thi.don_vi ?? '', noiDung: kq.hien_thi.mat_hang ?? '' }
}

export function dinhDangSo(s: string | null | undefined): string {
  const n = Number(s)
  return s === null || s === undefined || s === '' || !Number.isFinite(n) ? '—' : n.toLocaleString('vi-VN')
}

/** Một mục của danh sách sổ cái gần đây */
export interface MucSoCai {
  loai: LoaiMa
  ma: string
  chieu: string
  so_luong: string
  don_vi: string
  noi_dung: string | null
  diem_nhan: string | null
  thoi_diem: string
  ledger_index: number
}

export function mucSoCaiTuPhanHoi(body: unknown): MucSoCai[] {
  const ds = (body as { muc?: unknown } | null)?.muc
  if (!Array.isArray(ds)) return []
  return ds.filter((m): m is MucSoCai => {
    const o = m as Record<string, unknown> | null
    return !!o && (o.loai === 'phieu_kho' || o.loai === 'khoan_tien') && typeof o.ma === 'string' && laMaHopLe(o.ma)
      && typeof o.chieu === 'string' && typeof o.so_luong === 'string' && Number.isInteger(o.ledger_index)
  })
}

export interface TongQuy { tong_thu: string; tong_chi: string; so_du: string; don_vi: string }

export function quyTuPhanHoi(body: unknown): TongQuy | null {
  const o = body as Record<string, unknown> | null
  if (!o || typeof o.tong_thu !== 'string' || typeof o.tong_chi !== 'string' || typeof o.so_du !== 'string') return null
  return { tong_thu: o.tong_thu, tong_chi: o.tong_chi, so_du: o.so_du, don_vi: typeof o.don_vi === 'string' ? o.don_vi : 'VND' }
}

/** Mô tả ngắn một mục sổ cái: "Xuất 40 thùng Mì tôm → Trường THCS" / "Thu 50.000.000 đ · Ủng hộ" */
export function moTaMuc(m: MucSoCai): string {
  const chieu = { nhap: 'Nhập', xuat: 'Xuất', thu: 'Thu', chi: 'Chi' }[m.chieu] ?? m.chieu
  if (m.loai === 'khoan_tien') return `${chieu} ${dinhDangSo(m.so_luong)} đ · ${HANG_MUC[m.noi_dung ?? ''] ?? m.noi_dung ?? ''}`.trim()
  return `${chieu} ${dinhDangSo(m.so_luong)} ${m.don_vi} ${m.noi_dung ?? ''}${m.diem_nhan ? ` → ${m.diem_nhan}` : ''}`.trim()
}
