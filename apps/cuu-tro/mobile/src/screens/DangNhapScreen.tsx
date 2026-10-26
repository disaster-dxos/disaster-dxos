// SPDX-License-Identifier: Apache-2.0
// Đăng nhập Keycloak (PKCE, trình duyệt hệ thống). Hiện máy chủ đang dùng và lối đổi máy chủ (máy dev, máy chủ
// của xã, VPS demo). Hàng đợi chưa gửi vẫn giữ trên máy và gửi tiếp sau khi đăng nhập.
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { LogIn, Server } from 'lucide-react-native';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Image, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Nut } from '@/components/Nut';
import type { RootStackParamList } from '@/navigation/types';
import { useAuthStore } from '@/stores/authStore';
import { useCaiDatStore } from '@/stores/caiDatStore';
import { CHU, KHOANG, MAU, THE } from '@/theme';

const LOGO = require('@logo/mark-180.png');

type Props = NativeStackScreenProps<RootStackParamList, 'DangNhap'>;

export function DangNhapScreen({ navigation }: Props) {
  const { t } = useTranslation();
  const [dangMo, setDangMo] = useState(false);
  const loi = useAuthStore(s => s.loi);
  const keycloakUrl = useCaiDatStore(s => s.keycloakUrl);

  const dangNhap = async () => {
    setDangMo(true);
    try {
      await useAuthStore.getState().dangNhap();
    } finally {
      setDangMo(false);
    }
  };

  return (
    <SafeAreaView style={styles.nen}>
      <View style={styles.dau}>
        <Image source={LOGO} style={styles.logo} accessibilityIgnoresInvertColors accessible={false} />
        <Text style={[CHU.tieuDe, styles.giua]}>{t('app.ten')}</Text>
        <Text style={[CHU.phu, styles.giua]}>{t('app.khauHieu')}</Text>
      </View>
      <View style={[THE.coBan, styles.the]}>
        <Text style={CHU.muc} accessibilityRole="header">
          {t('dangNhap.tieuDe')}
        </Text>
        <Text style={CHU.thuong}>{t('dangNhap.moTa')}</Text>
        {loi ? <Text style={styles.loi}>{t('dangNhap.loi', { chiTiet: loi })}</Text> : null}
        <Nut
          nhan={dangMo ? t('dangNhap.dangMo') : t('dangNhap.nut')}
          onPress={dangNhap}
          dangChay={dangMo}
          BieuTuong={LogIn}
          testID="nut-dang-nhap"
        />
      </View>
      <View style={styles.mayChu}>
        <Text style={CHU.phu}>{t('dangNhap.mayChu', { url: keycloakUrl })}</Text>
        <Nut nhan={t('dangNhap.doiMayChu')} kieu="phu" BieuTuong={Server} onPress={() => navigation.navigate('MayChu')} />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  nen: { flex: 1, backgroundColor: MAU.nen, padding: KHOANG.lg, gap: KHOANG.xl, justifyContent: 'center' },
  dau: { alignItems: 'center', gap: KHOANG.sm },
  logo: { width: 96, height: 96 },
  giua: { textAlign: 'center' },
  the: { gap: KHOANG.md },
  loi: { color: MAU.loi, fontWeight: '600' },
  mayChu: { gap: KHOANG.sm },
});
