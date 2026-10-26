// SPDX-License-Identifier: Apache-2.0
// Cài đặt: tài khoản + vai, ngôn ngữ (Tiếng Việt / English), máy chủ (API Gateway, Keycloak), đăng xuất.
// Đổi máy chủ dùng cho máy dev, máy chủ của xã, VPS demo; đổi xong phải đăng nhập lại (token gắn với Keycloak).
import { LogOut, Save } from 'lucide-react-native';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Alert, StyleSheet, Text, View } from 'react-native';
import { ChonMuc } from '@/components/ChonMuc';
import { ManHinh } from '@/components/ManHinh';
import { Nut } from '@/components/Nut';
import { OVanBan } from '@/components/OVanBan';
import { NGON_NGU, TEN_NGON_NGU, type NgonNgu } from '@/i18n';
import { useAuthStore } from '@/stores/authStore';
import { chuanHoaUrl, useCaiDatStore } from '@/stores/caiDatStore';
import { useHangDoiStore } from '@/stores/hangDoiStore';
import { CHU, KHOANG, MAU, THE } from '@/theme';
import { version } from '../../package.json';
import { boQua } from '@/utils/boQua';

export function MayChuForm() {
  const { t } = useTranslation();
  const caiDat = useCaiDatStore();
  const [gateway, setGateway] = useState(caiDat.gatewayUrl);
  const [keycloak, setKeycloak] = useState(caiDat.keycloakUrl);
  const [loi, setLoi] = useState<{ g?: string; k?: string }>({});
  const [daLuu, setDaLuu] = useState(false);

  const luu = async () => {
    const g = chuanHoaUrl(gateway);
    const k = chuanHoaUrl(keycloak);
    setLoi({ g: g ? undefined : t('caiDat.urlSai'), k: k ? undefined : t('caiDat.urlSai') });
    if (!g || !k) {
      return;
    }
    const doiKeycloak = k !== caiDat.keycloakUrl;
    await caiDat.luuMayChu(g, k);
    setDaLuu(true);
    if (doiKeycloak && useAuthStore.getState().trangThai === 'da_dang_nhap') {
      await useAuthStore.getState().dangXuat();
    }
  };

  return (
    <View style={[THE.coBan, styles.khoi]}>
      <Text style={CHU.muc}>{t('caiDat.mayChu')}</Text>
      <OVanBan nhan={t('caiDat.gateway')} value={gateway} onChangeText={setGateway} keyboardType="url" loi={loi.g} testID="o-gateway" />
      <OVanBan nhan={t('caiDat.keycloak')} value={keycloak} onChangeText={setKeycloak} keyboardType="url" loi={loi.k} testID="o-keycloak" />
      <Nut nhan={t('chung.luu')} kieu="phu" BieuTuong={Save} onPress={luu} testID="nut-luu-may-chu" />
      {daLuu ? <Text style={[CHU.nhan, styles.ok]}>{t('caiDat.daLuu')}</Text> : null}
    </View>
  );
}

export function CaiDatMayChuScreen() {
  return (
    <ManHinh>
      <MayChuForm />
    </ManHinh>
  );
}

export function CaiDatScreen() {
  const { t } = useTranslation();
  const nguoiDung = useAuthStore(s => s.nguoiDung);
  const ngonNgu = useCaiDatStore(s => s.ngonNgu);
  const chuaGui = useHangDoiStore(s => s.ds.filter(b => b.trangThai !== 'da_gui').length);

  const dangXuat = () => {
    const lam = () => boQua(useAuthStore.getState().dangXuat());
    if (chuaGui > 0) {
      Alert.alert(t('caiDat.dangXuat'), t('caiDat.dangXuatCanhBao', { count: chuaGui }), [
        { text: t('chung.huy'), style: 'cancel' },
        { text: t('caiDat.dangXuat'), style: 'destructive', onPress: lam },
      ]);
    } else {
      lam();
    }
  };

  return (
    <ManHinh tieuDe={t('caiDat.tieuDe')}>
      <View style={[THE.coBan, styles.khoi]}>
        <Text style={CHU.muc}>{t('caiDat.taiKhoan')}</Text>
        <Text style={CHU.thuong}>{nguoiDung?.hoTen ?? nguoiDung?.tenDangNhap}</Text>
        <Text style={CHU.phu}>
          {t('caiDat.vaiTro')}: {nguoiDung?.vaiTro.map(v => t(`vaiTro.${v}`)).join(', ')}
        </Text>
        <Nut nhan={t('caiDat.dangXuat')} kieu="nguy" BieuTuong={LogOut} onPress={dangXuat} testID="nut-dang-xuat" />
      </View>
      <View style={[THE.coBan, styles.khoi]}>
        <ChonMuc<NgonNgu>
          nhan={t('caiDat.ngonNgu')}
          giaTri={ngonNgu}
          dsMuc={NGON_NGU.map(n => ({ giaTri: n, nhan: TEN_NGON_NGU[n] }))}
          onChon={n => boQua(useCaiDatStore.getState().doiNgonNgu(n))}
          testID="ngon-ngu"
        />
      </View>
      <MayChuForm />
      <Text style={[CHU.phu, styles.giua]}>
        {t('caiDat.phienBan', { v: version })}
        {'\n'}
        {t('caiDat.giayPhep')}
      </Text>
    </ManHinh>
  );
}

const styles = StyleSheet.create({
  khoi: { gap: KHOANG.sm },
  ok: { color: MAU.thanhCong },
  giua: { textAlign: 'center' },
});
