// SPDX-License-Identifier: Apache-2.0
import React from 'react';
import { useTranslation } from 'react-i18next';
import { StyleSheet, Text, View } from 'react-native';
import { BO_GOC, CO_CHU, KHOANG, MAU, MAU_MUC_KHAN } from '@/theme';
import type { MucKhan } from '@/types/api';

export function NhanMucKhan({ muc }: { muc: MucKhan }) {
  const { t } = useTranslation();
  return (
    <View style={[styles.nhan, { backgroundColor: MAU_MUC_KHAN[muc] }]}>
      <Text style={styles.chu}>{t(`mucKhan.${muc}`)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  nhan: { borderRadius: BO_GOC.nho, paddingHorizontal: KHOANG.sm, paddingVertical: 2, alignSelf: 'flex-start' },
  chu: { color: MAU.trang, fontSize: CO_CHU.nho, fontWeight: '700' },
});
