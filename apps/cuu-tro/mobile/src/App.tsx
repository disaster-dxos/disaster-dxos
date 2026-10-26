// SPDX-License-Identifier: Apache-2.0
// App hiện trường Disaster DX-OS (Tầng 2, D-011): tình nguyện viên và đội cứu hộ gửi kêu cứu, cập nhật hiện
// trường; mọi thao tác ghi qua hàng đợi offline có khóa idempotency. Chỉ gọi lõi qua API Gateway.
import { NavigationContainer, type Theme } from '@react-navigation/native';
import { QueryClientProvider } from '@tanstack/react-query';
import React, { useEffect } from 'react';
import { I18nextProvider } from 'react-i18next';
import { StatusBar } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { queryClient } from '@/config/queryClient';
import { useDongBoHangDoi } from '@/hooks/useDongBoHangDoi';
import i18n, { khoiTaoI18n } from '@/i18n';
import { navigationRef } from '@/navigation/NavigationService';
import { RootNavigator } from '@/navigation/RootNavigator';
import { useAuthStore } from '@/stores/authStore';
import { useCaiDatStore } from '@/stores/caiDatStore';
import { MAU } from '@/theme';
import { boQua } from '@/utils/boQua';

khoiTaoI18n(useCaiDatStore.getState().ngonNgu);

// Chỉ giao diện sáng: dùng ngoài trời, cần tương phản cao
const giaoDien: Theme = {
  dark: false,
  colors: {
    primary: MAU.navy,
    background: MAU.nen,
    card: MAU.beMat,
    text: MAU.chu,
    border: MAU.vien,
    notification: MAU.cam,
  },
  fonts: {
    regular: { fontFamily: 'System', fontWeight: '400' },
    medium: { fontFamily: 'System', fontWeight: '500' },
    bold: { fontFamily: 'System', fontWeight: '700' },
    heavy: { fontFamily: 'System', fontWeight: '800' },
  },
};

function DongBo() {
  useDongBoHangDoi();
  return null;
}

export default function App() {
  useEffect(() => {
    boQua(
      (async () => {
        await useCaiDatStore.getState().nap();
        await useAuthStore.getState().khoiPhuc();
      })(),
    );
  }, []);
  return (
    <SafeAreaProvider>
      <I18nextProvider i18n={i18n}>
        <QueryClientProvider client={queryClient}>
          <StatusBar barStyle="dark-content" backgroundColor={MAU.nen} />
          <NavigationContainer ref={navigationRef} theme={giaoDien}>
            <DongBo />
            <RootNavigator />
          </NavigationContainer>
        </QueryClientProvider>
      </I18nextProvider>
    </SafeAreaProvider>
  );
}
