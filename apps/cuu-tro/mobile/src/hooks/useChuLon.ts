// SPDX-License-Identifier: Apache-2.0
// Người dùng phóng to chữ hệ thống (Cài đặt → Cỡ chữ / Dynamic Type). Từ mức này hai nút cạnh nhau chuyển sang
// xếp dọc để nhãn không bị ngắt vụn (#113). App không chặn phóng to chữ ở đâu cả (không allowFontScaling={false}).
import { useWindowDimensions } from 'react-native';

export const NGUONG_CHU_LON = 1.3;

export function useChuLon(): boolean {
  return useWindowDimensions().fontScale >= NGUONG_CHU_LON;
}
