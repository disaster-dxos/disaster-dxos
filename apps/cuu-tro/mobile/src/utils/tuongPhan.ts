// SPDX-License-Identifier: Apache-2.0
// Tỷ lệ tương phản WCAG 2.2 giữa hai màu đặc (#RGB hoặc #RRGGBB), dùng cho kiểm thử bảng màu (#113).

function kenh(h: string, i: number): number {
  const c = parseInt(h.slice(i, i + 2), 16) / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

function doChoi(hex: string): number {
  const m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(hex)?.[1];
  if (!m) {
    throw new Error(`mã màu không hợp lệ: ${hex}`);
  }
  const h = m.length === 3 ? m.replace(/./g, c => c + c) : m;
  return 0.2126 * kenh(h, 0) + 0.7152 * kenh(h, 2) + 0.0722 * kenh(h, 4);
}

/** (L sáng + 0,05) / (L tối + 0,05), từ 1 đến 21 */
export function tyLeTuongPhan(a: string, b: string): number {
  const la = doChoi(a);
  const lb = doChoi(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}
