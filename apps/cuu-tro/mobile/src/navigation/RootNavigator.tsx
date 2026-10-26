// SPDX-License-Identifier: Apache-2.0
// Chưa đăng nhập: màn Đăng nhập (+ đổi máy chủ). Đã đăng nhập: các tab và màn phụ (Dán tin, Chọn vị trí, Chi
// tiết tin). Đổi nhánh bằng điều kiện render (không resetTo sau khi đổi trạng thái đăng nhập).
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import React from 'react';
import { useTranslation } from 'react-i18next';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { CaiDatMayChuScreen } from '@/screens/CaiDatScreen';
import { ChiTietTinScreen } from '@/screens/ChiTietTinScreen';
import { ChonViTriScreen } from '@/screens/ChonViTriScreen';
import { DangNhapScreen } from '@/screens/DangNhapScreen';
import { DanTinScreen } from '@/screens/DanTinScreen';
import { useAuthStore } from '@/stores/authStore';
import { MAU } from '@/theme';
import { MainTabs } from './MainTabs';
import type { RootStackParamList } from './types';

const Stack = createNativeStackNavigator<RootStackParamList>();

export function RootNavigator() {
  const { t } = useTranslation();
  const trangThai = useAuthStore(s => s.trangThai);
  if (trangThai === 'dang_nap') {
    return (
      <View style={styles.cho}>
        <ActivityIndicator color={MAU.navy} size="large" />
      </View>
    );
  }
  return (
    <Stack.Navigator screenOptions={{ headerTintColor: MAU.navy, headerTitleStyle: { fontWeight: '700' } }}>
      {trangThai === 'chua_dang_nhap' ? (
        <>
          <Stack.Screen name="DangNhap" component={DangNhapScreen} options={{ headerShown: false }} />
          <Stack.Screen name="MayChu" component={CaiDatMayChuScreen} options={{ title: t('caiDat.mayChu') }} />
        </>
      ) : (
        <>
          <Stack.Screen name="Chinh" component={MainTabs} options={{ headerShown: false }} />
          <Stack.Screen name="DanTin" component={DanTinScreen} options={{ title: t('danTin.tieuDe') }} />
          <Stack.Screen name="ChonViTri" component={ChonViTriScreen} options={{ title: t('banDo.tieuDe') }} />
          <Stack.Screen name="ChiTietTin" component={ChiTietTinScreen} options={{ title: t('hienTruong.tieuDe') }} />
        </>
      )}
    </Stack.Navigator>
  );
}

const styles = StyleSheet.create({
  cho: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: MAU.nen },
});
