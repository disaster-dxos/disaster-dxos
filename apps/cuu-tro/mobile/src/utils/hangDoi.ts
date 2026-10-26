// SPDX-License-Identifier: Apache-2.0
// Hàng đợi offline (D-011): mọi thao tác GHI của app (gửi kêu cứu, chuyển tin cho điều phối, ảnh hiện trường,
// vị trí đội) vào hàng đợi trước, rồi mới gửi. Logic thuần, có test (__tests__/hangDoi.test.ts); lưu trữ và gọi
// mạng ở stores/hangDoiStore.ts.
//
// Bất biến:
//   - mỗi bản ghi có MỘT khóa idempotency sinh lúc tạo, giữ nguyên qua mọi lần gửi lại (máy chủ không tạo trùng);
//   - gửi theo thứ tự tạo (FIFO); lỗi tạm thì lùi 5 s, 10 s, 20 s … tối đa 10 phút; lỗi vĩnh viễn thì dừng;
//   - ảnh chụp cho một tin kêu cứu CHƯA gửi được (cùng ở hàng đợi) chờ tin đó lên máy chủ rồi dùng mã tin thật;
//   - app bị tắt giữa lúc gửi: bản ghi "đang gửi" quay về "chờ gửi" khi mở lại (gửi lại an toàn nhờ khóa).
import type { NguonVanBan, TinKeuCuuVao } from '@/types/api';
import { taoKhoa } from './khoaIdempotency';
import type { LoiGui } from './loiApi';

export type DuLieu =
  | { loai: 'keu_cuu'; tin: TinKeuCuuVao }
  | { loai: 'chuyen_tin'; vanBan: string; nguon: NguonVanBan }
  | {
      loai: 'anh';
      /** Mã tin trên máy chủ; hoặc tuBanGhi: id bản ghi kêu cứu trong hàng đợi chưa gửi */
      incidentId?: string;
      tuBanGhi?: string;
      /** Tệp ảnh đã chép vào thư mục riêng của app (không phải tệp tạm của camera) */
      duongDan: string;
      contentType: string;
    }
  | { loai: 'vi_tri_doi'; doiId: string; lat: number; lon: number; luc: string };

export type LoaiBanGhi = DuLieu['loai'];
export type TrangThai = 'cho_gui' | 'dang_gui' | 'da_gui' | 'loi';

export interface KetQuaOk {
  phatLai: boolean;
  maTin?: string;
  maHangCho?: string;
  maAnh?: string;
}

export interface BanGhi {
  id: string;
  /** Header Idempotency-Key, không đổi khi gửi lại */
  khoa: string;
  duLieu: DuLieu;
  trangThai: TrangThai;
  /** Số lần đã gửi lỗi tạm */
  soLan: number;
  taoLuc: number;
  lanThuTiep: number;
  guiLuc?: number;
  loi?: LoiGui;
  ketQua?: KetQuaOk;
}

export type KetQuaGui = ({ ok: true } & KetQuaOk) | ({ ok: false } & LoiGui);

export const LUI_DAU_MS = 5_000;
export const LUI_TOI_DA_MS = 10 * 60_000;
/** Bản ghi đã gửi giữ lại 7 ngày để người dùng xem lịch sử, rồi tự xóa */
export const GIU_DA_GUI_MS = 7 * 24 * 3600_000;

export function taoBanGhi(duLieu: DuLieu, now: number, khoa: string = taoKhoa()): BanGhi {
  return { id: taoKhoa(), khoa, duLieu, trangThai: 'cho_gui', soLan: 0, taoLuc: now, lanThuTiep: now };
}

export function luiMs(soLan: number): number {
  return Math.min(LUI_DAU_MS * 2 ** Math.max(0, soLan - 1), LUI_TOI_DA_MS);
}

/** Mở lại app: bản ghi đang gửi dở (app bị tắt) quay về chờ gửi, gửi lại ngay (cùng khóa nên không trùng). */
export function khoiPhuc(ds: BanGhi[], now: number): BanGhi[] {
  return ds.map(b => (b.trangThai === 'dang_gui' ? { ...b, trangThai: 'cho_gui', lanThuTiep: now } : b));
}

export type ViecTiep =
  | { loai: 'gui'; banGhi: BanGhi; incidentId?: string }
  | { loai: 'loi_phu_thuoc'; banGhi: BanGhi }
  | null;

/**
 * Bản ghi kế tiếp cần gửi (FIFO, đã tới hạn thử lại). Ảnh gắn tin còn trong hàng đợi: tin đã gửi → dùng mã
 * tin thật; tin còn chờ → bỏ qua ảnh, xét bản ghi sau; tin lỗi vĩnh viễn/bị xóa → báo lỗi phụ thuộc.
 */
export function viecTiep(ds: BanGhi[], now: number): ViecTiep {
  const theoId = new Map(ds.map(b => [b.id, b]));
  const sap = [...ds].sort((a, b) => a.taoLuc - b.taoLuc);
  for (const b of sap) {
    if (b.trangThai !== 'cho_gui' || b.lanThuTiep > now) {
      continue;
    }
    if (b.duLieu.loai === 'anh' && !b.duLieu.incidentId && b.duLieu.tuBanGhi) {
      const goc = theoId.get(b.duLieu.tuBanGhi);
      if (goc?.trangThai === 'da_gui' && goc.ketQua?.maTin) {
        return { loai: 'gui', banGhi: b, incidentId: goc.ketQua.maTin };
      }
      if (!goc || goc.trangThai === 'loi') {
        return { loai: 'loi_phu_thuoc', banGhi: b };
      }
      continue;
    }
    return { loai: 'gui', banGhi: b, incidentId: b.duLieu.loai === 'anh' ? b.duLieu.incidentId : undefined };
  }
  return null;
}

/** Thời điểm sớm nhất có bản ghi tới hạn thử lại (để hẹn giờ), null nếu không có */
export function hanKeTiep(ds: BanGhi[]): number | null {
  const ds2 = ds.filter(b => b.trangThai === 'cho_gui').map(b => b.lanThuTiep);
  return ds2.length ? Math.min(...ds2) : null;
}

export function apKetQua(b: BanGhi, kq: KetQuaGui, now: number): BanGhi {
  if (kq.ok) {
    const ketQua: KetQuaOk = { phatLai: kq.phatLai, maTin: kq.maTin, maHangCho: kq.maHangCho, maAnh: kq.maAnh };
    return { ...b, trangThai: 'da_gui', guiLuc: now, loi: undefined, ketQua };
  }
  const loi: LoiGui = { loai: kq.loai, status: kq.status, khoa: kq.khoa, chiTiet: kq.chiTiet, maTinTrung: kq.maTinTrung };
  switch (loi.loai) {
    case 'tam': {
      const soLan = b.soLan + 1;
      return { ...b, trangThai: 'cho_gui', soLan, lanThuTiep: now + luiMs(soLan), loi };
    }
    case 'can_dang_nhap':
      // Không tính là một lần lỗi: đăng nhập lại xong gửi ngay
      return { ...b, trangThai: 'cho_gui', lanThuTiep: now, loi };
    case 'vinh_vien':
      return { ...b, trangThai: 'loi', loi };
  }
}

/** Người dùng bấm "Gửi lại": giữ nguyên khóa idempotency, gửi ngay. */
export function guiLai(b: BanGhi, now: number): BanGhi {
  if (b.trangThai === 'da_gui' || b.trangThai === 'dang_gui') {
    return b;
  }
  return { ...b, trangThai: 'cho_gui', lanThuTiep: now, loi: undefined };
}

export function donDaGui(ds: BanGhi[], now: number, giuMs: number = GIU_DA_GUI_MS): BanGhi[] {
  return ds.filter(b => !(b.trangThai === 'da_gui' && (b.guiLuc ?? 0) < now - giuMs));
}

export function demTheoTrangThai(ds: BanGhi[]): Record<TrangThai, number> {
  const kq: Record<TrangThai, number> = { cho_gui: 0, dang_gui: 0, da_gui: 0, loi: 0 };
  for (const b of ds) {
    kq[b.trangThai] += 1;
  }
  return kq;
}
