// SPDX-License-Identifier: Apache-2.0
// Thông báo realtime cho người điều phối (#68): hàm thuần, có test (tests/thong-bao.test.ts).
// Sự kiện đến từ Centrifugo (kênh server-side "dieu-phoi"), do cầu nối NATS → Centrifugo của backend
// đẩy lên (apps/cuu-tro/workflow/cuu_tro_workflow/thong_bao.py). Payload không có SĐT hay tên.
import { MUC_KHAN, type MucKhan } from './tin-gia'

export type LoaiThongBao = 'can_xu_ly' | 'tin_moi' | 'canh_bao'
export type MucDo = 'khan' | 'canh-bao' | 'thong-tin'

export interface ThongBao {
  id: string
  loai: LoaiThongBao
  tieuDe: string
  noiDung: string
  mucDo: MucDo
  /** Thời điểm sự kiện (ISO 8601); thiếu thì lấy lúc nhận */
  luc: string
  incidentId?: string
}

export const DUONG_WS = '/realtime/websocket'
export const DUONG_TOKEN = '/workflow/realtime/token'
export const SO_THONG_BAO_TOI_DA = 30

const LY_DO: Record<string, string> = {
  het_lan_giao: 'Đã giao hết số lần, không đội nào nhận',
  khong_co_doi: 'Không có đội sẵn sàng trong bán kính',
  qua_han_xac_nhan: 'Đội chưa xác nhận đã cứu sau hạn',
}

const MUC_NUOC: Record<string, string> = { canh_bao: 'Cảnh báo', nguy_hiem: 'Nguy hiểm' }

/** URL WebSocket của Centrifugo qua API Gateway: http(s)://gateway → ws(s)://gateway/realtime/websocket */
export function wsUrl(gatewayUrl: string): string {
  const u = new URL(gatewayUrl)
  if (u.protocol !== 'http:' && u.protocol !== 'https:') throw new Error(`gatewayUrl không hợp lệ: ${gatewayUrl}`)
  u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:'
  u.pathname = DUONG_WS
  u.search = ''
  u.hash = ''
  return u.toString()
}

export function tokenUrl(gatewayUrl: string): string {
  return new URL(DUONG_TOKEN, gatewayUrl).toString()
}

function chuoi(v: unknown): string | undefined {
  return typeof v === 'string' && v.length > 0 ? v : undefined
}

function soNgan(v: unknown): string | undefined {
  return typeof v === 'number' && Number.isFinite(v) ? String(Math.round(v * 100) / 100) : undefined
}

/** Mã ngắn của tin để người điều phối đọc: 8 ký tự đầu của UUID */
export function maNgan(id: string): string {
  return id.slice(0, 8)
}

function nhanMucKhan(u: unknown): string {
  return MUC_KHAN[u as MucKhan]?.nhan ?? 'Chưa rõ'
}

/** Dữ liệu một publication → thông báo hiển thị; dữ liệu lạ/thiếu trường thì trả null (bỏ qua). */
export function docThongBao(data: unknown, bayGio = new Date()): ThongBao | null {
  if (!data || typeof data !== 'object') return null
  const d = data as Record<string, unknown>
  const id = chuoi(d.id)
  if (!id) return null
  const luc = chuoi(d.luc) ?? chuoi(d.thoi_diem) ?? bayGio.toISOString()
  switch (d.loai) {
    case 'can_xu_ly': {
      const incidentId = chuoi(d.incident_id)
      if (!incidentId) return null
      const lyDo = chuoi(d.ly_do)
      return {
        id, loai: 'can_xu_ly', luc, incidentId,
        tieuDe: `Cần xử lý: tin ${maNgan(incidentId)}`,
        noiDung: `${(lyDo && LY_DO[lyDo]) ?? chuoi(d.mo_ta) ?? 'Luồng phân công tự động đã dừng'} · mức ${nhanMucKhan(d.urgency)}`,
        mucDo: 'khan',
      }
    }
    case 'tin_moi': {
      const incidentId = chuoi(d.incident_id)
      if (!incidentId) return null
      return {
        id, loai: 'tin_moi', luc, incidentId,
        tieuDe: `Tin kêu cứu mới ${maNgan(incidentId)}`,
        noiDung: `Mức ${nhanMucKhan(d.urgency)} · đang tìm đội gần nhất`,
        mucDo: d.urgency === 'khan_cap' ? 'khan' : 'thong-tin',
      }
    }
    case 'canh_bao': {
      const maTram = chuoi(d.ma_tram)
      if (!maTram) return null
      const giaTri = soNgan(d.gia_tri)
      const nguong = soNgan(d.nguong)
      const donVi = chuoi(d.don_vi) ?? ''
      return {
        id, loai: 'canh_bao', luc,
        tieuDe: `${MUC_NUOC[d.muc as string] ?? 'Cảnh báo'}: ${chuoi(d.ten_tram) ?? maTram}`,
        noiDung: giaTri
          ? `Đo được ${giaTri} ${donVi}${nguong ? `, ngưỡng ${nguong} ${donVi}` : ''}`.trim()
          : 'Trạm đo vượt ngưỡng',
        mucDo: d.muc === 'nguy_hiem' ? 'khan' : 'canh-bao',
      }
    }
    default:
      return null
  }
}

/** Thêm thông báo mới lên đầu, bỏ trùng theo id (kết nối lại có thể nhận lại tin), giữ tối đa n. */
export function themThongBao(ds: ThongBao[], tb: ThongBao, n = SO_THONG_BAO_TOI_DA): ThongBao[] {
  if (ds.some((x) => x.id === tb.id)) return ds
  return [tb, ...ds].slice(0, n)
}
