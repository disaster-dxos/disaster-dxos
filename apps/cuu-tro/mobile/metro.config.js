// SPDX-License-Identifier: Apache-2.0
// Metro theo dõi thêm docs/images/logo/ của repo để app dùng chung logo với web điều phối (alias '@logo').
const path = require('path');
const { getDefaultConfig, mergeConfig } = require('@react-native/metro-config');

/** @type {import('@react-native/metro-config').MetroConfig} */
const config = {
  watchFolders: [path.resolve(__dirname, '../../../docs/images/logo')],
};

module.exports = mergeConfig(getDefaultConfig(__dirname), config);
