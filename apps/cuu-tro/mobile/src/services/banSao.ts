// SPDX-License-Identifier: Apache-2.0
// Bản sao dữ liệu ĐỌC của màn Hiện trường (tin của tôi, đội của tôi) trên máy (#113): đội cứu hộ hay tắt máy cho
// đỡ pin rồi mở lại ở chỗ mất sóng; không có bản sao thì danh sách nhiệm vụ trống và không cập nhật được vị trí đội
// (cần mã đội). Lưu MÃ HÓA trong Keychain/Keystore như hàng đợi (có địa chỉ, mô tả), gắn với người dùng + vai:
// người khác đăng nhập trên cùng máy không đọc được bản của người trước. Bản quá 7 ngày bị bỏ. Màn hình luôn hiện
// mốc "cập nhật lúc" của dữ liệu để không ai tưởng dữ liệu cũ là mới.
import * as Keychain from 'react-native-keychain';

const TIEN_TO = 'org.disasterdxos.cuutro.ban-sao';
const PHIEN_BAN = 1;
export const TUOI_TOI_DA_MS = 7 * 24 * 3600 * 1000;

export interface KhoBanSao {
  doc: (ten: string) => Promise<string | null>;
  ghi: (ten: string, noiDung: string) => Promise<void>;
}

export const khoKeychain: KhoBanSao = {
  doc: async ten => {
    const c = await Keychain.getGenericPassword({ service: `${TIEN_TO}.${ten}` });
    return c ? c.password : null;
  },
  ghi: async (ten, noiDung) => {
    await Keychain.setGenericPassword('ban-sao', noiDung, {
      service: `${TIEN_TO}.${ten}`,
      accessible: Keychain.ACCESSIBLE.AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY,
    });
  },
};

let kho: KhoBanSao = khoKeychain;

/** Chỉ dùng trong kiểm thử */
export function datKhoBanSao(k: KhoBanSao): void {
  kho = k;
}

interface Goi<T> {
  v: number;
  chu: string;
  luc: number;
  duLieu: T;
}

/** Bản sao của `ten` thuộc `chu` (người dùng + vai), hoặc null nếu không có, của người khác, hỏng, quá cũ. */
export async function docBanSao<T>(ten: string, chu: string, now = Date.now()): Promise<{ duLieu: T; luc: number } | null> {
  try {
    const s = await kho.doc(ten);
    if (!s) {
      return null;
    }
    const g = JSON.parse(s) as Partial<Goi<T>>;
    if (g.v !== PHIEN_BAN || g.chu !== chu || typeof g.luc !== 'number' || g.duLieu === undefined) {
      return null;
    }
    if (now - g.luc > TUOI_TOI_DA_MS || g.luc > now + 5 * 60_000) {
      return null;
    }
    return { duLieu: g.duLieu, luc: g.luc };
  } catch {
    return null;
  }
}

/** Ghi đè bản sao; lỗi lưu trữ không làm hỏng màn hình (chỉ mất bản sao). */
export async function ghiBanSao<T>(ten: string, chu: string, duLieu: T, luc: number): Promise<void> {
  const g: Goi<T> = { v: PHIEN_BAN, chu, luc, duLieu };
  try {
    await kho.ghi(ten, JSON.stringify(g));
  } catch {
    // Keychain đầy hoặc bị khóa: bỏ qua, lần tải sau ghi lại
  }
}
