// SPDX-License-Identifier: Apache-2.0
// Jest cho app hiện trường: logic thuần (hàng đợi, kiểm tra, lỗi API, JWT), store với lưu trữ/mạng giả, gọi API
// với adapter axios giả, và vài màn hình render bằng @testing-library/react-native. Không cần máy ảo.
module.exports = {
  preset: 'react-native',
  setupFiles: ['<rootDir>/jest.setup.js'],
  moduleNameMapper: {
    '^@logo/(.*)$': '<rootDir>/__tests__/__mocks__/anh.js',
    '^@/(.*)$': '<rootDir>/src/$1',
  },
  testPathIgnorePatterns: ['/node_modules/', '/__tests__/__mocks__/'],
  transformIgnorePatterns: [
    'node_modules/(?!(?:@react-native|react-native|@react-navigation|react-native-.*|@maplibre|lucide-react-native)/)',
  ],
};
