// SPDX-License-Identifier: Apache-2.0
// Poka-yoke phía app cho tin kêu cứu, cùng luật với API (apps/cuu-tro/workflow/cuu_tro_workflow/keu_cuu.py):
// báo lỗi ngay trên máy khi chưa có mạng, trước khi tin vào hàng đợi. API vẫn kiểm lại (vùng phục vụ, tin trùng).
// Lỗi trả về KHÓA i18n (đổi ngôn ngữ giữa chừng thì câu lỗi đổi theo), không trả câu chữ.
import type { MucKhan, TinKeuCuuVao } from '@/types/api';

export const MO_TA_TOI_DA = 500;
export const DIA_CHI_TOI_DA = 300;
export const TEN_TOI_DA = 100;
export const SO_NGUOI_TOI_DA = 10_000;
export const VAN_BAN_TOI_DA = 2000;

export interface LoiForm {
  truong: keyof FormKeuCuu | 'body';
  khoa: string;
  thamSo?: Record<string, number | string>;
}

/** Ô nhập của form kêu cứu: chuỗi như người dùng gõ */
export interface FormKeuCuu {
  sdt: string;
  ten: string;
  soNguoi: string;
  mucKhan: MucKhan;
  moTa: string;
  diaChi: string;
  lat: number | null;
  lon: number | null;
}

export const FORM_TRONG: FormKeuCuu = {
  sdt: '',
  ten: '',
  soNguoi: '1',
  mucKhan: 'trung_binh',
  moTa: '',
  diaChi: '',
  lat: null,
  lon: null,
};

// Cùng tập ký tự điều khiển API từ chối (keu_cuu._KY_TU_DIEU_KHIEN): cố ý so khớp ký tự điều khiển
// eslint-disable-next-line no-control-regex
const DIEU_KHIEN = /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/;

/** Bỏ dấu cách, chấm, gạch, ngoặc; +84/84 → 0. Trả null nếu không phải di động Việt Nam 10 số. */
export function chuanHoaSdt(s: string): string | null {
  let x = s.replace(/[\s.\-()]/g, '');
  if (x.startsWith('+84')) {
    x = '0' + x.slice(3);
  } else if (x.startsWith('84') && x.length === 11) {
    x = '0' + x.slice(2);
  }
  return /^0[35789]\d{8}$/.test(x) ? x : null;
}

/** "16,0712" hay "16.0712" → số; không đọc được → NaN */
export function docSo(s: string): number {
  const t = s.trim().replace(/^(-?\d+),(\d+)$/, '$1.$2');
  return /^-?\d+(\.\d+)?$/.test(t) ? Number(t) : Number.NaN;
}

/** Kiểm form; hợp lệ thì trả body POST /workflow/keu-cuu đã chuẩn hóa. */
export function kiemTraKeuCuu(f: FormKeuCuu): { body: TinKeuCuuVao | null; loi: LoiForm[] } {
  const loi: LoiForm[] = [];
  if (f.lat === null || f.lon === null) {
    loi.push({ truong: 'lat', khoa: 'loi.thieuViTri' });
  } else if (!(f.lat >= -90 && f.lat <= 90 && f.lon >= -180 && f.lon <= 180)) {
    loi.push({ truong: 'lat', khoa: 'loi.viTriSai' });
  }
  const sdt = f.sdt.trim() ? chuanHoaSdt(f.sdt) : null;
  if (!f.sdt.trim()) {
    loi.push({ truong: 'sdt', khoa: 'loi.thieuSdt' });
  } else if (sdt === null) {
    loi.push({ truong: 'sdt', khoa: 'loi.sdtSai' });
  }
  const moTa = f.moTa.trim();
  if (!moTa) {
    loi.push({ truong: 'moTa', khoa: 'loi.thieuMoTa' });
  }
  const dai: Array<[keyof FormKeuCuu, string, number]> = [
    ['moTa', moTa, MO_TA_TOI_DA],
    ['diaChi', f.diaChi.trim(), DIA_CHI_TOI_DA],
    ['ten', f.ten.trim(), TEN_TOI_DA],
  ];
  for (const [truong, v, toiDa] of dai) {
    if (v.length > toiDa) {
      loi.push({ truong, khoa: 'loi.quaDai', thamSo: { toiDa } });
    } else if (DIEU_KHIEN.test(v)) {
      loi.push({ truong, khoa: 'loi.kyTuLa' });
    }
  }
  const soNguoi = docSo(f.soNguoi || '1');
  if (!Number.isInteger(soNguoi) || soNguoi < 1 || soNguoi > SO_NGUOI_TOI_DA) {
    loi.push({ truong: 'soNguoi', khoa: 'loi.soNguoiSai', thamSo: { toiDa: SO_NGUOI_TOI_DA } });
  }
  if (loi.length || f.lat === null || f.lon === null || sdt === null) {
    return { body: null, loi };
  }
  const body: TinKeuCuuVao = {
    lat: Math.round(f.lat * 1e6) / 1e6,
    lon: Math.round(f.lon * 1e6) / 1e6,
    reporter_phone: sdt,
    description: moTa,
    urgency: f.mucKhan,
    people_count: soNguoi,
    source: 'app',
  };
  if (f.diaChi.trim()) {
    body.address_text = f.diaChi.trim();
  }
  if (f.ten.trim()) {
    body.reporter_name = f.ten.trim();
  }
  return { body, loi };
}

/** Đề xuất của AI bóc tách (#102) → form (người dùng soát lại rồi mới gửi). Trường AI không thấy giữ giá trị cũ. */
export function formTuDeXuat(
  cu: FormKeuCuu,
  d: { lat?: number; lon?: number; reporter_phone?: string; reporter_name?: string; address_text?: string;
    people_count?: number; urgency?: MucKhan; description?: string },
): FormKeuCuu {
  return {
    sdt: d.reporter_phone ?? cu.sdt,
    ten: d.reporter_name ?? cu.ten,
    soNguoi: d.people_count !== undefined ? String(d.people_count) : cu.soNguoi,
    mucKhan: d.urgency ?? cu.mucKhan,
    moTa: d.description ?? cu.moTa,
    diaChi: d.address_text ?? cu.diaChi,
    lat: d.lat ?? cu.lat,
    lon: d.lon ?? cu.lon,
  };
}

/** Lỗi theo trường của API (422) → trường của form */
export const TRUONG_API_SANG_FORM: Record<string, keyof FormKeuCuu> = {
  lat: 'lat',
  lon: 'lat',
  reporter_phone: 'sdt',
  reporter_name: 'ten',
  people_count: 'soNguoi',
  urgency: 'mucKhan',
  description: 'moTa',
  address_text: 'diaChi',
};
