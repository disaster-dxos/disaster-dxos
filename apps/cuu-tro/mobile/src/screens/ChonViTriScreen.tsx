// SPDX-License-Identifier: Apache-2.0
// Chọn vị trí trên bản đồ (tin không có GPS, hoặc báo hộ người ở chỗ khác): chạm đặt ghim, "Dùng vị trí này"
// ghi vào bản nháp tin kêu cứu rồi quay lại form.
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Check, Crosshair } from 'lucide-react-native';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { StyleSheet, Text, View } from 'react-native';
import { BanDo } from '@/components/BanDo';
import { Nut } from '@/components/Nut';
import { useViTri } from '@/hooks/useViTri';
import type { RootStackParamList } from '@/navigation/types';
import { useNhapTinStore } from '@/stores/nhapTinStore';
import { CHU, KHOANG, MAU } from '@/theme';

type Props = NativeStackScreenProps<RootStackParamList, 'ChonViTri'>;

export function ChonViTriScreen({ navigation }: Props) {
  const { t } = useTranslation();
  const form = useNhapTinStore(s => s.form);
  const [diem, setDiem] = useState<[number, number] | null>(
    form.lat !== null && form.lon !== null ? [form.lon, form.lat] : null,
  );
  const viTri = useViTri();

  const viTriCuaToi = async () => {
    const p = await viTri.lay();
    if (p) {
      setDiem([p.lon, p.lat]);
    }
  };

  return (
    <View style={styles.nen}>
      <Text style={[CHU.phu, styles.huongDan]}>{t('banDo.huongDan')}</Text>
      <BanDo diem={diem} onChon={setDiem} testID="ban-do-chon" />
      <View style={styles.chan}>
        {diem ? <Text style={CHU.phu}>{`${diem[1].toFixed(5)}, ${diem[0].toFixed(5)}`}</Text> : null}
        {viTri.loi ? <Text style={styles.loi}>{t(viTri.loi)}</Text> : null}
        <Nut nhan={t('banDo.viTriCuaToi')} kieu="phu" BieuTuong={Crosshair} onPress={viTriCuaToi} dangChay={viTri.dangLay} />
        <Nut
          nhan={t('banDo.xacNhan')}
          BieuTuong={Check}
          tat={!diem}
          onPress={() => {
            if (diem) {
              useNhapTinStore.getState().sua({ lon: diem[0], lat: diem[1] });
              navigation.goBack();
            }
          }}
          testID="nut-xac-nhan-vi-tri"
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  nen: { flex: 1, backgroundColor: MAU.nen },
  huongDan: { padding: KHOANG.md },
  chan: { padding: KHOANG.md, gap: KHOANG.sm, backgroundColor: MAU.beMat, borderTopWidth: 1, borderTopColor: MAU.vien },
  loi: { color: MAU.loi, fontWeight: '600' },
});
