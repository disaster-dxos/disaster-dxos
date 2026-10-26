// SPDX-License-Identifier: Apache-2.0
/** Chạy promise không chờ kết quả (sự kiện giao diện, hẹn giờ); lỗi đã được xử lý bên trong nên bỏ qua. */
export function boQua(p: Promise<unknown>): void {
  p.catch(() => undefined);
}
