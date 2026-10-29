// SPDX-License-Identifier: Apache-2.0
// Ô nhập có nhãn, gợi ý, lỗi ngay dưới ô (trình đọc màn hình đọc kèm nhãn). Chữ và lỗi 17 sp, ô cao ≥ 52 dp,
// viền vienO đạt 3:1 để thấy ô ngoài nắng (#113).
import React from 'react';
import { StyleSheet, Text, TextInput, View, type KeyboardTypeOptions } from 'react-native';
import { BO_GOC, CHU, CO_CHU, KHOANG, MAU, VUNG_CHAM } from '@/theme';

interface Props {
  nhan: string;
  value: string;
  onChangeText: (s: string) => void;
  loi?: string | null;
  goiY?: string;
  phu?: string;
  nhieuDong?: boolean;
  keyboardType?: KeyboardTypeOptions;
  maxLength?: number;
  testID?: string;
}

export function OVanBan({ nhan, value, onChangeText, loi, goiY, phu, nhieuDong, keyboardType, maxLength, testID }: Props) {
  return (
    <View style={styles.khoi}>
      <Text style={CHU.nhan}>
        {nhan}
        {phu ? <Text style={CHU.phu}>{`  ${phu}`}</Text> : null}
      </Text>
      <TextInput
        testID={testID}
        accessibilityLabel={nhan}
        accessibilityHint={loi ?? undefined}
        value={value}
        onChangeText={onChangeText}
        placeholder={goiY}
        placeholderTextColor={MAU.chuMo}
        multiline={nhieuDong}
        keyboardType={keyboardType}
        maxLength={maxLength}
        style={[styles.o, nhieuDong && styles.nhieuDong, loi ? styles.oLoi : null]}
      />
      {loi ? (
        <Text style={styles.loi} accessibilityLiveRegion="polite">
          {loi}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  khoi: { gap: KHOANG.xs },
  o: {
    minHeight: VUNG_CHAM,
    borderWidth: 1.5,
    borderColor: MAU.vienO,
    borderRadius: BO_GOC.nho,
    backgroundColor: MAU.beMat,
    paddingHorizontal: KHOANG.md,
    paddingVertical: KHOANG.sm,
    fontSize: CO_CHU.thuong,
    color: MAU.chu,
  },
  nhieuDong: { minHeight: 96, textAlignVertical: 'top' },
  oLoi: { borderColor: MAU.loi },
  loi: { color: MAU.loi, fontSize: CO_CHU.thuong, fontWeight: '600' },
});
