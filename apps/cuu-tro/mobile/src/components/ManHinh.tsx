// SPDX-License-Identifier: Apache-2.0
// Khung một màn: vùng an toàn, băng mạng, tiêu đề + mô tả, nội dung cuộn được (bàn phím không che ô nhập).
import React, { type ReactNode } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { CHU, KHOANG, MAU } from '@/theme';
import { BangMang } from './BangMang';

interface Props {
  tieuDe?: string;
  moTa?: string;
  children: ReactNode;
  cuon?: boolean;
  chan?: ReactNode;
}

export function ManHinh({ tieuDe, moTa, children, cuon = true, chan }: Props) {
  const dau = tieuDe ? (
    <View style={styles.dau}>
      <Text style={CHU.tieuDe} accessibilityRole="header">
        {tieuDe}
      </Text>
      {moTa ? <Text style={CHU.phu}>{moTa}</Text> : null}
    </View>
  ) : null;
  return (
    <SafeAreaView style={styles.nen} edges={['top', 'left', 'right']}>
      <BangMang />
      <KeyboardAvoidingView style={styles.nen} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        {cuon ? (
          <ScrollView contentContainerStyle={styles.noiDung} keyboardShouldPersistTaps="handled">
            {dau}
            {children}
          </ScrollView>
        ) : (
          <View style={[styles.nen, styles.noiDung]}>
            {dau}
            {children}
          </View>
        )}
        {chan ? <View style={styles.chan}>{chan}</View> : null}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  nen: { flex: 1, backgroundColor: MAU.nen },
  noiDung: { padding: KHOANG.lg, gap: KHOANG.lg },
  dau: { gap: KHOANG.xs },
  chan: {
    padding: KHOANG.md,
    backgroundColor: MAU.beMat,
    borderTopWidth: 1,
    borderTopColor: MAU.vien,
    gap: KHOANG.sm,
  },
});
