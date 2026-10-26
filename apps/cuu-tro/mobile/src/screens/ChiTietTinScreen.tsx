// SPDX-License-Identifier: Apache-2.0
// Chi tiết một tin (từ danh sách Hiện trường, dữ liệu trong cache TanStack Query) và gửi ảnh hiện trường: chụp
// hoặc chọn ảnh → chép vào app → bản ghi `anh` trong hàng đợi (khóa idempotency riêng) → tự gửi khi có mạng.
// Quyền tải ảnh do API kiểm: tình nguyện viên chỉ khi tin của mình còn ở Tiếp nhận; cứu hộ cho tin của đội mình.
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Camera, Image as ImageIcon } from 'lucide-react-native';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { StyleSheet, Text, View } from 'react-native';
import { BanDo } from '@/components/BanDo';
import { ManHinh } from '@/components/ManHinh';
import { NhanMucKhan } from '@/components/NhanMucKhan';
import { Nut } from '@/components/Nut';
import { useTinCuaToi } from '@/hooks/useDuLieuHienTruong';
import type { RootStackParamList } from '@/navigation/types';
import { chupAnh, LoiQuyenCamera } from '@/services/chupAnh';
import { useHangDoiStore } from '@/stores/hangDoiStore';
import { CHU, KHOANG, MAU } from '@/theme';
import { taoKhoa } from '@/utils/khoaIdempotency';
import { maNgan } from '@/utils/thoiGian';

type Props = NativeStackScreenProps<RootStackParamList, 'ChiTietTin'>;

export function ChiTietTinScreen({ route }: Props) {
  const { t } = useTranslation();
  const tin = useTinCuaToi().data?.find(x => x.id === route.params.id) ?? null;
  const [bao, setBao] = useState<{ ok: boolean; chu: string } | null>(null);

  const anh = async (nguon: 'camera' | 'thu_vien') => {
    setBao(null);
    try {
      const a = await chupAnh(nguon, taoKhoa());
      if (!a) {
        return;
      }
      await useHangDoiStore
        .getState()
        .them({ loai: 'anh', incidentId: route.params.id, duongDan: a.duongDan, contentType: a.contentType });
      setBao({ ok: true, chu: t('hienTruong.daLuuAnh') });
    } catch (e) {
      setBao({ ok: false, chu: e instanceof LoiQuyenCamera ? t(e.message) : String(e) });
    }
  };

  return (
    <ManHinh tieuDe={`${t('hangDoi.maTin', { ma: maNgan(route.params.id) })}`}>
      {tin ? (
        <View style={styles.khoi}>
          <View style={styles.hang}>
            <NhanMucKhan muc={tin.urgency} />
            <Text style={CHU.phu}>{t(`trangThaiTin.${tin.status}`)}</Text>
          </View>
          <Text style={CHU.thuong}>{tin.description}</Text>
          {tin.address_text ? <Text style={CHU.phu}>{tin.address_text}</Text> : null}
          <Text style={CHU.phu}>{t('hienTruong.soNguoi', { count: tin.people_count })}</Text>
          {tin.toaDo ? <BanDo diem={tin.toaDo} cao={200} /> : null}
        </View>
      ) : null}
      <Nut nhan={t('hienTruong.chupAnh')} BieuTuong={Camera} onPress={() => anh('camera')} testID="nut-chup" />
      <Nut nhan={t('hienTruong.chonAnh')} kieu="phu" BieuTuong={ImageIcon} onPress={() => anh('thu_vien')} />
      {bao ? <Text style={[CHU.nhan, { color: bao.ok ? MAU.thanhCong : MAU.loi }]}>{bao.chu}</Text> : null}
    </ManHinh>
  );
}

const styles = StyleSheet.create({
  khoi: { gap: KHOANG.sm },
  hang: { flexDirection: 'row', alignItems: 'center', gap: KHOANG.sm },
});
