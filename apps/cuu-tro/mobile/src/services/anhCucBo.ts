// SPDX-License-Identifier: Apache-2.0
// Ảnh hiện trường chờ gửi: chép từ tệp tạm của camera/thư viện vào thư mục riêng của app (DocumentDir/hang-doi),
// vì hệ điều hành có thể dọn tệp tạm khi app đang chờ mạng. Gửi xong (hoặc người dùng xóa bản ghi) thì xóa tệp.
import ReactNativeBlobUtil from 'react-native-blob-util';

const THU_MUC = `${ReactNativeBlobUtil.fs.dirs.DocumentDir}/hang-doi`;

function boFile(uri: string): string {
  return decodeURIComponent(uri.replace(/^file:\/\//, ''));
}

export function duoiTep(contentType: string): string {
  return contentType === 'image/png' ? 'png' : contentType === 'image/webp' ? 'webp' : 'jpg';
}

export async function chepVaoApp(uri: string, ten: string, contentType: string): Promise<string> {
  if (!(await ReactNativeBlobUtil.fs.isDir(THU_MUC))) {
    await ReactNativeBlobUtil.fs.mkdir(THU_MUC);
  }
  const dich = `${THU_MUC}/${ten}.${duoiTep(contentType)}`;
  await ReactNativeBlobUtil.fs.cp(boFile(uri), dich);
  return dich;
}

export async function conTrenMay(duongDan: string): Promise<boolean> {
  return ReactNativeBlobUtil.fs.exists(duongDan);
}

export async function xoaTep(duongDan: string): Promise<void> {
  try {
    if (await ReactNativeBlobUtil.fs.exists(duongDan)) {
      await ReactNativeBlobUtil.fs.unlink(duongDan);
    }
  } catch {
    // Không xóa được tệp không làm hỏng hàng đợi
  }
}
