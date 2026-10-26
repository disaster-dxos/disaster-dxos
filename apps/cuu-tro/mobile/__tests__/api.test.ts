// SPDX-License-Identifier: Apache-2.0
// Client axios qua gateway: gắn Bearer token, làm mới khi 401 rồi gọi lại một lần, mất mạng → status 0,
// đọc header Idempotent-Replayed, lấy `detail` lỗi của API.
import type { AxiosRequestConfig, AxiosResponse } from 'axios';
import { taoApi } from '@/services/api';

function adapter(dsTraLoi: Array<Partial<AxiosResponse> | Error>) {
  const goi: AxiosRequestConfig[] = [];
  const fn = async (cfg: AxiosRequestConfig) => {
    goi.push(cfg);
    const r = dsTraLoi.shift();
    if (r instanceof Error || r === undefined) {
      throw r ?? new Error('Network Error');
    }
    return { data: null, status: 200, statusText: '', headers: {}, config: cfg, ...r } as AxiosResponse;
  };
  return { fn, goi };
}

describe('client API qua gateway', () => {
  const token = jest.fn(async (lamMoi?: boolean) => (lamMoi ? 'moi' : 'cu'));

  it('gắn Bearer + header của lời gọi, URL gateway, phát lại', async () => {
    const a = adapter([{ status: 201, data: { id: 'x' }, headers: { 'idempotent-replayed': 'true' } }]);
    const api = taoApi({ gatewayUrl: () => 'http://gw:9080', layToken: token }, a.fn as never);
    const r = await api.goi({ method: 'POST', url: '/workflow/keu-cuu', data: {}, headers: { 'Idempotency-Key': 'k-12345678' } });
    expect(r).toEqual({ ok: true, status: 201, data: { id: 'x' }, phatLai: true });
    expect(a.goi[0]?.baseURL).toBe('http://gw:9080');
    expect(a.goi[0]?.headers).toMatchObject({ Authorization: 'Bearer cu', 'Idempotency-Key': 'k-12345678' });
  });

  it('401 → làm mới token, gọi lại đúng một lần', async () => {
    const a = adapter([{ status: 401 }, { status: 200, data: {} }]);
    const api = taoApi({ gatewayUrl: () => 'http://gw', layToken: token }, a.fn as never);
    expect((await api.goi({ url: '/x' })).ok).toBe(true);
    expect(a.goi.map(c => (c.headers as Record<string, string>).Authorization)).toEqual(['Bearer cu', 'Bearer moi']);
  });

  it('mất mạng → status 0; lỗi API → detail; chưa đăng nhập → 401 không gọi mạng', async () => {
    const a = adapter([new Error('Network Error'), { status: 422, data: { detail: { ma: 'x' } } }]);
    const api = taoApi({ gatewayUrl: () => 'http://gw', layToken: token }, a.fn as never);
    expect(await api.goi({ url: '/x' })).toEqual({ ok: false, status: 0, detail: null });
    expect(await api.goi({ url: '/x' })).toEqual({ ok: false, status: 422, detail: { ma: 'x' } });
    const khong = taoApi({ gatewayUrl: () => 'http://gw', layToken: async () => null }, a.fn as never);
    expect(await khong.goi({ url: '/x' })).toEqual({ ok: false, status: 401, detail: null });
  });
});
