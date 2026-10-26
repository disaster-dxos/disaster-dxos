// SPDX-License-Identifier: Apache-2.0
// Vị trí hiện tại (GPS) một lần, có xin quyền. Android xin ACCESS_FINE_LOCATION lúc chạy; iOS hỏi theo
// NSLocationWhenInUseUsageDescription. Lỗi trả khóa i18n để màn hình báo và gợi ý chọn trên bản đồ.
import Geolocation from '@react-native-community/geolocation';
import { useCallback, useState } from 'react';
import { PermissionsAndroid, Platform } from 'react-native';

export interface ViTri {
  lat: number;
  lon: number;
  /** Sai số (m) */
  doChinhXac: number | null;
}

Geolocation.setRNConfiguration({ skipPermissionRequests: false, authorizationLevel: 'whenInUse', locationProvider: 'auto' });

async function xinQuyen(): Promise<boolean> {
  if (Platform.OS !== 'android') {
    return true;
  }
  const r = await PermissionsAndroid.request(PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION);
  return r === PermissionsAndroid.RESULTS.GRANTED;
}

export function layViTri(): Promise<ViTri> {
  return new Promise((resolve, reject) => {
    Geolocation.getCurrentPosition(
      p => resolve({ lat: p.coords.latitude, lon: p.coords.longitude, doChinhXac: p.coords.accuracy ?? null }),
      e => reject(new Error(e.code === 1 ? 'quyen.viTriBiTuChoi' : 'quyen.gpsLoi')),
      { enableHighAccuracy: true, timeout: 20_000, maximumAge: 30_000 },
    );
  });
}

export function useViTri() {
  const [dangLay, setDangLay] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const lay = useCallback(async (): Promise<ViTri | null> => {
    setLoi(null);
    setDangLay(true);
    try {
      if (!(await xinQuyen())) {
        setLoi('quyen.viTriBiTuChoi');
        return null;
      }
      return await layViTri();
    } catch (e) {
      setLoi(e instanceof Error && e.message.startsWith('quyen.') ? e.message : 'quyen.gpsLoi');
      return null;
    } finally {
      setDangLay(false);
    }
  }, []);
  return { lay, dangLay, loi };
}
