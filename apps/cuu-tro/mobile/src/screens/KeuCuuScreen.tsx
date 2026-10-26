// SPDX-License-Identifier: Apache-2.0
// Gửi tin kêu cứu: form (SĐT, số người, mức khẩn, tình hình, địa chỉ) + vị trí (GPS hoặc chọn trên bản đồ) +
// ảnh kèm. Kiểm ngay trên máy theo cùng luật với API (utils/kiemTra.ts); hợp lệ thì vào hàng đợi offline với
// khóa idempotency mới và gửi ngay nếu có mạng. Ảnh kèm là bản ghi riêng, chờ tin lên máy chủ rồi gắn mã tin thật.
// "Dán tin nhắn" mở màn AI bóc tách để điền sẵn form (người dùng soát rồi mới gửi).
import { useNavigation, type NavigationProp } from '@react-navigation/native';
import { Camera, ClipboardPaste, Crosshair, Map as MapIcon, Send } from 'lucide-react-native';
import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { StyleSheet, Text, View } from 'react-native';
import { BanDo } from '@/components/BanDo';
import { ChonMuc } from '@/components/ChonMuc';
import { ManHinh } from '@/components/ManHinh';
import { Nut } from '@/components/Nut';
import { OVanBan } from '@/components/OVanBan';
import { useViTri } from '@/hooks/useViTri';
import type { RootStackParamList } from '@/navigation/types';
import { chupAnh, LoiQuyenCamera } from '@/services/chupAnh';
import { useHangDoiStore } from '@/stores/hangDoiStore';
import { useNhapTinStore } from '@/stores/nhapTinStore';
import { CHU, KHOANG, MAU, MAU_MUC_KHAN, THE } from '@/theme';
import { DS_MUC_KHAN, type MucKhan } from '@/types/api';
import { DIA_CHI_TOI_DA, kiemTraKeuCuu, MO_TA_TOI_DA, TEN_TOI_DA, type LoiForm } from '@/utils/kiemTra';
import { taoKhoa } from '@/utils/khoaIdempotency';

export function KeuCuuScreen() {
  const { t } = useTranslation();
  const nav = useNavigation<NavigationProp<RootStackParamList>>();
  const { form, anhKem, tuAi, sua, themAnh, xoaHet } = useNhapTinStore();
  const viTri = useViTri();
  const [loi, setLoi] = useState<LoiForm[]>([]);
  const [daLuu, setDaLuu] = useState(false);
  const [dangGui, setDangGui] = useState(false);
  const [loiAnh, setLoiAnh] = useState<string | null>(null);

  const loiCua = (truong: LoiForm['truong']) => {
    const l = loi.find(x => x.truong === truong);
    return l ? t(l.khoa, l.thamSo) : null;
  };
  const dsMuc = useMemo(
    () => DS_MUC_KHAN.map(m => ({ giaTri: m, nhan: t(`mucKhan.${m}`), mau: MAU_MUC_KHAN[m] })),
    [t],
  );
  const diem: [number, number] | null = form.lat !== null && form.lon !== null ? [form.lon, form.lat] : null;

  const layGps = async () => {
    const p = await viTri.lay();
    if (p) {
      sua({ lat: p.lat, lon: p.lon });
    }
  };

  const themAnhKem = async () => {
    setLoiAnh(null);
    try {
      const a = await chupAnh('camera', taoKhoa());
      if (a) {
        themAnh(a);
      }
    } catch (e) {
      setLoiAnh(e instanceof LoiQuyenCamera ? t(e.message) : String(e));
    }
  };

  const gui = async () => {
    const { body, loi: dsLoi } = kiemTraKeuCuu(form);
    setLoi(dsLoi);
    if (!body) {
      return;
    }
    setDangGui(true);
    try {
      const hd = useHangDoiStore.getState();
      const tin = await hd.them({ loai: 'keu_cuu', tin: body });
      for (const a of anhKem) {
        await hd.them({ loai: 'anh', tuBanGhi: tin.id, duongDan: a.duongDan, contentType: a.contentType });
      }
      xoaHet();
      setLoi([]);
      setDaLuu(true);
    } finally {
      setDangGui(false);
    }
  };

  return (
    <ManHinh
      tieuDe={t('keuCuu.tieuDe')}
      moTa={t('keuCuu.moTaManHinh')}
      chan={<Nut nhan={t('keuCuu.gui')} kieu="cam" BieuTuong={Send} onPress={gui} dangChay={dangGui} testID="nut-gui" />}
    >
      {daLuu ? (
        <View style={[styles.bao, styles.baoOk]} accessibilityLiveRegion="polite" testID="da-luu">
          <Text style={CHU.nhan}>{t('keuCuu.daVaoHangDoi')}</Text>
        </View>
      ) : null}
      {tuAi ? (
        <View style={[styles.bao, styles.baoAi]}>
          <Text style={CHU.nhan}>{t('keuCuu.deXuatAi')}</Text>
        </View>
      ) : null}
      <Nut
        nhan={t('keuCuu.danTin')}
        kieu="phu"
        BieuTuong={ClipboardPaste}
        onPress={() => {
          setDaLuu(false);
          nav.navigate('DanTin');
        }}
        testID="nut-dan-tin"
      />

      <View style={[THE.coBan, styles.khoi]}>
        <Text style={CHU.nhan}>{t('keuCuu.viTri')}</Text>
        {diem ? (
          <>
            <BanDo diem={diem} cao={180} />
            <Text style={CHU.phu}>{`${diem[1].toFixed(5)}, ${diem[0].toFixed(5)}`}</Text>
          </>
        ) : (
          <Text style={[CHU.phu, loiCua('lat') ? styles.chuLoi : null]}>{loiCua('lat') ?? t('keuCuu.chuaCoViTri')}</Text>
        )}
        {viTri.loi ? <Text style={styles.chuLoi}>{t(viTri.loi)}</Text> : null}
        <View style={styles.hang}>
          <View style={styles.o}>
            <Nut
              nhan={viTri.dangLay ? t('keuCuu.dangLayGps') : t('keuCuu.layGps')}
              BieuTuong={Crosshair}
              onPress={layGps}
              dangChay={viTri.dangLay}
              testID="nut-gps"
            />
          </View>
          <View style={styles.o}>
            <Nut nhan={t('keuCuu.chonTrenBanDo')} kieu="phu" BieuTuong={MapIcon} onPress={() => nav.navigate('ChonViTri')} />
          </View>
        </View>
      </View>

      <OVanBan
        nhan={t('keuCuu.sdt')}
        phu={t('chung.batBuoc')}
        value={form.sdt}
        onChangeText={sdt => sua({ sdt })}
        keyboardType="phone-pad"
        loi={loiCua('sdt')}
        testID="o-sdt"
      />
      <ChonMuc<MucKhan> nhan={t('keuCuu.mucKhan')} giaTri={form.mucKhan} dsMuc={dsMuc} onChon={mucKhan => sua({ mucKhan })} testID="muc-khan" />
      <OVanBan
        nhan={t('keuCuu.soNguoi')}
        value={form.soNguoi}
        onChangeText={soNguoi => sua({ soNguoi })}
        keyboardType="number-pad"
        loi={loiCua('soNguoi')}
        testID="o-so-nguoi"
      />
      <OVanBan
        nhan={t('keuCuu.moTa')}
        phu={t('chung.batBuoc')}
        value={form.moTa}
        onChangeText={moTa => sua({ moTa })}
        goiY={t('keuCuu.moTaGoiY')}
        nhieuDong
        maxLength={MO_TA_TOI_DA}
        loi={loiCua('moTa')}
        testID="o-mo-ta"
      />
      <OVanBan
        nhan={t('keuCuu.diaChi')}
        phu={t('chung.khongBatBuoc')}
        value={form.diaChi}
        onChangeText={diaChi => sua({ diaChi })}
        maxLength={DIA_CHI_TOI_DA}
        loi={loiCua('diaChi')}
      />
      <OVanBan
        nhan={t('keuCuu.ten')}
        phu={t('chung.khongBatBuoc')}
        value={form.ten}
        onChangeText={ten => sua({ ten })}
        maxLength={TEN_TOI_DA}
        loi={loiCua('ten')}
      />
      <View style={styles.khoi}>
        <Nut nhan={t('keuCuu.chupAnh')} kieu="phu" BieuTuong={Camera} onPress={themAnhKem} testID="nut-anh-kem" />
        {anhKem.length ? <Text style={CHU.phu}>{t('keuCuu.soAnhKem', { count: anhKem.length })}</Text> : null}
        {loiAnh ? <Text style={styles.chuLoi}>{loiAnh}</Text> : null}
      </View>
    </ManHinh>
  );
}

const styles = StyleSheet.create({
  khoi: { gap: KHOANG.sm },
  hang: { flexDirection: 'row', gap: KHOANG.sm },
  o: { flex: 1 },
  bao: { borderRadius: 12, padding: KHOANG.md },
  baoOk: { backgroundColor: MAU.thanhCongNhat },
  baoAi: { backgroundColor: MAU.nuocNhat },
  chuLoi: { color: MAU.loi, fontWeight: '600' },
});
