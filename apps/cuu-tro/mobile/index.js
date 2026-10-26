// SPDX-License-Identifier: Apache-2.0
// Điểm vào của app. Polyfill crypto.getRandomValues PHẢI nạp trước mọi mã khác: khóa idempotency và PKCE
// cần số ngẫu nhiên an toàn (Hermes không có sẵn crypto.getRandomValues).
import 'react-native-get-random-values';
import { AppRegistry } from 'react-native';
import App from './src/App';
import { name as appName } from './app.json';

AppRegistry.registerComponent(appName, () => App);
