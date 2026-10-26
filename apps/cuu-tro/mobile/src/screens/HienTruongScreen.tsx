// SPDX-License-Identifier: Apache-2.0
// Hiện trường: danh sách tin theo quyền của vai (Hasura lọc): tình nguyện viên thấy tin mình gửi, đội cứu hộ thấy
// nhiệm vụ của đội. Đội cứu hộ cập nhật vị trí đội bằng GPS (bản ghi vi_tri_doi trong hàng đợi). Bấm tin → chi
// tiết để gửi ảnh hiện trường. Mất mạng vẫn hiện danh sách đã tải lần trước.
import { useNavigation, type NavigationProp } from '@react-navigation/native';
import { MapPinned } from 'lucide-react-native';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { BangMang } from '@/components/BangMang';
import { NhanMucKhan } from '@/components/NhanMucKhan';
import { Nut } from '@/components/Nut';
import { useDoiCuaToi, useTinCuaToi, useVai } from '@/hooks/useDuLieuHienTruong';
import { useViTri } from '@/hooks/useViTri';
import type { RootStackParamList } from '@/navigation/types';
import { useHangDoiStore } from '@/stores/hangDoiStore';
import { CHU, KHOANG, MAU, THE } from '@/theme';
import type { TinCuaToi } from '@/types/api';
import { maNgan } from '@/utils/thoiGian';
import { boQua } from '@/utils/boQua';

export function HienTruongScreen() {
  const { t } = useTranslation();
  const nav = useNavigation<NavigationProp<RootStackParamList>>();
  const vai = useVai();
  const tin = useTinCuaToi();
  const doi = useDoiCuaToi();
  const viTri = useViTri();
  const [baoViTri, setBaoViTri] = useState(false);

  const capNhatViTriDoi = async () => {
    setBaoViTri(false);
    const p = await viTri.lay();
    if (p && doi.data) {
      await useHangDoiStore
        .getState()
        .them({ loai: 'vi_tri_doi', doiId: doi.data.id, lat: p.lat, lon: p.lon, luc: new Date().toISOString() });
      setBaoViTri(true);
    }
  };

  const dau = (
    <View style={styles.dau}>
      <Text style={CHU.tieuDe} accessibilityRole="header">
        {t('hienTruong.tieuDe')}
      </Text>
      <Text style={CHU.phu}>{vai === 'cuu-ho' ? t('hienTruong.moTaCuuHo') : t('hienTruong.moTaTinhNguyen')}</Text>
      {vai === 'cuu-ho' && doi.data ? (
        <View style={[THE.coBan, styles.khoi]}>
          <Text style={CHU.nhan}>{t('hienTruong.doi', { ten: doi.data.name })}</Text>
          <Nut
            nhan={t('hienTruong.capNhatViTriDoi')}
            BieuTuong={MapPinned}
            onPress={capNhatViTriDoi}
            dangChay={viTri.dangLay}
            testID="nut-vi-tri-doi"
          />
          {viTri.loi ? <Text style={styles.loi}>{t(viTri.loi)}</Text> : null}
          {baoViTri ? <Text style={[CHU.nhan, styles.ok]}>{t('hienTruong.daLuuViTri')}</Text> : null}
        </View>
      ) : null}
      {tin.isError ? <Text style={styles.loi}>{tin.data ? t('hienTruong.dangTaiCu') : t('hienTruong.loiTai')}</Text> : null}
    </View>
  );

  const the = ({ item }: { item: TinCuaToi }) => (
    <Pressable
      accessibilityRole="button"
      onPress={() => nav.navigate('ChiTietTin', { id: item.id })}
      style={({ pressed }) => [THE.coBan, styles.the, pressed && styles.nhan]}
      testID={`tin-${item.id}`}
    >
      <View style={styles.hang}>
        <NhanMucKhan muc={item.urgency} />
        <Text style={CHU.phu}>{t(`trangThaiTin.${item.status}`)}</Text>
        <Text style={[CHU.phu, styles.ma]}>{maNgan(item.id)}</Text>
      </View>
      <Text style={CHU.thuong} numberOfLines={2}>
        {item.description}
      </Text>
      <Text style={CHU.phu}>
        {[item.address_text, t('hienTruong.soNguoi', { count: item.people_count })].filter(Boolean).join(' · ')}
      </Text>
    </Pressable>
  );

  return (
    <SafeAreaView style={styles.nen} edges={['top', 'left', 'right']}>
      <BangMang />
      <FlatList
        data={tin.data ?? []}
        keyExtractor={x => x.id}
        renderItem={the}
        ListHeaderComponent={dau}
        ListEmptyComponent={tin.isLoading ? null : <Text style={CHU.phu}>{t('hienTruong.trong')}</Text>}
        contentContainerStyle={styles.noiDung}
        refreshControl={
          <RefreshControl
            refreshing={tin.isFetching}
            onRefresh={() => {
              boQua(tin.refetch());
              boQua(doi.refetch());
            }}
          />
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  nen: { flex: 1, backgroundColor: MAU.nen },
  noiDung: { padding: KHOANG.lg, gap: KHOANG.md },
  dau: { gap: KHOANG.md, marginBottom: KHOANG.sm },
  khoi: { gap: KHOANG.sm },
  the: { gap: KHOANG.xs },
  nhan: { opacity: 0.85 },
  hang: { flexDirection: 'row', alignItems: 'center', gap: KHOANG.sm },
  ma: { marginLeft: 'auto', fontVariant: ['tabular-nums'] },
  loi: { color: MAU.loi, fontWeight: '600' },
  ok: { color: MAU.thanhCong },
});
