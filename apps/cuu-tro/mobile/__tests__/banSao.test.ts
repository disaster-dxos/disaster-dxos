// SPDX-License-Identifier: Apache-2.0
// Bản sao dữ liệu đọc của màn Hiện trường (#113): ghi/đọc qua Keychain (mock), gắn với người dùng + vai, bỏ bản
// hỏng, quá cũ, ở tương lai; lỗi lưu trữ không làm hỏng màn hình.
import * as Keychain from 'react-native-keychain';
import { datKhoBanSao, docBanSao, ghiBanSao, khoKeychain, TUOI_TOI_DA_MS, type KhoBanSao } from '@/services/banSao';

const NOW = Date.UTC(2026, 9, 28, 3, 0);
const CHU = 'sub-1|cuu-ho';

beforeEach(() => {
  (Keychain as unknown as { __xoaHet: () => void }).__xoaHet();
  datKhoBanSao(khoKeychain);
});

describe('bản sao dữ liệu đọc', () => {
  it('ghi rồi đọc lại đúng dữ liệu và mốc tải, lưu trong Keychain chỉ trên máy này', async () => {
    await ghiBanSao('tin-cua-toi', CHU, [{ id: 'a' }], NOW - 60_000);
    expect(await docBanSao('tin-cua-toi', CHU, NOW)).toEqual({ duLieu: [{ id: 'a' }], luc: NOW - 60_000 });
    expect(Keychain.setGenericPassword).toHaveBeenLastCalledWith('ban-sao', expect.any(String), {
      service: 'org.disasterdxos.cuutro.ban-sao.tin-cua-toi',
      accessible: Keychain.ACCESSIBLE.AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY,
    });
    // Mỗi loại dữ liệu một mục riêng
    expect(await docBanSao('doi-cua-toi', CHU, NOW)).toBeNull();
  });

  it('người khác hoặc vai khác trên cùng máy không đọc được', async () => {
    await ghiBanSao('tin-cua-toi', CHU, [{ id: 'a' }], NOW);
    expect(await docBanSao('tin-cua-toi', 'sub-2|cuu-ho', NOW)).toBeNull();
    expect(await docBanSao('tin-cua-toi', 'sub-1|tinh-nguyen', NOW)).toBeNull();
  });

  it('quá 7 ngày hoặc ở tương lai thì bỏ', async () => {
    await ghiBanSao('tin-cua-toi', CHU, [], NOW - TUOI_TOI_DA_MS - 1);
    expect(await docBanSao('tin-cua-toi', CHU, NOW)).toBeNull();
    await ghiBanSao('tin-cua-toi', CHU, [], NOW + 3600_000);
    expect(await docBanSao('tin-cua-toi', CHU, NOW)).toBeNull();
    await ghiBanSao('tin-cua-toi', CHU, [], NOW - TUOI_TOI_DA_MS + 1000);
    expect(await docBanSao('tin-cua-toi', CHU, NOW)).not.toBeNull();
  });

  it('nội dung hỏng, sai phiên bản, kho lỗi: trả null / bỏ qua, không ném lỗi', async () => {
    const hong: Record<string, string> = {};
    const kho: KhoBanSao = { doc: async t => hong[t] ?? null, ghi: async (t, s) => {
        hong[t] = s;
      },
    };
    datKhoBanSao(kho);
    hong.a = '{không phải json';
    expect(await docBanSao('a', CHU, NOW)).toBeNull();
    hong.a = JSON.stringify({ v: 99, chu: CHU, luc: NOW, duLieu: [] });
    expect(await docBanSao('a', CHU, NOW)).toBeNull();
    hong.a = JSON.stringify({ v: 1, chu: CHU, luc: 'hôm qua', duLieu: [] });
    expect(await docBanSao('a', CHU, NOW)).toBeNull();
    datKhoBanSao({
      doc: () => Promise.reject(new Error('Keychain bị khóa')),
      ghi: () => Promise.reject(new Error('Keychain đầy')),
    });
    await expect(ghiBanSao('a', CHU, [], NOW)).resolves.toBeUndefined();
    expect(await docBanSao('a', CHU, NOW)).toBeNull();
  });
});
