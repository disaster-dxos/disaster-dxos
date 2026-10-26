// SPDX-License-Identifier: Apache-2.0
// Dán tin nhắn kêu cứu viết tự do (SMS, Zalo, ghi lại cuộc gọi):
//  - "Bóc tách bằng AI" (cần mạng): POST /workflow/ai/boc-tach (#102) → điền sẵn form kêu cứu, người dùng soát
//    lại từng ô rồi mới gửi (không tự gửi);
//  - "Chuyển cho điều phối duyệt" (không cần mạng): bản ghi chuyen_tin vào hàng đợi → khi có mạng gửi
//    /workflow/ai/boc-tach với vao_hang_cho (#104), điều phối viên duyệt trên web.
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Forward, Sparkles } from 'lucide-react-native';
import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { StyleSheet, Text } from 'react-native';
import { ChonMuc } from '@/components/ChonMuc';
import { ManHinh } from '@/components/ManHinh';
import { Nut } from '@/components/Nut';
import { OVanBan } from '@/components/OVanBan';
import type { RootStackParamList } from '@/navigation/types';
import { bocTach } from '@/services/bocTach';
import { useHangDoiStore } from '@/stores/hangDoiStore';
import { useMangStore } from '@/stores/mangStore';
import { useNhapTinStore } from '@/stores/nhapTinStore';
import { CHU, MAU } from '@/theme';
import { DS_NGUON_VAN_BAN, type NguonVanBan } from '@/types/api';
import { VAN_BAN_TOI_DA } from '@/utils/kiemTra';

type Props = NativeStackScreenProps<RootStackParamList, 'DanTin'>;

export function DanTinScreen({ navigation }: Props) {
  const { t } = useTranslation();
  const coMang = useMangStore(s => s.coMang);
  const [vanBan, setVanBan] = useState('');
  const [nguon, setNguon] = useState<NguonVanBan>('zalo');
  const [dangBocTach, setDangBocTach] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [daChuyen, setDaChuyen] = useState(false);
  const dsNguon = useMemo(() => DS_NGUON_VAN_BAN.map(n => ({ giaTri: n, nhan: t(`nguon.${n}`) })), [t]);

  const trong = () => {
    if (!vanBan.trim()) {
      setLoi(t('danTin.trong'));
      return true;
    }
    return false;
  };

  const bocTachAi = async () => {
    setLoi(null);
    if (trong()) {
      return;
    }
    if (!coMang) {
      setLoi(t('danTin.canMang'));
      return;
    }
    setDangBocTach(true);
    try {
      const r = await bocTach(vanBan.trim(), nguon);
      if (!r.ok) {
        setLoi([t(r.loi.khoa), r.loi.chiTiet].filter(Boolean).join(' '));
        return;
      }
      useNhapTinStore.getState().apDeXuat(r.kq);
      navigation.goBack();
    } finally {
      setDangBocTach(false);
    }
  };

  const chuyen = async () => {
    setLoi(null);
    if (trong()) {
      return;
    }
    await useHangDoiStore.getState().them({ loai: 'chuyen_tin', vanBan: vanBan.trim(), nguon });
    setVanBan('');
    setDaChuyen(true);
  };

  return (
    <ManHinh moTa={t('danTin.moTa')}>
      <OVanBan
        nhan={t('danTin.oNhap')}
        value={vanBan}
        onChangeText={s => {
          setVanBan(s);
          setDaChuyen(false);
        }}
        nhieuDong
        maxLength={VAN_BAN_TOI_DA}
        loi={loi}
        testID="o-van-ban"
      />
      <ChonMuc<NguonVanBan> nhan={t('danTin.nguon')} giaTri={nguon} dsMuc={dsNguon} onChon={setNguon} />
      {daChuyen ? <Text style={[CHU.nhan, styles.ok]}>{t('danTin.daChuyen')}</Text> : null}
      <Nut
        nhan={dangBocTach ? t('danTin.dangBocTach') : t('danTin.bocTach')}
        BieuTuong={Sparkles}
        onPress={bocTachAi}
        dangChay={dangBocTach}
        testID="nut-boc-tach"
      />
      <Nut nhan={t('danTin.chuyenDieuPhoi')} kieu="phu" BieuTuong={Forward} onPress={chuyen} testID="nut-chuyen" />
      <Text style={CHU.phu}>{t('danTin.chuyenDieuPhoiMoTa')}</Text>
    </ManHinh>
  );
}

const styles = StyleSheet.create({
  ok: { color: MAU.thanhCong },
});
