// SPDX-License-Identifier: Apache-2.0
// Kiểu dữ liệu của API ứng dụng qua gateway (apps/cuu-tro/README.md): /workflow/keu-cuu, /workflow/ai/boc-tach,
// /workflow/tai-len/su-co/{id}/anh, GraphQL /graphql. Tên trường giữ nguyên như API (snake_case).

export type MucKhan = 'khan_cap' | 'cao' | 'trung_binh' | 'thap';
export const DS_MUC_KHAN: readonly MucKhan[] = ['khan_cap', 'cao', 'trung_binh', 'thap'];

export type TrangThaiTin = 'tiep_nhan' | 'phan_cong' | 'dang_cuu' | 'da_cuu' | 'dong';

export type NguonVanBan = 'sms' | 'zalo' | 'dien_thoai' | 'mang_xa_hoi' | 'van_ban';
export const DS_NGUON_VAN_BAN: readonly NguonVanBan[] = ['sms', 'zalo', 'dien_thoai', 'mang_xa_hoi', 'van_ban'];

export type VaiTro = 'dieu-phoi' | 'cuu-ho' | 'tinh-nguyen';

/** Body POST /workflow/keu-cuu (Poka-yoke ở API, #66) */
export interface TinKeuCuuVao {
  lat: number;
  lon: number;
  reporter_phone: string;
  description: string;
  urgency?: MucKhan;
  people_count?: number;
  address_text?: string;
  reporter_name?: string;
  source?: 'app';
}

export interface TinKeuCuuKetQua {
  id: string;
  status: TrangThaiTin;
  urgency: MucKhan;
  people_count: number;
  lat: number;
  lon: number;
  created_at: string;
}

export interface LoiTruongApi {
  truong: string;
  thong_bao: string;
}

/** `detail` lỗi 409/422 của API ứng dụng */
export interface ChiTietLoiApi {
  ma?: string;
  thong_bao?: string;
  loi?: LoiTruongApi[];
  incident_id?: string;
}

/** Phản hồi POST /workflow/ai/boc-tach (#102); `hang_cho` khi vao_hang_cho (#104) */
export interface BocTachKetQua {
  tin_keu_cuu: Partial<Omit<TinKeuCuuVao, 'source'>> & { source?: string };
  de_xuat?: { nhu_cau?: string[] };
  poka_yoke: { hop_le: boolean; loi?: LoiTruongApi[]; tin_trung?: { incident_id: string; thong_bao: string } | null };
  ai: { nha_cung_cap: string; mo_hinh: string | null; du_phong: boolean };
  canh_bao?: string[];
  hang_cho?: { id: string; trang_thai: string };
}

export interface AnhKetQua {
  id: string;
  incident_id: string;
  size_bytes: number;
}

/** Tin kêu cứu đọc qua GraphQL (Hasura lọc theo vai: tinh-nguyen tin mình tạo, cuu-ho tin của đội mình) */
export interface TinCuaToi {
  id: string;
  status: TrangThaiTin;
  urgency: MucKhan;
  description: string;
  address_text: string | null;
  people_count: number;
  created_at: string;
  /** [kinh độ, vĩ độ] */
  toaDo: [number, number] | null;
}

export interface DoiCuaToi {
  id: string;
  name: string;
  status: string;
  location_updated_at: string | null;
}
