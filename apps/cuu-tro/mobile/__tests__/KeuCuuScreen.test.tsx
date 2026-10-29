// SPDX-License-Identifier: Apache-2.0
// Màn gửi kêu cứu: báo lỗi theo trường ngay trên máy (không cần mạng), lấy GPS, tin hợp lệ vào hàng đợi offline
// (không gửi trực tiếp) với khóa idempotency, form được xóa để nhập tin mới. Rà soát UX (#113): tóm tắt lỗi ở chân
// màn cạnh nút Gửi + đọc to cho trình đọc màn hình, sai số GPS, báo nền bản đồ khi mất mạng, chữ lớn.
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import Geolocation from '@react-native-community/geolocation';
import React from 'react';
import { AccessibilityInfo } from 'react-native';
import * as RN from 'react-native';
import { khoiTaoI18n } from '@/i18n';
import { KeuCuuScreen } from '@/screens/KeuCuuScreen';
import { useHangDoiStore } from '@/stores/hangDoiStore';
import { useMangStore } from '@/stores/mangStore';
import { useNhapTinStore } from '@/stores/nhapTinStore';
import { khoaHopLe } from '@/utils/khoaIdempotency';

// Mức phóng to chữ hệ thống (mock Dimensions của React Native mặc định fontScale 2, máy thường là 1)
const mockChuLon = { bat: false };
jest.mock('@/hooks/useChuLon', () => ({ useChuLon: () => mockChuLon.bat, NGUONG_CHU_LON: 1.3 }));

const Stack = createNativeStackNavigator();

function manHinh() {
  return render(
    <NavigationContainer>
      <Stack.Navigator>
        <Stack.Screen name="KeuCuu" component={KeuCuuScreen} />
      </Stack.Navigator>
    </NavigationContainer>,
  );
}

beforeEach(() => {
  khoiTaoI18n('vi');
  useMangStore.getState().datTrangThai(false);
  useNhapTinStore.getState().xoaHet();
  useHangDoiStore.setState({ ds: [] });
  mockChuLon.bat = false;
});

describe('màn gửi kêu cứu', () => {
  it('thiếu vị trí, SĐT, mô tả: báo lỗi từng trường, không vào hàng đợi', async () => {
    manHinh();
    fireEvent.press(await screen.findByTestId('nut-gui'));
    expect(await screen.findByText('Thiếu số điện thoại.')).toBeTruthy();
    expect(screen.getByText('Mô tả ngắn tình hình.')).toBeTruthy();
    expect(screen.getByText('Thiếu vị trí: lấy GPS hoặc chọn trên bản đồ.')).toBeTruthy();
    expect(useHangDoiStore.getState().ds).toEqual([]);
  });

  it('điền đủ + GPS: tin vào hàng đợi (mất mạng vẫn được), có khóa idempotency, form trống lại', async () => {
    manHinh();
    fireEvent.changeText(await screen.findByTestId('o-sdt'), '0935 111 222');
    fireEvent.changeText(screen.getByTestId('o-mo-ta'), 'Nước ngập tới mái');
    fireEvent.changeText(screen.getByTestId('o-so-nguoi'), '4');
    fireEvent.press(screen.getByTestId('muc-khan-khan_cap'));
    await act(async () => {
      fireEvent.press(screen.getByTestId('nut-gps'));
    });
    await waitFor(() => expect(useNhapTinStore.getState().form.lat).toBe(15.95));
    await act(async () => {
      fireEvent.press(screen.getByTestId('nut-gui'));
    });
    expect(await screen.findByTestId('da-luu')).toBeTruthy();
    const [b] = useHangDoiStore.getState().ds;
    expect(b?.duLieu).toEqual({
      loai: 'keu_cuu',
      tin: {
        lat: 15.95,
        lon: 108.25,
        reporter_phone: '0935111222',
        description: 'Nước ngập tới mái',
        urgency: 'khan_cap',
        people_count: 4,
        source: 'app',
      },
    });
    expect(khoaHopLe(b!.khoa)).toBe(true);
    expect(useNhapTinStore.getState().form.sdt).toBe('');
  });

  it('form sai: tóm tắt lỗi ngay trên nút Gửi (một tay), đọc to, chạm được', async () => {
    const doc = jest.spyOn(AccessibilityInfo, 'announceForAccessibility');
    manHinh();
    fireEvent.press(await screen.findByTestId('nut-gui'));
    const tomTat = 'Chưa gửi: còn 3 ô cần sửa (Vị trí, Số điện thoại người cần cứu, Tình hình). Chạm để tới ô đầu tiên.';
    expect(await screen.findByText(tomTat)).toBeTruthy();
    expect(doc).toHaveBeenCalledWith(tomTat);
    fireEvent.press(screen.getByTestId('tom-tat-loi'));
    // Sửa từng ô: tóm tắt cập nhật ngay, không chờ bấm Gửi lại
    fireEvent.changeText(screen.getByTestId('o-sdt'), '0935111222');
    expect(
      await screen.findByText('Chưa gửi: còn 2 ô cần sửa (Vị trí, Tình hình). Chạm để tới ô đầu tiên.'),
    ).toBeTruthy();
    expect(screen.queryByText('Thiếu số điện thoại.')).toBeNull();
    fireEvent.changeText(screen.getByTestId('o-mo-ta'), 'Ngập');
    await act(async () => {
      fireEvent.press(screen.getByTestId('nut-gps'));
    });
    await act(async () => {
      fireEvent.press(screen.getByTestId('nut-gui'));
    });
    expect(screen.queryByTestId('tom-tat-loi')).toBeNull();
    expect(await screen.findByTestId('da-luu')).toBeTruthy();
    doc.mockRestore();
  });

  it('GPS: hiện sai số; sai số lớn thì cảnh báo; mất mạng thì báo nền bản đồ có thể không hiện', async () => {
    manHinh();
    await act(async () => {
      fireEvent.press(await screen.findByTestId('nut-gps'));
    });
    expect(await screen.findByText('GPS sai số khoảng 12 m')).toBeTruthy();
    expect(screen.getByText('Không có mạng: nền bản đồ có thể không hiện. Vị trí GPS vẫn lấy được.')).toBeTruthy();
    jest.mocked(Geolocation.getCurrentPosition).mockImplementationOnce(ok =>
      ok({ coords: { latitude: 15.9, longitude: 108.2, accuracy: 240.4 } } as never),
    );
    await act(async () => {
      fireEvent.press(screen.getByTestId('nut-gps'));
    });
    expect(
      await screen.findByText('GPS chưa chính xác (sai số khoảng 240 m). Ra chỗ thoáng rồi lấy lại, hoặc chỉnh trên bản đồ.'),
    ).toBeTruthy();
    // Có mạng thì không báo về nền bản đồ
    act(() => useMangStore.getState().datTrangThai(true));
    expect(screen.queryByText(/nền bản đồ có thể không hiện/)).toBeNull();
  });

  it('vị trí chọn trên bản đồ không mang sai số GPS cũ', () => {
    useNhapTinStore.getState().datViTri(15.9, 108.2, 30);
    expect(useNhapTinStore.getState().saiSoGps).toBe(30);
    useNhapTinStore.getState().datViTri(15.91, 108.21, null);
    expect(useNhapTinStore.getState()).toMatchObject({ saiSoGps: null, form: { lat: 15.91, lon: 108.21 } });
  });

  it('chữ hệ thống phóng to: hai nút vị trí xếp dọc (cỡ thường: cạnh nhau)', async () => {
    const laHang = (st: Record<string, unknown>) => st.flexDirection === 'column' || st.flexDirection === 'row';
    const coBan = manHinh();
    expect(timToTien(await screen.findByTestId('nut-gps'), laHang)?.flexDirection).toBe('row');
    coBan.unmount();
    mockChuLon.bat = true;
    manHinh();
    expect(timToTien(await screen.findByTestId('nut-gps'), laHang)?.flexDirection).not.toBe('row');
  });
});

/** Style phẳng của tổ tiên gần nhất thỏa điều kiện (kiểm bố cục khi không có máy thật) */
function timToTien(
  node: { parent: unknown; props: { style?: unknown } } | null,
  dieuKien: (st: Record<string, unknown>) => boolean,
): Record<string, unknown> | null {
  let n = node?.parent as typeof node;
  while (n) {
    const st = (RN.StyleSheet.flatten(n.props.style as RN.StyleProp<RN.ViewStyle>) ?? {}) as Record<string, unknown>;
    if (dieuKien(st)) {
      return st;
    }
    n = n.parent as typeof node;
  }
  return null;
}
