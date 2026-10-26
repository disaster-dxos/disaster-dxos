// SPDX-License-Identifier: Apache-2.0
// Thanh tab dưới: Kêu cứu · Hiện trường · Hàng đợi (số bản ghi chờ gửi) · Cài đặt. Nhãn chữ luôn hiện.
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { ClipboardList, Inbox, LifeBuoy, Settings } from 'lucide-react-native';
import React from 'react';
import { useTranslation } from 'react-i18next';
import { CaiDatScreen } from '@/screens/CaiDatScreen';
import { HangDoiScreen } from '@/screens/HangDoiScreen';
import { HienTruongScreen } from '@/screens/HienTruongScreen';
import { KeuCuuScreen } from '@/screens/KeuCuuScreen';
import { useHangDoiStore } from '@/stores/hangDoiStore';
import { CO_CHU, MAU } from '@/theme';
import type { TabParamList } from './types';

const Tab = createBottomTabNavigator<TabParamList>();

interface IconProps {
  color: string;
}
const IconKeuCuu = ({ color }: IconProps) => <LifeBuoy color={color} size={26} />;
const IconHienTruong = ({ color }: IconProps) => <ClipboardList color={color} size={26} />;
const IconHangDoi = ({ color }: IconProps) => <Inbox color={color} size={26} />;
const IconCaiDat = ({ color }: IconProps) => <Settings color={color} size={26} />;

export function MainTabs() {
  const { t } = useTranslation();
  const cho = useHangDoiStore(s => s.ds.filter(b => b.trangThai !== 'da_gui').length);
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: MAU.navy,
        tabBarInactiveTintColor: MAU.chuPhu,
        tabBarLabelStyle: { fontSize: CO_CHU.nho, fontWeight: '600' },
        tabBarStyle: { minHeight: 64 },
      }}
    >
      <Tab.Screen
        name="KeuCuu"
        component={KeuCuuScreen}
        options={{ title: t('tab.keuCuu'), tabBarIcon: IconKeuCuu }}
      />
      <Tab.Screen
        name="HienTruong"
        component={HienTruongScreen}
        options={{ title: t('tab.hienTruong'), tabBarIcon: IconHienTruong }}
      />
      <Tab.Screen
        name="HangDoi"
        component={HangDoiScreen}
        options={{
          title: t('tab.hangDoi'),
          tabBarIcon: IconHangDoi,
          tabBarBadge: cho > 0 ? cho : undefined,
          tabBarBadgeStyle: { backgroundColor: MAU.cam, color: MAU.trang },
        }}
      />
      <Tab.Screen
        name="CaiDat"
        component={CaiDatScreen}
        options={{ title: t('tab.caiDat'), tabBarIcon: IconCaiDat }}
      />
    </Tab.Navigator>
  );
}
