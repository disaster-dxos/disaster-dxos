// SPDX-License-Identifier: Apache-2.0
// Điều hướng từ ngoài cây React (ví dụ thông báo hệ thống sau này). Chưa sẵn sàng thì bỏ qua.
import { createNavigationContainerRef } from '@react-navigation/native';
import type { RootStackParamList } from './types';

export const navigationRef = createNavigationContainerRef<RootStackParamList>();

export function denHangDoi(): void {
  if (navigationRef.isReady()) {
    navigationRef.navigate('Chinh', { screen: 'HangDoi' });
  }
}
