// SPDX-License-Identifier: Apache-2.0
// Nút bấm: vùng chạm ≥ 52 dp, chữ lớn, có trạng thái đang chạy và bị tắt (đọc được bởi trình đọc màn hình).
import type { LucideIcon } from 'lucide-react-native';
import React from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { BO_GOC, CO_CHU, DO_DAM, KHOANG, MAU, VUNG_CHAM } from '@/theme';

type Kieu = 'chinh' | 'cam' | 'phu' | 'nguy';

interface Props {
  nhan: string;
  onPress: () => void;
  kieu?: Kieu;
  dangChay?: boolean;
  tat?: boolean;
  BieuTuong?: LucideIcon;
  testID?: string;
}

const MAU_KIEU: Record<Kieu, { nen: string; chu: string; vien: string }> = {
  chinh: { nen: MAU.navy, chu: MAU.trang, vien: MAU.navy },
  cam: { nen: MAU.cam, chu: MAU.trang, vien: MAU.cam },
  phu: { nen: MAU.beMat, chu: MAU.navy, vien: MAU.vien },
  nguy: { nen: MAU.beMat, chu: MAU.loi, vien: MAU.loi },
};

export function Nut({ nhan, onPress, kieu = 'chinh', dangChay = false, tat = false, BieuTuong, testID }: Props) {
  const m = MAU_KIEU[kieu];
  const khongBam = tat || dangChay;
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityState={{ disabled: khongBam, busy: dangChay }}
      onPress={onPress}
      disabled={khongBam}
      style={({ pressed }) => [
        styles.nut,
        { backgroundColor: m.nen, borderColor: m.vien },
        pressed && styles.nhan,
        khongBam && styles.tat,
      ]}
    >
      <View style={styles.trong}>
        {dangChay ? (
          <ActivityIndicator color={m.chu} />
        ) : (
          BieuTuong && <BieuTuong color={m.chu} size={22} strokeWidth={2.25} />
        )}
        <Text style={[styles.chu, { color: m.chu }]}>{nhan}</Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  nut: {
    minHeight: VUNG_CHAM,
    borderRadius: BO_GOC.vua,
    borderWidth: 1.5,
    paddingHorizontal: KHOANG.lg,
    justifyContent: 'center',
  },
  trong: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: KHOANG.sm },
  chu: { fontSize: CO_CHU.thuong, fontWeight: DO_DAM.dam, textAlign: 'center' },
  nhan: { opacity: 0.85 },
  tat: { opacity: 0.5 },
});
