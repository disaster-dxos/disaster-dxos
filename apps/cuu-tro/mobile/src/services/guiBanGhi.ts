// SPDX-License-Identifier: Apache-2.0
// Gửi MỘT bản ghi của hàng đợi lên máy chủ qua gateway, kèm header Idempotency-Key = khóa của bản ghi
// (máy chủ: cuu_tro_workflow/idempotency.py). Gửi lại cùng khóa → máy chủ trả kết quả cũ (header
// Idempotent-Replayed), không tạo tin/ảnh/mục hàng chờ thứ hai.
//   keu_cuu     POST /workflow/keu-cuu
//   chuyen_tin  POST /workflow/ai/boc-tach {vao_hang_cho: true} (hàng chờ duyệt HITL của điều phối, #104)
//   anh         POST /workflow/tai-len/su-co/{id}/anh, body = tệp ảnh (đọc thẳng từ tệp, không qua bộ nhớ JS)
//   vi_tri_doi  GraphQL update_rescue_teams (vai cuu-ho; tự idempotent: chỉ ghi khi mới hơn vị trí đang có)
import ReactNativeBlobUtil from 'react-native-blob-util';
import { THOI_HAN_MS } from '@/config/env';
import type { BocTachKetQua, TinKeuCuuKetQua } from '@/types/api';
import type { BanGhi, KetQuaGui } from '@/utils/hangDoi';
import { phanLoaiLoi } from '@/utils/loiApi';
import { useAuthStore } from '@/stores/authStore';
import { useCaiDatStore } from '@/stores/caiDatStore';
import { api, tokenHoacLoi, type KetQuaGoi } from './api';
import { conTrenMay, xoaTep } from './anhCucBo';
import { M_VI_TRI_DOI, M_VI_TRI_DOI_DAU, Q_MOC_VI_TRI_DOI } from './graphql';

const IDEM = 'Idempotency-Key';

function loi(r: { status: number; detail: unknown }): KetQuaGui {
  return { ok: false, ...phanLoaiLoi(r.status, r.detail) };
}

export interface PhuThuocGui {
  goi: typeof api.goi;
  taiTep: (url: string, headers: Record<string, string>, duongDan: string) => Promise<KetQuaGoi<{ id: string }>>;
  conTrenMay: (duongDan: string) => Promise<boolean>;
  xoaTep: (duongDan: string) => Promise<void>;
}

/** Tải tệp làm body nhị phân (react-native-blob-util đọc thẳng từ đĩa) */
async function taiTepThat(url: string, headers: Record<string, string>, duongDan: string) {
  const token = await tokenHoacLoi(b => useAuthStore.getState().layToken(b));
  if (typeof token !== 'string') {
    return token;
  }
  try {
    const r = await ReactNativeBlobUtil.config({ timeout: THOI_HAN_MS * 4 }).fetch(
      'POST',
      `${useCaiDatStore.getState().gatewayUrl}${url}`,
      { ...headers, Authorization: `Bearer ${token}` },
      ReactNativeBlobUtil.wrap(duongDan),
    );
    const info = r.info();
    let body: unknown = null;
    try {
      body = r.json();
    } catch {
      // Trang lỗi không phải JSON (APISIX 413/429/502)
    }
    if (info.status >= 200 && info.status < 300) {
      const phatLai = Object.entries(info.headers ?? {}).some(
        ([k, v]) => k.toLowerCase() === 'idempotent-replayed' && String(v) === 'true',
      );
      return { ok: true as const, status: info.status, data: body as { id: string }, phatLai };
    }
    return { ok: false as const, status: info.status, detail: (body as { detail?: unknown } | null)?.detail ?? null };
  } catch {
    return { ok: false as const, status: 0, detail: null };
  }
}

const macDinh: PhuThuocGui = { goi: api.goi, taiTep: taiTepThat, conTrenMay, xoaTep };

export async function guiBanGhi(b: BanGhi, incidentId: string | undefined, pt: PhuThuocGui = macDinh): Promise<KetQuaGui> {
  const d = b.duLieu;
  switch (d.loai) {
    case 'keu_cuu': {
      const r = await pt.goi<TinKeuCuuKetQua>({
        method: 'POST',
        url: '/workflow/keu-cuu',
        data: d.tin,
        headers: { 'Content-Type': 'application/json', [IDEM]: b.khoa },
      });
      return r.ok ? { ok: true, phatLai: r.phatLai, maTin: r.data.id } : loi(r);
    }
    case 'chuyen_tin': {
      const r = await pt.goi<BocTachKetQua>({
        method: 'POST',
        url: '/workflow/ai/boc-tach',
        data: { van_ban: d.vanBan, nguon: d.nguon, vao_hang_cho: true },
        headers: { 'Content-Type': 'application/json', [IDEM]: b.khoa },
      });
      return r.ok ? { ok: true, phatLai: r.phatLai, maHangCho: r.data.hang_cho?.id } : loi(r);
    }
    case 'anh': {
      if (!incidentId) {
        return { ok: false, loai: 'vinh_vien', status: 0, khoa: 'loi.tinGocLoi' };
      }
      if (!(await pt.conTrenMay(d.duongDan))) {
        return { ok: false, loai: 'vinh_vien', status: 0, khoa: 'loi.anhMat' };
      }
      const r = await pt.taiTep(
        `/workflow/tai-len/su-co/${incidentId}/anh`,
        { 'Content-Type': d.contentType, [IDEM]: b.khoa },
        d.duongDan,
      );
      if (!r.ok) {
        return loi(r);
      }
      await pt.xoaTep(d.duongDan);
      return { ok: true, phatLai: r.phatLai, maTin: incidentId, maAnh: r.data?.id };
    }
    case 'vi_tri_doi': {
      const bien = { id: d.doiId, p: { type: 'Point', coordinates: [d.lon, d.lat] }, luc: d.luc };
      const gql = (query: string, variables: Record<string, unknown>) =>
        pt.goi<{ data?: Record<string, { affected_rows?: number; location_updated_at?: string | null } | null>; errors?: Array<{ message?: string }> }>({
          method: 'POST',
          url: '/graphql',
          data: { query, variables },
          headers: { 'Content-Type': 'application/json', 'X-Hasura-Role': 'cuu-ho' },
        });
      // Hasura trả 200 kèm lỗi (không có quyền với đội này, dữ liệu sai): gửi lại cũng vậy
      const loiGql = (m?: string): KetQuaGui => ({ ok: false, loai: 'vinh_vien', status: 200, khoa: 'loi.khongQuyen', chiTiet: m });
      const r = await gql(M_VI_TRI_DOI, bien);
      if (!r.ok) {
        return loi(r);
      }
      if (r.data.errors?.length) {
        return loiGql(r.data.errors[0]?.message);
      }
      if ((r.data.data?.update_rescue_teams?.affected_rows ?? 0) > 0) {
        return { ok: true, phatLai: false };
      }
      // 0 dòng: đã có vị trí mới hơn (bỏ qua bản ghi cũ), hoặc đội chưa từng có vị trí (ghi lần đầu)
      const moc = await gql(Q_MOC_VI_TRI_DOI, { id: d.doiId });
      if (!moc.ok) {
        return loi(moc);
      }
      if (moc.data.errors?.length || !moc.data.data?.rescue_teams_by_pk) {
        return loiGql(moc.data.errors?.[0]?.message);
      }
      if (moc.data.data.rescue_teams_by_pk.location_updated_at) {
        return { ok: true, phatLai: true };
      }
      const dau = await gql(M_VI_TRI_DOI_DAU, bien);
      if (!dau.ok) {
        return loi(dau);
      }
      return dau.data.errors?.length ? loiGql(dau.data.errors[0]?.message) : { ok: true, phatLai: false };
    }
  }
}
