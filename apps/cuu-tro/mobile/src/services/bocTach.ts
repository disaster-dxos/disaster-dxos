// SPDX-License-Identifier: Apache-2.0
// AI bóc tách tin nhắn tự do (#102) để ĐIỀN SẴN form: gọi trực tiếp (cần mạng), không qua hàng đợi, không tạo
// gì trên máy chủ. Người dùng soát lại form rồi mới gửi (HITL). Không có mạng thì "Chuyển cho điều phối duyệt"
// (bản ghi chuyen_tin trong hàng đợi, #104).
import type { BocTachKetQua, NguonVanBan } from '@/types/api';
import { phanLoaiLoi, type LoiGui } from '@/utils/loiApi';
import { api } from './api';

export async function bocTach(
  vanBan: string,
  nguon: NguonVanBan,
  goi = api.goi,
): Promise<{ ok: true; kq: BocTachKetQua } | { ok: false; loi: LoiGui }> {
  const r = await goi<BocTachKetQua>({
    method: 'POST',
    url: '/workflow/ai/boc-tach',
    data: { van_ban: vanBan, nguon },
    headers: { 'Content-Type': 'application/json' },
    // Mô hình chạy CPU có thể mất ~10–20 giây (#102)
    timeout: 120_000,
  });
  return r.ok ? { ok: true, kq: r.data } : { ok: false, loi: phanLoaiLoi(r.status, r.detail) };
}
