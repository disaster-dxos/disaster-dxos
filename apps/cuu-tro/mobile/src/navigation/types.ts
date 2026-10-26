// SPDX-License-Identifier: Apache-2.0
// Mọi route và tham số khai ở đây (typed). Bản nháp tin kêu cứu KHÔNG đi qua tham số (có SĐT): nằm ở
// stores/nhapTinStore.ts.
import type { NavigatorScreenParams } from '@react-navigation/native';

export type TabParamList = {
  KeuCuu: undefined;
  HienTruong: undefined;
  HangDoi: undefined;
  CaiDat: undefined;
};

export type RootStackParamList = {
  DangNhap: undefined;
  MayChu: undefined;
  Chinh: NavigatorScreenParams<TabParamList> | undefined;
  DanTin: undefined;
  ChonViTri: undefined;
  ChiTietTin: { id: string };
};
