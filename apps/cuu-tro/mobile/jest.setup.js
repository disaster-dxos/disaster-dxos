// SPDX-License-Identifier: Apache-2.0
// Mock các module native (không có trong môi trường Node của Jest). Mock giữ đúng API mà app dùng, không rộng
// hơn: test xanh phải là bằng chứng mã gọi đúng thư viện thật.

jest.mock('@react-native-async-storage/async-storage', () =>
  require('@react-native-async-storage/async-storage/jest/async-storage-mock'),
);

// Keychain: lưu trong bộ nhớ theo `service` (API generic password thật dùng trong authStore, hangDoiStore)
jest.mock('react-native-keychain', () => {
  const kho = new Map();
  return {
    setGenericPassword: jest.fn(async (username, password, options) => {
      kho.set(options?.service ?? 'default', { username, password });
      return { service: options?.service ?? 'default', storage: 'mock' };
    }),
    getGenericPassword: jest.fn(async options => {
      const v = kho.get(options?.service ?? 'default');
      return v ? { ...v, service: options?.service ?? 'default', storage: 'mock' } : false;
    }),
    resetGenericPassword: jest.fn(async options => kho.delete(options?.service ?? 'default')),
    ACCESSIBLE: { AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY: 'AccessibleAfterFirstUnlockThisDeviceOnly' },
    __xoaHet: () => kho.clear(),
  };
});

jest.mock('@react-native-community/netinfo', () => ({
  __esModule: true,
  default: {
    fetch: jest.fn(() => Promise.resolve({ isConnected: true, isInternetReachable: true })),
    addEventListener: jest.fn(() => jest.fn()),
  },
}));

jest.mock('react-native-localize', () => ({
  findBestLanguageTag: jest.fn(() => ({ languageTag: 'vi', isRTL: false })),
}));

jest.mock('react-native-app-auth', () => ({
  authorize: jest.fn(),
  refresh: jest.fn(),
  logout: jest.fn(() => Promise.resolve()),
}));

jest.mock('react-native-image-picker', () => ({
  launchCamera: jest.fn(() => Promise.resolve({ didCancel: true })),
  launchImageLibrary: jest.fn(() => Promise.resolve({ didCancel: true })),
}));

jest.mock('@react-native-community/geolocation', () => ({
  __esModule: true,
  default: {
    setRNConfiguration: jest.fn(),
    getCurrentPosition: jest.fn(ok => ok({ coords: { latitude: 15.95, longitude: 108.25, accuracy: 12 } })),
  },
}));

jest.mock('react-native-blob-util', () => ({
  __esModule: true,
  default: {
    fs: {
      dirs: { DocumentDir: '/tmp/cuu-tro' },
      isDir: jest.fn(() => Promise.resolve(true)),
      mkdir: jest.fn(() => Promise.resolve()),
      cp: jest.fn(() => Promise.resolve(true)),
      exists: jest.fn(() => Promise.resolve(true)),
      unlink: jest.fn(() => Promise.resolve()),
    },
    wrap: jest.fn(p => `RNFetchBlob-file://${p}`),
    config: jest.fn(() => ({ fetch: jest.fn() })),
  },
}));

// Bản đồ native: View thay thế, giữ prop để test đọc được
jest.mock('@maplibre/maplibre-react-native', () => {
  const React = require('react');
  const { View } = require('react-native');
  const Map = props => React.createElement(View, { testID: 'maplibre-map', ...props }, props.children);
  const Camera = React.forwardRef((_props, _ref) => null);
  const Marker = props => React.createElement(View, { testID: 'maplibre-marker' }, props.children);
  return { Map, Camera, Marker };
});

jest.mock('react-native-safe-area-context', () => {
  const inset = { top: 0, right: 0, bottom: 0, left: 0 };
  return {
    ...jest.requireActual('react-native-safe-area-context'),
    SafeAreaProvider: ({ children }) => children,
    SafeAreaView: ({ children }) => children,
    useSafeAreaInsets: () => inset,
  };
});

// Biểu tượng lucide (SVG): thay bằng phần tử rỗng có tên, không cần react-native-svg native
jest.mock('lucide-react-native', () => new Proxy({}, { get: (_t, ten) => (ten === '__esModule' ? false : () => null) }));
