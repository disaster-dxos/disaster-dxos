// SPDX-License-Identifier: Apache-2.0
// Khóa idempotency của mỗi bản ghi trong hàng đợi offline: UUID v4 từ crypto.getRandomValues (polyfill
// react-native-get-random-values nạp ở index.js). Sinh MỘT lần lúc bản ghi vào hàng đợi, gửi lại bao nhiêu lần
// cũng dùng đúng khóa đó trong header Idempotency-Key: máy chủ trả lại kết quả cũ, không tạo trùng.

const HEX = Array.from({ length: 256 }, (_, i) => i.toString(16).padStart(2, '0'));

export function taoKhoa(): string {
  const b = new Uint8Array(16);
  crypto.getRandomValues(b);
  b[6] = ((b[6] ?? 0) % 16) + 0x40; // phiên bản 4: 4 bit cao = 0100
  b[8] = ((b[8] ?? 0) % 64) + 0x80; // biến thể RFC 4122: 2 bit cao = 10
  const h = Array.from(b, x => HEX[x] ?? '00');
  return `${h.slice(0, 4).join('')}-${h.slice(4, 6).join('')}-${h.slice(6, 8).join('')}-${h
    .slice(8, 10)
    .join('')}-${h.slice(10, 16).join('')}`;
}

/** Khóa đúng dạng máy chủ nhận (8–128 ký tự chữ, số, '-', '_'; cuu_tro_workflow/idempotency.py). */
export function khoaHopLe(k: string): boolean {
  return /^[A-Za-z0-9_-]{8,128}$/.test(k);
}
