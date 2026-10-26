// SPDX-License-Identifier: Apache-2.0
// Khoảng cách (bội số 4), bo góc, cỡ chữ. Cỡ chữ lớn hơn app thường: người dùng ngoài trời, mưa, tay ướt.

export const KHOANG = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;

export const BO_GOC = { nho: 8, vua: 12, lon: 16, tron: 999 } as const;

/** Vùng chạm tối thiểu (dp): lớn hơn khuyến nghị 44–48 vì người dùng có thể đeo găng, tay ướt */
export const VUNG_CHAM = 52;

export const CO_CHU = { nho: 14, thuong: 17, vua: 19, lon: 22, tieuDe: 26 } as const;

export const DO_DAM = { thuong: '400', vua: '600', dam: '700' } as const;
