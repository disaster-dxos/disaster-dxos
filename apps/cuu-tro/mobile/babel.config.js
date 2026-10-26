// SPDX-License-Identifier: Apache-2.0
// Babel của React Native + alias đường dẫn: '@/…' → src/ (khớp tsconfig.json, jest.config.js),
// '@logo/…' → bộ logo dùng chung của repo docs/images/logo/ (không chép bản sao vào app).
module.exports = {
  presets: ['module:@react-native/babel-preset'],
  plugins: [
    [
      'module-resolver',
      {
        root: ['./src'],
        alias: { '@': './src', '@logo': '../../../docs/images/logo' },
        extensions: ['.ts', '.tsx', '.js', '.jsx', '.json'],
      },
    ],
  ],
};
