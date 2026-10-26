// SPDX-License-Identifier: Apache-2.0
// Một axios instance cho mọi lời gọi lõi QUA API Gateway (APISIX): /workflow/*, /graphql. Gắn Bearer token
// (tự làm mới), hết giờ 15 giây, gặp 401 thì làm mới token một lần rồi gọi lại. Không ghi log header/body
// (có token, SĐT). Kết quả trả dạng {ok, data} | {ok: false, status, detail} để hàng đợi phân loại lỗi.
import axios, { type AxiosInstance, type AxiosRequestConfig } from 'axios';
import { THOI_HAN_MS } from '@/config/env';
import { useAuthStore } from '@/stores/authStore';
import { useCaiDatStore } from '@/stores/caiDatStore';

export type KetQuaGoi<T> =
  | { ok: true; status: number; data: T; phatLai: boolean }
  | { ok: false; status: number; detail: unknown };

export interface PhuThuoc {
  gatewayUrl: () => string;
  layToken: (batBuocLamMoi?: boolean) => Promise<string | null>;
}

const phuThuocMacDinh: PhuThuoc = {
  gatewayUrl: () => useCaiDatStore.getState().gatewayUrl,
  layToken: b => useAuthStore.getState().layToken(b),
};

export function taoApi(pt: PhuThuoc = phuThuocMacDinh, adapter?: AxiosRequestConfig['adapter']) {
  const http: AxiosInstance = axios.create({ timeout: THOI_HAN_MS, adapter });

  async function goi<T>(cfg: AxiosRequestConfig, daLamMoi = false): Promise<KetQuaGoi<T>> {
    const token = await pt.layToken(daLamMoi);
    if (!token) {
      return { ok: false, status: 401, detail: null };
    }
    try {
      const r = await http.request<T>({
        ...cfg,
        baseURL: pt.gatewayUrl(),
        headers: { ...(cfg.headers as Record<string, string> | undefined), Authorization: `Bearer ${token}` },
        // Tự xử lý mọi mã HTTP
        validateStatus: () => true,
      });
      if (r.status === 401 && !daLamMoi) {
        return goi<T>(cfg, true);
      }
      if (r.status >= 200 && r.status < 300) {
        return { ok: true, status: r.status, data: r.data, phatLai: r.headers['idempotent-replayed'] === 'true' };
      }
      const body = r.data as { detail?: unknown } | null;
      return { ok: false, status: r.status, detail: body && typeof body === 'object' ? body.detail ?? null : null };
    } catch {
      // Mất mạng, hết giờ, DNS: chưa tới máy chủ
      return { ok: false, status: 0, detail: null };
    }
  }

  return { goi };
}

export const api = taoApi();
