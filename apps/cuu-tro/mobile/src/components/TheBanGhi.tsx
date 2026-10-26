// SPDX-License-Identifier: Apache-2.0
// Một bản ghi trong hàng đợi: loại, tóm tắt (không hiện SĐT đầy đủ), trạng thái bằng chữ + biểu tượng, lỗi,
// mã tin sau khi gửi, nút Gửi lại / Xóa.
import { AlertTriangle, CheckCircle2, Clock, Loader } from 'lucide-react-native';
import React from 'react';
import { useTranslation } from 'react-i18next';
import { StyleSheet, Text, View } from 'react-native';
import { CHU, KHOANG, MAU, THE } from '@/theme';
import type { BanGhi, TrangThai } from '@/utils/hangDoi';
import { maNgan, thoiGianTruoc } from '@/utils/thoiGian';
import { Nut } from './Nut';

const BIEU_TUONG: Record<TrangThai, { Icon: typeof Clock; mau: string }> = {
  cho_gui: { Icon: Clock, mau: MAU.canhBao },
  dang_gui: { Icon: Loader, mau: MAU.navy },
  da_gui: { Icon: CheckCircle2, mau: MAU.thanhCong },
  loi: { Icon: AlertTriangle, mau: MAU.loi },
};

/** SĐT che giữa: 0935***222 */
export function cheSdt(s: string): string {
  return s.length >= 7 ? `${s.slice(0, 4)}***${s.slice(-3)}` : s;
}

function tomTat(b: BanGhi): string {
  const d = b.duLieu;
  switch (d.loai) {
    case 'keu_cuu':
      return `${cheSdt(d.tin.reporter_phone)} · ${d.tin.description.slice(0, 80)}`;
    case 'chuyen_tin':
      return d.vanBan.slice(0, 80);
    case 'anh':
      return d.incidentId ? maNgan(d.incidentId) : '';
    case 'vi_tri_doi':
      return `${d.lat.toFixed(5)}, ${d.lon.toFixed(5)}`;
  }
}

interface Props {
  banGhi: BanGhi;
  now: number;
  choTinGoc?: boolean;
  onGuiLai: () => void;
  onXoa: () => void;
}

export function TheBanGhi({ banGhi: b, now, choTinGoc, onGuiLai, onXoa }: Props) {
  const { t } = useTranslation();
  const { Icon, mau } = BIEU_TUONG[b.trangThai];
  const gio = new Date(b.lanThuTiep).toLocaleTimeString();
  return (
    <View style={[THE.coBan, styles.the]} testID={`ban-ghi-${b.id}`}>
      <View style={styles.dau}>
        <Text style={CHU.nhan}>{t(`hangDoi.loai.${b.duLieu.loai}`)}</Text>
        <View style={styles.trangThai}>
          <Icon color={mau} size={18} />
          <Text style={[styles.chuTrangThai, { color: mau }]}>{t(`hangDoi.trangThai.${b.trangThai}`)}</Text>
        </View>
      </View>
      <Text style={CHU.thuong} numberOfLines={2}>
        {tomTat(b)}
      </Text>
      <Text style={CHU.phu}>{thoiGianTruoc(b.taoLuc, now, t)}</Text>
      {b.trangThai === 'cho_gui' && choTinGoc ? <Text style={CHU.phu}>{t('hangDoi.choTinGoc')}</Text> : null}
      {b.loi ? (
        <Text style={styles.loi}>
          {t(b.loi.khoa)}
          {b.loi.chiTiet ? ` ${b.loi.chiTiet}` : ''}
          {b.trangThai === 'cho_gui' && b.lanThuTiep > now ? ` ${t('hangDoi.thuLaiSau', { gio })}` : ''}
        </Text>
      ) : null}
      {b.ketQua?.maTin && b.duLieu.loai === 'keu_cuu' ? (
        <Text style={CHU.nhan}>{t('hangDoi.maTin', { ma: maNgan(b.ketQua.maTin) })}</Text>
      ) : null}
      {b.ketQua?.maHangCho ? <Text style={CHU.nhan}>{t('hangDoi.maHangCho', { ma: maNgan(b.ketQua.maHangCho) })}</Text> : null}
      {b.ketQua?.phatLai ? <Text style={CHU.phu}>{t('hangDoi.phatLai')}</Text> : null}
      {b.trangThai === 'loi' || b.trangThai === 'cho_gui' ? (
        <View style={styles.nut}>
          <View style={styles.o}>
            <Nut nhan={t('hangDoi.guiLai')} kieu="phu" onPress={onGuiLai} testID={`gui-lai-${b.id}`} />
          </View>
          <View style={styles.o}>
            <Nut nhan={t('chung.xoa')} kieu="nguy" onPress={onXoa} testID={`xoa-${b.id}`} />
          </View>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  the: { gap: KHOANG.xs },
  dau: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: KHOANG.sm },
  trangThai: { flexDirection: 'row', alignItems: 'center', gap: KHOANG.xs },
  chuTrangThai: { fontWeight: '700' },
  loi: { color: MAU.loi, fontWeight: '600' },
  nut: { flexDirection: 'row', gap: KHOANG.sm, marginTop: KHOANG.sm },
  o: { flex: 1 },
});
