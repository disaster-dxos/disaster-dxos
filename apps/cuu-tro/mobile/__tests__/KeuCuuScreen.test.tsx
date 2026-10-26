// SPDX-License-Identifier: Apache-2.0
// Màn gửi kêu cứu: báo lỗi theo trường ngay trên máy (không cần mạng), lấy GPS, tin hợp lệ vào hàng đợi offline
// (không gửi trực tiếp) với khóa idempotency, form được xóa để nhập tin mới.
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import React from 'react';
import { khoiTaoI18n } from '@/i18n';
import { KeuCuuScreen } from '@/screens/KeuCuuScreen';
import { useHangDoiStore } from '@/stores/hangDoiStore';
import { useMangStore } from '@/stores/mangStore';
import { useNhapTinStore } from '@/stores/nhapTinStore';
import { khoaHopLe } from '@/utils/khoaIdempotency';

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
});
