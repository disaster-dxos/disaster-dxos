// SPDX-License-Identifier: Apache-2.0
// Làm mới access token (#108): lỗi mạng/lỗi lạ giữ phiên và báo lỗi tạm; chỉ Keycloak từ chối refresh token
// (invalid_grant…) mới xóa phiên. Nhiều lời gọi cùng lúc chỉ làm mới một lần.
import { refresh } from 'react-native-app-auth';
import { useAuthStore } from '@/stores/authStore';
import { LoiTamToken, phienBiTuChoi } from '@/utils/loiPhien';

const refreshMock = refresh as jest.Mock;
const HASURA = 'https://hasura.io/jwt/claims';

function jwt(sub: string): string {
  const b64 = (o: object) => btoa(JSON.stringify(o)).replace(/[=]+$/, '').replace(/\+/g, '-').replace(/\//g, '_');
  return `${b64({ alg: 'RS256' })}.${b64({ sub, preferred_username: sub, [HASURA]: { 'x-hasura-allowed-roles': ['tinh-nguyen'] } })}.k`;
}

function datPhien(hetHan: number) {
  useAuthStore.setState({
    trangThai: 'da_dang_nhap',
    token: { accessToken: jwt('tn'), refreshToken: 'rt', idToken: 'id', hetHan },
    nguoiDung: { sub: 'tn', tenDangNhap: 'tn', hoTen: null, vaiTro: ['tinh-nguyen'] },
  });
}

beforeEach(() => refreshMock.mockReset());

describe('phân loại lỗi làm mới token', () => {
  it.each([
    ['invalid_grant', true],
    ['Token is not active', true],
    ['Session not active', true],
    ['Offline user session not found', true],
    ['unauthorized_client', true],
    ['Network error', false],
    ['The Internet connection appears to be offline.', false],
    ['The request timed out.', false],
    ['Unable to resolve host "keycloak.xa.vn"', false],
    ['Trust anchor for certification path not found.', false],
    ['HTTP 502', false],
    ['lỗi gì đó không rõ', false],
  ])('"%s" → xóa phiên: %s', (msg, xoa) => {
    expect(phienBiTuChoi(new Error(msg))).toBe(xoa);
  });

  it('đọc cả code và userInfo của lỗi native', () => {
    const e = Object.assign(new Error('token_refresh_failed'), { userInfo: { error: 'invalid_grant' } });
    expect(phienBiTuChoi(e)).toBe(true);
  });
});

describe('authStore.layToken', () => {
  it('token còn hạn: trả ngay, không gọi Keycloak', async () => {
    datPhien(Date.now() + 10 * 60_000);
    expect(await useAuthStore.getState().layToken()).toBe(jwt('tn'));
    expect(refreshMock).not.toHaveBeenCalled();
  });

  it('mất mạng khi làm mới: GIỮ phiên, ném LoiTamToken', async () => {
    datPhien(Date.now() - 1);
    refreshMock.mockRejectedValue(new Error('Unable to resolve host'));
    await expect(useAuthStore.getState().layToken()).rejects.toBeInstanceOf(LoiTamToken);
    expect(useAuthStore.getState()).toMatchObject({ trangThai: 'da_dang_nhap' });
    expect(useAuthStore.getState().token).not.toBeNull();
  });

  it('Keycloak từ chối refresh token: xóa phiên, trả null', async () => {
    datPhien(Date.now() - 1);
    refreshMock.mockRejectedValue(new Error('invalid_grant: Token is not active'));
    expect(await useAuthStore.getState().layToken()).toBeNull();
    expect(useAuthStore.getState()).toMatchObject({ trangThai: 'chua_dang_nhap', token: null });
  });

  it('làm mới thành công: lưu token mới; nhiều lời gọi cùng lúc chỉ làm mới một lần', async () => {
    datPhien(Date.now() - 1);
    refreshMock.mockResolvedValue({
      accessToken: jwt('tn2'),
      accessTokenExpirationDate: new Date(Date.now() + 900_000).toISOString(),
      idToken: 'id2',
      refreshToken: null,
      tokenType: 'Bearer',
    });
    const ds = await Promise.all([1, 2, 3].map(() => useAuthStore.getState().layToken()));
    expect(new Set(ds)).toEqual(new Set([jwt('tn2')]));
    expect(refreshMock).toHaveBeenCalledTimes(1);
    // Keycloak không trả refresh token mới thì giữ cái cũ
    expect(useAuthStore.getState().token).toMatchObject({ refreshToken: 'rt', idToken: 'id2' });
  });

  it('chưa đăng nhập: null, không gọi Keycloak', async () => {
    useAuthStore.setState({ trangThai: 'chua_dang_nhap', token: null, nguoiDung: null });
    expect(await useAuthStore.getState().layToken()).toBeNull();
    expect(refreshMock).not.toHaveBeenCalled();
  });
});
