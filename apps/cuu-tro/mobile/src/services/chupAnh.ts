// SPDX-License-Identifier: Apache-2.0
// Chụp/chọn ảnh hiện trường (react-native-image-picker, MIT) rồi chép vào thư mục riêng của app để chờ gửi.
// Thu nhỏ còn cạnh dài 1600 px, JPEG 70%: đủ nhìn rõ hiện trường, nhẹ khi mạng yếu (API nhận tối đa 10 MiB).
import { PermissionsAndroid, Platform } from 'react-native';
import { launchCamera, launchImageLibrary, type ImagePickerResponse } from 'react-native-image-picker';
import type { AnhKem } from '@/stores/nhapTinStore';
import { chepVaoApp } from './anhCucBo';

const TUY_CHON = { mediaType: 'photo', maxWidth: 1600, maxHeight: 1600, quality: 0.7, saveToPhotos: false } as const;

export class LoiQuyenCamera extends Error {}

async function xinQuyenCamera(): Promise<boolean> {
  if (Platform.OS !== 'android') {
    return true;
  }
  const r = await PermissionsAndroid.request(PermissionsAndroid.PERMISSIONS.CAMERA);
  return r === PermissionsAndroid.RESULTS.GRANTED;
}

/** Ảnh đã chép vào app; null nếu người dùng bỏ qua. Không có quyền camera → LoiQuyenCamera. */
export async function chupAnh(nguon: 'camera' | 'thu_vien', ten: string): Promise<AnhKem | null> {
  let r: ImagePickerResponse;
  if (nguon === 'camera') {
    if (!(await xinQuyenCamera())) {
      throw new LoiQuyenCamera('quyen.cameraBiTuChoi');
    }
    r = await launchCamera(TUY_CHON);
  } else {
    r = await launchImageLibrary({ ...TUY_CHON, selectionLimit: 1 });
  }
  const a = r.assets?.[0];
  if (r.didCancel || !a?.uri) {
    return null;
  }
  if (r.errorCode === 'permission') {
    throw new LoiQuyenCamera('quyen.cameraBiTuChoi');
  }
  const contentType = a.type === 'image/png' || a.type === 'image/webp' ? a.type : 'image/jpeg';
  return { duongDan: await chepVaoApp(a.uri, ten, contentType), contentType };
}
