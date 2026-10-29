// SPDX-License-Identifier: Apache-2.0
// Hàng đợi gửi: mọi bản ghi (chờ, đang gửi, đã gửi, lỗi), mới nhất trên cùng. "Gửi ngay" kích hoạt bộ xử lý;
// "Gửi lại" giữ nguyên khóa idempotency nên máy chủ không tạo trùng; "Xóa" hỏi lại vì nội dung chưa gửi sẽ mất.
import { RefreshCw } from 'lucide-react-native';
import React, { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Alert, FlatList, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { BangMang } from '@/components/BangMang';
import { Nut } from '@/components/Nut';
import { TheBanGhi } from '@/components/TheBanGhi';
import { useHangDoiStore } from '@/stores/hangDoiStore';
import { useMangStore } from '@/stores/mangStore';
import { CHU, KHOANG, MAU } from '@/theme';
import type { BanGhi } from '@/utils/hangDoi';
import { boQua } from '@/utils/boQua';

export function HangDoiScreen() {
  const { t } = useTranslation();
  const ds = useHangDoiStore(s => s.ds);
  const dangXuLy = useHangDoiStore(s => s.dangXuLy);
  const coMang = useMangStore(s => s.coMang);
  const sap = useMemo(() => [...ds].sort((a, b) => b.taoLuc - a.taoLuc), [ds]);
  const theoId = useMemo(() => new Map(ds.map(b => [b.id, b])), [ds]);
  const now = Date.now();

  const xoa = (b: BanGhi) => {
    Alert.alert(t('chung.xoa'), t('hangDoi.xoaXacNhan'), [
      { text: t('chung.huy'), style: 'cancel' },
      { text: t('chung.xoa'), style: 'destructive', onPress: () => boQua(useHangDoiStore.getState().xoa(b.id)) },
    ]);
  };

  const choTinGoc = (b: BanGhi) =>
    b.duLieu.loai === 'anh' && !!b.duLieu.tuBanGhi && theoId.get(b.duLieu.tuBanGhi)?.trangThai !== 'da_gui';

  return (
    <SafeAreaView style={styles.nen} edges={['top', 'left', 'right']}>
      <BangMang />
      <FlatList
        data={sap}
        keyExtractor={b => b.id}
        contentContainerStyle={styles.noiDung}
        ListHeaderComponent={
          <View style={styles.dau}>
            <Text style={CHU.tieuDe} accessibilityRole="header">
              {t('hangDoi.tieuDe')}
            </Text>
            <Text style={CHU.phu}>{t('hangDoi.moTa')}</Text>
            <Nut
              nhan={t('hangDoi.guiNgay')}
              BieuTuong={RefreshCw}
              onPress={() => boQua(useHangDoiStore.getState().xuLy())}
              dangChay={dangXuLy}
              tat={!coMang}
              testID="nut-gui-ngay"
            />
          </View>
        }
        ListEmptyComponent={<Text style={CHU.phu}>{t('hangDoi.trong')}</Text>}
        renderItem={({ item }) => (
          <TheBanGhi
            banGhi={item}
            now={now}
            choTinGoc={choTinGoc(item)}
            onGuiLai={() => boQua(useHangDoiStore.getState().guiLai(item.id))}
            onXoa={() => xoa(item)}
          />
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  nen: { flex: 1, backgroundColor: MAU.nen },
  noiDung: { padding: KHOANG.lg, gap: KHOANG.md },
  dau: { gap: KHOANG.md, marginBottom: KHOANG.sm },
});
