// SPDX-License-Identifier: Apache-2.0
// crypto.getRandomValues: Hermes không có sẵn, polyfill react-native-get-random-values nạp ở index.js.
declare const crypto: {
  getRandomValues<T extends Uint8Array>(a: T): T;
};

/** Hermes (React Native ≥ 0.74) và Node đều có atob */
declare function atob(data: string): string;
declare function btoa(data: string): string;
