// SPDX-License-Identifier: Apache-2.0
// Bản đồ MapLibre (@maplibre/maplibre-react-native, MIT; không dùng bản đồ Google/Apple). Kiểu nền vector
// OpenFreeMap (dữ liệu © OpenStreetMap, ghi công hiện ở nút (i)), cùng nguồn với web điều phối. Chạm để chọn
// điểm khi `onChon`; ghim cam đánh dấu vị trí người cần cứu.
import { Camera, Map as BanDoMapLibre, Marker, type CameraRef } from '@maplibre/maplibre-react-native';
import { MapPin } from 'lucide-react-native';
import React, { useEffect, useRef } from 'react';
import { StyleSheet, View } from 'react-native';
import { MAC_DINH, TAM_MAC_DINH } from '@/config/env';
import { BO_GOC, MAU } from '@/theme';

interface Props {
  /** [kinh độ, vĩ độ] */
  diem: [number, number] | null;
  onChon?: (lngLat: [number, number]) => void;
  cao?: number;
  testID?: string;
}

export function BanDo({ diem, onChon, cao, testID }: Props) {
  const cam = useRef<CameraRef>(null);
  useEffect(() => {
    if (diem) {
      cam.current?.flyTo({ center: diem, zoom: 15, duration: 600 });
    }
  }, [diem]);
  return (
    <View style={[styles.khung, cao ? { height: cao } : styles.day]} testID={testID}>
      <BanDoMapLibre
        style={styles.day}
        mapStyle={MAC_DINH.mapStyleUrl}
        logo={false}
        compass={false}
        onPress={onChon ? e => onChon(e.nativeEvent.lngLat) : undefined}
        accessibilityLabel="map"
      >
        <Camera ref={cam} initialViewState={{ center: diem ?? TAM_MAC_DINH, zoom: diem ? 15 : 10 }} />
        {diem ? (
          <Marker id="diem-chon" lngLat={diem} anchor="bottom">
            <View>
              <MapPin color={MAU.trang} fill={MAU.cam} size={40} strokeWidth={1.5} />
            </View>
          </Marker>
        ) : null}
      </BanDoMapLibre>
    </View>
  );
}

const styles = StyleSheet.create({
  khung: { overflow: 'hidden', borderRadius: BO_GOC.vua, borderWidth: 1, borderColor: MAU.vien },
  day: { flex: 1 },
});
