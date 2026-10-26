// SPDX-License-Identifier: Apache-2.0
// Băng trạng thái ở đầu màn hình: mất mạng (nói rõ dữ liệu vẫn được giữ) và số bản ghi chờ gửi.
import { CloudOff, Upload } from 'lucide-react-native';
import React from 'react';
import { useTranslation } from 'react-i18next';
import { StyleSheet, Text, View } from 'react-native';
import { useHangDoiStore } from '@/stores/hangDoiStore';
import { useMangStore } from '@/stores/mangStore';
import { CO_CHU, KHOANG, MAU } from '@/theme';

export function BangMang() {
  const { t } = useTranslation();
  const coMang = useMangStore(s => s.coMang);
  const cho = useHangDoiStore(s => s.ds.filter(b => b.trangThai === 'cho_gui' || b.trangThai === 'dang_gui').length);
  if (coMang && cho === 0) {
    return null;
  }
  return (
    <View style={[styles.bang, coMang ? styles.cho : styles.mat]} accessibilityLiveRegion="polite" testID="bang-mang">
      {coMang ? <Upload color={MAU.navy} size={20} /> : <CloudOff color={MAU.canhBao} size={20} />}
      <Text style={styles.chu}>{coMang ? t('mang.choGui', { count: cho }) : t('mang.matMang')}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  bang: { flexDirection: 'row', alignItems: 'center', gap: KHOANG.sm, padding: KHOANG.md },
  mat: { backgroundColor: MAU.canhBaoNhat },
  cho: { backgroundColor: MAU.navyNhat },
  chu: { flex: 1, fontSize: CO_CHU.nho, color: MAU.chu, fontWeight: '600' },
});
