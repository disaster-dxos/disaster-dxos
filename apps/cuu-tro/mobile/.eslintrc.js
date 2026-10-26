// SPDX-License-Identifier: Apache-2.0
// ESLint của React Native + cấm mã màu viết tay ngoài src/theme (màu nhận diện Team 1 nằm ở một chỗ).
module.exports = {
  root: true,
  extends: '@react-native',
  ignorePatterns: ['android/', 'ios/', 'coverage/', 'node_modules/'],
  rules: {
    'no-restricted-syntax': [
      'error',
      {
        selector: 'Literal[value=/^#(?:[0-9a-fA-F]{3,4}){1,2}$/]',
        message: 'Không viết mã màu ở đây: dùng MAU trong src/theme.',
      },
    ],
  },
  overrides: [
    { files: ['src/theme/**/*.ts'], rules: { 'no-restricted-syntax': 'off' } },
    { files: ['jest.setup.js', '**/__tests__/**'], env: { jest: true } },
  ],
};
