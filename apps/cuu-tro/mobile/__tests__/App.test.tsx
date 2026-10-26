// SPDX-License-Identifier: Apache-2.0
// App khởi động khi chưa có phiên: hiện màn đăng nhập (tiếng Việt mặc định), không gọi mạng.
import { render, screen } from '@testing-library/react-native';
import React from 'react';
import App from '@/App';

it('chưa đăng nhập → màn Đăng nhập', async () => {
  render(<App />);
  expect(await screen.findByTestId('nut-dang-nhap')).toBeTruthy();
  expect(screen.getByText('Cứu trợ hiện trường')).toBeTruthy();
});
