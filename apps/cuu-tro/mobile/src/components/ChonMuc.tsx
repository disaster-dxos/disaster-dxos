// SPDX-License-Identifier: Apache-2.0
// Chọn một trong vài giá trị bằng các ô to (mức khẩn cấp, nguồn tin, ngôn ngữ). Ô đang chọn có viền đậm và
// dấu tích, không chỉ dựa vào màu.
import { Check } from 'lucide-react-native';
import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { BO_GOC, CO_CHU, DO_DAM, KHOANG, MAU, VUNG_CHAM } from '@/theme';

interface Props<T extends string> {
  nhan?: string;
  giaTri: T;
  dsMuc: ReadonlyArray<{ giaTri: T; nhan: string; mau?: string }>;
  onChon: (v: T) => void;
  testID?: string;
}

export function ChonMuc<T extends string>({ nhan, giaTri, dsMuc, onChon, testID }: Props<T>) {
  return (
    <View style={styles.khoi} accessibilityRole="radiogroup" accessibilityLabel={nhan} testID={testID}>
      {nhan ? <Text style={styles.nhan}>{nhan}</Text> : null}
      <View style={styles.hang}>
        {dsMuc.map(m => {
          const chon = m.giaTri === giaTri;
          const mau = m.mau ?? MAU.navy;
          return (
            <Pressable
              key={m.giaTri}
              testID={testID ? `${testID}-${m.giaTri}` : undefined}
              accessibilityRole="radio"
              accessibilityState={{ selected: chon }}
              onPress={() => onChon(m.giaTri)}
              style={[styles.o, chon ? { backgroundColor: mau, borderColor: mau } : null]}
            >
              {chon ? <Check color={MAU.trang} size={18} strokeWidth={3} /> : null}
              <Text style={[styles.chu, chon ? styles.chuChon : null]}>{m.nhan}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  khoi: { gap: KHOANG.xs },
  nhan: { fontSize: CO_CHU.thuong, fontWeight: DO_DAM.vua, color: MAU.chu },
  hang: { flexDirection: 'row', flexWrap: 'wrap', gap: KHOANG.sm },
  o: {
    minHeight: VUNG_CHAM - 4,
    paddingHorizontal: KHOANG.md,
    borderRadius: BO_GOC.nho,
    borderWidth: 1.5,
    borderColor: MAU.vien,
    backgroundColor: MAU.beMat,
    flexDirection: 'row',
    alignItems: 'center',
    gap: KHOANG.xs,
  },
  chu: { fontSize: CO_CHU.thuong, color: MAU.chu, fontWeight: DO_DAM.vua },
  chuChon: { color: MAU.trang },
});
