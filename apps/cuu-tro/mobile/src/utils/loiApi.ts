// SPDX-License-Identifier: Apache-2.0
// Phân loại kết quả gửi một bản ghi lên máy chủ, quyết định hàng đợi làm gì tiếp:
//   tam          lỗi tạm (mất mạng, hết giờ, 5xx, 429): giữ bản ghi, gửi lại sau (lùi dần), cùng khóa idempotency
//   can_dang_nhap 401: chờ người dùng đăng nhập lại rồi gửi tiếp
//   vinh_vien    gửi lại cũng vậy (422 dữ liệu sai, 409 tin trùng, 403, 404…): dừng, báo người dùng sửa/xóa
import type { ChiTietLoiApi } from '@/types/api';

export type LoaiLoi = 'tam' | 'can_dang_nhap' | 'vinh_vien';

export interface LoiGui {
  loai: LoaiLoi;
  /** 0 = không tới được máy chủ */
  status: number;
  /** Khóa i18n câu báo lỗi */
  khoa: string;
  /** Câu lỗi tiếng Việt của API (422 theo trường, 409 tin trùng): hiện thêm cho người dùng */
  chiTiet?: string;
  /** 409 tin trùng: mã tin kêu cứu đang mở của cùng số điện thoại */
  maTinTrung?: string;
}

function docChiTiet(detail: unknown): ChiTietLoiApi | null {
  return detail && typeof detail === 'object' ? (detail as ChiTietLoiApi) : null;
}

export function phanLoaiLoi(status: number, detail: unknown): LoiGui {
  const d = docChiTiet(detail);
  const tb = typeof detail === 'string' ? detail : d?.thong_bao;
  if (status === 0) {
    return { loai: 'tam', status, khoa: 'loi.mang' };
  }
  if (status === 401) {
    return { loai: 'can_dang_nhap', status, khoa: 'loi.hetPhien' };
  }
  if (status === 429) {
    return { loai: 'tam', status, khoa: 'loi.quaNhanh' };
  }
  if (status === 408 || status === 425 || status >= 500) {
    return { loai: 'tam', status, khoa: 'loi.mayChu' };
  }
  if (status === 409 && d?.ma === 'tin_trung') {
    return { loai: 'vinh_vien', status, khoa: 'loi.tinTrung', chiTiet: tb, maTinTrung: d.incident_id };
  }
  if (status === 422) {
    const dau = d?.loi?.[0]?.thong_bao;
    return { loai: 'vinh_vien', status, khoa: 'loi.duLieuSai', chiTiet: dau ?? tb };
  }
  const khoa: Record<number, string> = {
    403: 'loi.khongQuyen',
    404: 'loi.khongCo',
    409: 'loi.xungDot',
    413: 'loi.quaLon',
    415: 'loi.dinhDangAnh',
  };
  return { loai: 'vinh_vien', status, khoa: khoa[status] ?? 'loi.khac', chiTiet: tb };
}
