// SPDX-License-Identifier: Apache-2.0
// Bản nháp tin kêu cứu đang nhập (form, ảnh kèm). Chỉ trong bộ nhớ (có SĐT, tên): không lưu xuống máy, không
// truyền qua tham số điều hướng. Màn Dán tin và Chọn vị trí ghi vào đây rồi quay lại form.
import { create } from 'zustand';
import { FORM_TRONG, formTuDeXuat, type FormKeuCuu } from '@/utils/kiemTra';
import type { BocTachKetQua } from '@/types/api';

export interface AnhKem {
  duongDan: string;
  contentType: string;
}

interface NhapTinState {
  form: FormKeuCuu;
  anhKem: AnhKem[];
  /** Form vừa được điền theo AI bóc tách (#102): nhắc người dùng soát lại */
  tuAi: boolean;
  sua: (p: Partial<FormKeuCuu>) => void;
  apDeXuat: (kq: BocTachKetQua) => void;
  themAnh: (a: AnhKem) => void;
  xoaHet: () => void;
}

export const useNhapTinStore = create<NhapTinState>((set, get) => ({
  form: FORM_TRONG,
  anhKem: [],
  tuAi: false,
  sua: p => set({ form: { ...get().form, ...p } }),
  apDeXuat: kq => {
    const t = kq.tin_keu_cuu;
    set({
      form: formTuDeXuat(get().form, {
        lat: t.lat,
        lon: t.lon,
        reporter_phone: t.reporter_phone,
        reporter_name: t.reporter_name,
        address_text: t.address_text,
        people_count: t.people_count,
        urgency: t.urgency,
        description: t.description,
      }),
      tuAi: true,
    });
  },
  themAnh: a => set({ anhKem: [...get().anhKem, a] }),
  xoaHet: () => set({ form: FORM_TRONG, anhKem: [], tuAi: false }),
}));
