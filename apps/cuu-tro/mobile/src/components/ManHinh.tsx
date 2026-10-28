// SPDX-License-Identifier: Apache-2.0
// Khung một màn: vùng an toàn, băng mạng, tiêu đề + mô tả, nội dung cuộn được (bàn phím không che ô nhập).
// `chan`: vùng cố định ở đáy màn cho nút chính, trong tầm ngón cái khi cầm máy một tay (#113).
import React, { type ReactNode, type RefObject } from 'react';
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
  /** Để màn cuộn tới một ô (vd ô lỗi đầu tiên khi bấm Gửi ở chân màn) */
  cuonRef?: RefObject<ScrollView | null>;
}

export function ManHinh({ tieuDe, moTa, children, cuon = true, chan, cuonRef }: Props) {
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
          <ScrollView ref={cuonRef} contentContainerStyle={styles.noiDung} keyboardShouldPersistTaps="handled">
            {dau}
            {children}
          </ScrollView>
        ) : (
          <View style={[styles.nen, styles.noiDung]}>
            {dau}
            {children}
          </View>
        )}
        {/* Màn trong ngăn xếp (Dán tin) không có thanh tab đỡ: nút chân màn không được nằm dưới thanh cử chỉ/home
            indicator (Android 15 bắt buộc edge-to-edge). SafeAreaView chỉ đệm phần thật sự chồng lên vùng không
            an toàn, nên màn trong tab không bị đệm thừa. */}
        {chan ? (
          <SafeAreaView edges={['bottom']} style={styles.chan}>
            {chan}
          </SafeAreaView>
        ) : null}
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
