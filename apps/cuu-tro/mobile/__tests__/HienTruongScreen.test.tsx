// SPDX-License-Identifier: Apache-2.0
// Rà soát UX hiện trường (#113): màn Hiện trường khi mạng yếu (bản sao mã hóa nạp lại sau khi mở app, mốc
// "cập nhật … trước", báo đang xem bản đã tải), màn Dán tin (nút ở chân màn, gợi ý lối không cần mạng khi bóc
// tách lỗi), chữ lớn (ngưỡng phóng to, nút thẻ hàng đợi xếp dọc, băng mạng chữ cỡ thường).
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import React from 'react';
import { StyleSheet, Text } from 'react-native';
import { BangMang } from '@/components/BangMang';
import { TheBanGhi } from '@/components/TheBanGhi';
import { useChuLon } from '@/hooks/useChuLon';
import { khoiTaoI18n } from '@/i18n';
import { DanTinScreen } from '@/screens/DanTinScreen';
import { HienTruongScreen } from '@/screens/HienTruongScreen';
import { datKhoBanSao, type KhoBanSao } from '@/services/banSao';
import { bocTach } from '@/services/bocTach';
import { layTinCuaToi } from '@/services/graphql';
import { useAuthStore } from '@/stores/authStore';
import { useHangDoiStore } from '@/stores/hangDoiStore';
import { useMangStore } from '@/stores/mangStore';
import { CO_CHU } from '@/theme';
import type { TinCuaToi } from '@/types/api';
import type { BanGhi } from '@/utils/hangDoi';

jest.mock('@/services/graphql', () => ({ layTinCuaToi: jest.fn(), layDoiCuaToi: jest.fn() }));
jest.mock('@/services/bocTach', () => ({ bocTach: jest.fn() }));
const mockCoChu = { fontScale: 1 };
jest.mock('react-native/Libraries/Utilities/useWindowDimensions', () => ({
  __esModule: true,
  default: () => ({ width: 360, height: 780, scale: 3, fontScale: mockCoChu.fontScale }),
}));

const TIN: TinCuaToi = {
  id: 'a1b2c3d4-0000-4000-8000-000000000001',
  status: 'phan_cong',
  urgency: 'khan_cap',
  description: 'Nước ngập tới mái, 3 người trên nóc nhà',
  address_text: 'Thôn 2 (giả định)',
  people_count: 3,
  created_at: '2026-10-28T01:00:00Z',
  toaDo: [108.2, 15.9],
};
const NGUOI = { sub: 'sub-1', tenDangNhap: 'tinhnguyen01', hoTen: null, vaiTro: ['tinh-nguyen' as const] };

let khoGia: Record<string, string>;
let qc: QueryClient;

function boc(ui: React.ReactElement) {
  // gcTime vô hạn: không để hẹn giờ dọn cache giữ tiến trình Jest sau khi chạy xong
  qc = new QueryClient({ defaultOptions: { queries: { retry: false, networkMode: 'offlineFirst', gcTime: Infinity } } });
  const Stack = createNativeStackNavigator();
  return render(
    <QueryClientProvider client={qc}>
      <NavigationContainer>
        <Stack.Navigator>
          <Stack.Screen name="Man">{() => ui}</Stack.Screen>
        </Stack.Navigator>
      </NavigationContainer>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  khoiTaoI18n('vi');
  khoGia = {};
  const kho: KhoBanSao = { doc: async t => khoGia[t] ?? null, ghi: async (t, s) => {
      khoGia[t] = s;
    },
  };
  datKhoBanSao(kho);
  useAuthStore.setState({ nguoiDung: NGUOI, trangThai: 'da_dang_nhap' });
  useHangDoiStore.setState({ ds: [] });
  mockCoChu.fontScale = 1;
  jest.mocked(layTinCuaToi).mockReset();
});

afterEach(() => {
  qc?.clear();
});

describe('Hiện trường khi mạng yếu', () => {
  it('mở lại app khi mất mạng: hiện danh sách từ bản sao, nói rõ đã tải bao lâu trước', async () => {
    useMangStore.getState().datTrangThai(false);
    jest.mocked(layTinCuaToi).mockRejectedValue(new Error('Network Error'));
    khoGia['tin-cua-toi'] = JSON.stringify({ v: 1, chu: 'sub-1|tinh-nguyen', luc: Date.now() - 12 * 60_000, duLieu: [TIN] });
    boc(<HienTruongScreen />);
    expect(await screen.findByText(TIN.description)).toBeTruthy();
    expect(
      await screen.findByText('Mất mạng: đang xem danh sách đã tải 12 phút trước, có thể đã cũ.'),
    ).toBeTruthy();
    // Trạng thái tin ở cỡ chữ thường (không phải chữ phụ nhỏ)
    expect(StyleSheet.flatten(screen.getByText('Đã phân công').props.style).fontSize).toBe(CO_CHU.thuong);
    // Mất mạng không hiện thêm thông báo lỗi tải
    expect(screen.queryByText('Không tải được danh sách. Kéo xuống để thử lại.')).toBeNull();
  });

  it('bản sao của người dùng khác không hiện', async () => {
    useMangStore.getState().datTrangThai(false);
    jest.mocked(layTinCuaToi).mockRejectedValue(new Error('Network Error'));
    khoGia['tin-cua-toi'] = JSON.stringify({ v: 1, chu: 'sub-9|tinh-nguyen', luc: Date.now(), duLieu: [TIN] });
    boc(<HienTruongScreen />);
    expect(await screen.findByText('Chưa có tin nào.')).toBeTruthy();
    expect(screen.queryByText(TIN.description)).toBeNull();
  });

  it('có mạng: tải từ máy chủ, hiện "Cập nhật vừa xong", ghi bản sao cho lần mất mạng sau', async () => {
    useMangStore.getState().datTrangThai(true);
    jest.mocked(layTinCuaToi).mockResolvedValue([TIN]);
    boc(<HienTruongScreen />);
    expect(await screen.findByText(TIN.description)).toBeTruthy();
    expect(await screen.findByText('Cập nhật vừa xong')).toBeTruthy();
    await waitFor(() => expect(khoGia['tin-cua-toi']).toBeDefined());
    const g = JSON.parse(khoGia['tin-cua-toi']!);
    expect(g).toMatchObject({ v: 1, chu: 'sub-1|tinh-nguyen', duLieu: [TIN] });
    expect(Math.abs(Date.now() - g.luc)).toBeLessThan(10_000);
  });
});

describe('Dán tin', () => {
  it('bóc tách lỗi (mạng yếu, AI quá hạn): báo lỗi và gợi ý chuyển cho điều phối, nút ở chân màn', async () => {
    useMangStore.getState().datTrangThai(true);
    jest.mocked(bocTach).mockResolvedValue({ ok: false, loi: { khoa: 'loi.mang', tamThoi: true } as never });
    boc(<DanTinScreen navigation={{ goBack: jest.fn() } as never} route={{} as never} />);
    fireEvent.changeText(await screen.findByTestId('o-van-ban'), 'Cứu với, nhà ngập, 0935111222');
    await act(async () => {
      fireEvent.press(screen.getByTestId('nut-boc-tach'));
    });
    expect(await screen.findByTestId('goi-y-chuyen')).toBeTruthy();
    expect(screen.getByText('Chưa tới được máy chủ (mất mạng). Sẽ tự gửi lại.')).toBeTruthy();
    // Chuyển cho điều phối (không cần mạng) xóa gợi ý, tin vào hàng đợi
    act(() => useMangStore.getState().datTrangThai(false));
    await act(async () => {
      fireEvent.press(screen.getByTestId('nut-chuyen'));
    });
    expect(screen.queryByTestId('goi-y-chuyen')).toBeNull();
    expect(useHangDoiStore.getState().ds[0]?.duLieu).toMatchObject({ loai: 'chuyen_tin' });
  });
});

describe('chữ lớn', () => {
  function DoChuLon() {
    return <Text testID="chu-lon">{String(useChuLon())}</Text>;
  }

  it('ngưỡng phóng to chữ hệ thống 1,3', () => {
    mockCoChu.fontScale = 1.29;
    const r = render(<DoChuLon />);
    expect(screen.getByTestId('chu-lon').props.children).toBe('false');
    r.unmount();
    mockCoChu.fontScale = 1.3;
    render(<DoChuLon />);
    expect(screen.getByTestId('chu-lon').props.children).toBe('true');
  });

  it('thẻ hàng đợi: Gửi lại / Xóa cạnh nhau ở cỡ thường, xếp dọc khi chữ lớn', () => {
    const b = {
      id: 'b1',
      khoa: 'k',
      taoLuc: Date.now(),
      lanThuTiep: Date.now(),
      soLanThu: 1,
      trangThai: 'loi',
      loi: { khoa: 'loi.khac' },
      duLieu: { loai: 'vi_tri_doi', doiId: 'd', lat: 15.9, lon: 108.2, luc: '2026-10-28T01:00:00Z' },
    } as unknown as BanGhi;
    const huong = () => {
      let n = screen.getByTestId('gui-lai-b1').parent;
      while (n) {
        const fd = StyleSheet.flatten(n.props.style)?.flexDirection;
        if (fd) {
          return fd;
        }
        n = n.parent;
      }
      return null;
    };
    const r = render(<TheBanGhi banGhi={b} now={Date.now()} onGuiLai={jest.fn()} onXoa={jest.fn()} />);
    expect(huong()).toBe('row');
    r.unmount();
    mockCoChu.fontScale = 2;
    render(<TheBanGhi banGhi={b} now={Date.now()} onGuiLai={jest.fn()} onXoa={jest.fn()} />);
    expect(huong()).toBe('column');
  });

  it('băng mất mạng dùng chữ cỡ thường, đậm', () => {
    useMangStore.getState().datTrangThai(false);
    render(<BangMang />);
    const st = StyleSheet.flatten(
      screen.getByText('Mất mạng: mọi thứ bạn gửi được lưu trên máy và tự gửi khi có mạng.').props.style,
    );
    expect(st).toMatchObject({ fontSize: CO_CHU.thuong, fontWeight: '700' });
  });
});
