// SPDX-License-Identifier: Apache-2.0
// Gửi tin kêu cứu: form (SĐT, số người, mức khẩn, tình hình, địa chỉ) + vị trí (GPS hoặc chọn trên bản đồ) +
// ảnh kèm. Kiểm ngay trên máy theo cùng luật với API (utils/kiemTra.ts); hợp lệ thì vào hàng đợi offline với
// khóa idempotency mới và gửi ngay nếu có mạng. Ảnh kèm là bản ghi riêng, chờ tin lên máy chủ rồi gắn mã tin thật.
// "Dán tin nhắn" mở màn AI bóc tách để điền sẵn form (người dùng soát rồi mới gửi).
// Một tay (#113): nút Gửi ở chân màn; form sai thì tóm tắt lỗi hiện ngay trên nút (trình đọc màn hình đọc to) và
// màn tự cuộn tới ô lỗi đầu tiên, vì các ô lỗi thường đã cuộn khuất phía trên. GPS báo sai số; mất mạng thì báo
// nền bản đồ có thể không hiện (tọa độ vẫn đúng). Chữ lớn: hai nút vị trí xếp dọc.
import { useNavigation, type NavigationProp } from '@react-navigation/native';
import { Camera, ClipboardPaste, Crosshair, Map as MapIcon, Send } from 'lucide-react-native';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AccessibilityInfo, Pressable, StyleSheet, Text, View, type LayoutChangeEvent, type ScrollView } from 'react-native';
import { BanDo } from '@/components/BanDo';
import { ChonMuc } from '@/components/ChonMuc';
import { ManHinh } from '@/components/ManHinh';
import { Nut } from '@/components/Nut';
import { OVanBan } from '@/components/OVanBan';
import { useChuLon } from '@/hooks/useChuLon';
import { useViTri } from '@/hooks/useViTri';
import type { RootStackParamList } from '@/navigation/types';
import { chupAnh, LoiQuyenCamera } from '@/services/chupAnh';
import { useHangDoiStore } from '@/stores/hangDoiStore';
import { useMangStore } from '@/stores/mangStore';
import { useNhapTinStore } from '@/stores/nhapTinStore';
import { CHU, CO_CHU, KHOANG, MAU, MAU_MUC_KHAN, THE } from '@/theme';
import { DS_MUC_KHAN, type MucKhan } from '@/types/api';
import { DIA_CHI_TOI_DA, kiemTraKeuCuu, MO_TA_TOI_DA, TEN_TOI_DA, type LoiForm } from '@/utils/kiemTra';
import { taoKhoa } from '@/utils/khoaIdempotency';

type Truong = LoiForm['truong'];

/** Nhãn ô theo trường lỗi (tóm tắt lỗi); lat/lon cùng là ô Vị trí */
const NHAN_TRUONG: Partial<Record<Truong, string>> = {
  lat: 'keuCuu.viTri',
  lon: 'keuCuu.viTri',
  sdt: 'keuCuu.sdt',
  soNguoi: 'keuCuu.soNguoi',
  moTa: 'keuCuu.moTa',
  diaChi: 'keuCuu.diaChi',
  ten: 'keuCuu.ten',
};

/** Sai số GPS (m) từ mức này coi là chưa chính xác: lệch cả một xóm, đội cứu hộ khó tìm */
export const SAI_SO_GPS_LON = 100;

export function KeuCuuScreen() {
  const { t } = useTranslation();
  const nav = useNavigation<NavigationProp<RootStackParamList>>();
  const { form, anhKem, tuAi, saiSoGps, sua, datViTri, themAnh, xoaHet } = useNhapTinStore();
  const viTri = useViTri();
  const coMang = useMangStore(s => s.coMang);
  const chuLon = useChuLon();
  const cuon = useRef<ScrollView>(null);
  const viTriO = useRef<Partial<Record<Truong, number>>>({});
  const moc = (...truong: Truong[]) => (e: LayoutChangeEvent) => {
    for (const tr of truong) {
      viTriO.current[tr] = e.nativeEvent.layout.y;
    }
  };
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
  // Sau một lần bấm Gửi có lỗi: kiểm lại theo từng thay đổi, lỗi đã sửa biến mất ngay (tóm tắt không nói sai)
  const daCoLoi = loi.length > 0;
  useEffect(() => {
    if (daCoLoi) {
      setLoi(kiemTraKeuCuu(form).loi);
    }
  }, [form, daCoLoi]);
  const diem: [number, number] | null = form.lat !== null && form.lon !== null ? [form.lon, form.lat] : null;
  const tenLoi = [...new Set(loi.map(l => NHAN_TRUONG[l.truong]).filter((k): k is string => !!k))].map(k => t(k));
  const tomTatLoi = tenLoi.length ? t('keuCuu.conLoi', { count: tenLoi.length, ds: tenLoi.join(', ') }) : null;

  const toiOLoiDau = (ds: LoiForm[] = loi) => {
    const y = ds.map(l => viTriO.current[l.truong]).filter((v): v is number => v !== undefined);
    cuon.current?.scrollTo({ y: y.length ? Math.max(0, Math.min(...y) - KHOANG.lg) : 0, animated: true });
  };

  const layGps = async () => {
    const p = await viTri.lay();
    if (p) {
      datViTri(p.lat, p.lon, p.doChinhXac);
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
      setDaLuu(false);
      toiOLoiDau(dsLoi);
      const ten = [...new Set(dsLoi.map(l => NHAN_TRUONG[l.truong]).filter((k): k is string => !!k))].map(k => t(k));
      AccessibilityInfo.announceForAccessibility(t('keuCuu.conLoi', { count: ten.length, ds: ten.join(', ') }));
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
      cuonRef={cuon}
      chan={
        <>
          {tomTatLoi ? (
            <Pressable
              accessibilityRole="button"
              onPress={() => toiOLoiDau()}
              style={styles.tomTatLoi}
              testID="tom-tat-loi"
            >
              <Text style={styles.chuTomTatLoi}>{tomTatLoi}</Text>
            </Pressable>
          ) : null}
          <Nut nhan={t('keuCuu.gui')} kieu="cam" BieuTuong={Send} onPress={gui} dangChay={dangGui} testID="nut-gui" />
        </>
      }
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

      <View style={[THE.coBan, styles.khoi]} onLayout={moc('lat', 'lon')}>
        <Text style={CHU.nhan}>{t('keuCuu.viTri')}</Text>
        {diem ? (
          <>
            <BanDo diem={diem} cao={180} />
            {coMang ? null : <Text style={CHU.phu}>{t('banDo.matMang')}</Text>}
            <Text style={CHU.phu}>{`${diem[1].toFixed(5)}, ${diem[0].toFixed(5)}`}</Text>
            {saiSoGps !== null ? (
              <Text
                style={saiSoGps >= SAI_SO_GPS_LON ? styles.chuCanhBao : CHU.phu}
                testID="sai-so-gps"
              >
                {t(saiSoGps >= SAI_SO_GPS_LON ? 'keuCuu.saiSoLon' : 'keuCuu.saiSo', { m: Math.round(saiSoGps) })}
              </Text>
            ) : null}
          </>
        ) : (
          <Text style={[CHU.phu, loiCua('lat') ? styles.chuLoi : null]}>{loiCua('lat') ?? t('keuCuu.chuaCoViTri')}</Text>
        )}
        {viTri.loi ? <Text style={styles.chuLoi}>{t(viTri.loi)}</Text> : null}
        <View style={chuLon ? styles.khoi : styles.hang}>
          <View style={chuLon ? undefined : styles.o}>
            <Nut
              nhan={viTri.dangLay ? t('keuCuu.dangLayGps') : t('keuCuu.layGps')}
              BieuTuong={Crosshair}
              onPress={layGps}
              dangChay={viTri.dangLay}
              testID="nut-gps"
            />
          </View>
          <View style={chuLon ? undefined : styles.o}>
            <Nut nhan={t('keuCuu.chonTrenBanDo')} kieu="phu" BieuTuong={MapIcon} onPress={() => nav.navigate('ChonViTri')} />
          </View>
        </View>
      </View>

      <View onLayout={moc('sdt')}>
        <OVanBan
          nhan={t('keuCuu.sdt')}
          phu={t('chung.batBuoc')}
          value={form.sdt}
          onChangeText={sdt => sua({ sdt })}
          keyboardType="phone-pad"
          loi={loiCua('sdt')}
          testID="o-sdt"
        />
      </View>
      <ChonMuc<MucKhan> nhan={t('keuCuu.mucKhan')} giaTri={form.mucKhan} dsMuc={dsMuc} onChon={mucKhan => sua({ mucKhan })} testID="muc-khan" />
      <View onLayout={moc('soNguoi')}>
        <OVanBan
          nhan={t('keuCuu.soNguoi')}
          value={form.soNguoi}
          onChangeText={soNguoi => sua({ soNguoi })}
          keyboardType="number-pad"
          loi={loiCua('soNguoi')}
          testID="o-so-nguoi"
        />
      </View>
      <View onLayout={moc('moTa')}>
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
      </View>
      <View onLayout={moc('diaChi')}>
        <OVanBan
          nhan={t('keuCuu.diaChi')}
          phu={t('chung.khongBatBuoc')}
          value={form.diaChi}
          onChangeText={diaChi => sua({ diaChi })}
          maxLength={DIA_CHI_TOI_DA}
          loi={loiCua('diaChi')}
        />
      </View>
      <View onLayout={moc('ten')}>
        <OVanBan
          nhan={t('keuCuu.ten')}
          phu={t('chung.khongBatBuoc')}
          value={form.ten}
          onChangeText={ten => sua({ ten })}
          maxLength={TEN_TOI_DA}
          loi={loiCua('ten')}
        />
      </View>
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
  chuLoi: { color: MAU.loi, fontWeight: '600', fontSize: CO_CHU.thuong },
  chuCanhBao: { color: MAU.canhBao, fontWeight: '600', fontSize: CO_CHU.thuong },
  tomTatLoi: { backgroundColor: MAU.loiNhat, borderRadius: 12, padding: KHOANG.md },
  chuTomTatLoi: { color: MAU.loi, fontWeight: '700', fontSize: CO_CHU.thuong },
});
