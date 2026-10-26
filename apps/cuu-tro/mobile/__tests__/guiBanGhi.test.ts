// SPDX-License-Identifier: Apache-2.0
// Mỗi loại bản ghi gọi đúng endpoint qua gateway, kèm header Idempotency-Key = khóa của bản ghi.
import type { KetQuaGoi } from '@/services/api';
import { guiBanGhi, type PhuThuocGui } from '@/services/guiBanGhi';
import { taoBanGhi } from '@/utils/hangDoi';

function pt(r: KetQuaGoi<unknown>, conTep = true) {
  const goi = jest.fn(async () => r) as unknown as PhuThuocGui['goi'] & jest.Mock;
  const taiTep = jest.fn(async () => r as KetQuaGoi<{ id: string }>);
  const xoaTep = jest.fn(async () => undefined);
  return { goi, taiTep, xoaTep, conTrenMay: jest.fn(async () => conTep) };
}

const TIN = { lat: 15.95, lon: 108.25, reporter_phone: '0935111222', description: 'Ngập', source: 'app' as const };

describe('gửi bản ghi', () => {
  it('kêu cứu: POST /workflow/keu-cuu + Idempotency-Key; phát lại từ máy chủ', async () => {
    const p = pt({ ok: true, status: 201, data: { id: 'inc-1' }, phatLai: true });
    const b = taoBanGhi({ loai: 'keu_cuu', tin: TIN }, 0);
    expect(await guiBanGhi(b, undefined, p)).toEqual({ ok: true, phatLai: true, maTin: 'inc-1' });
    expect(p.goi).toHaveBeenCalledWith({
      method: 'POST',
      url: '/workflow/keu-cuu',
      data: TIN,
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': b.khoa },
    });
  });

  it('chuyển tin: /workflow/ai/boc-tach với vao_hang_cho, trả mã hàng chờ', async () => {
    const p = pt({ ok: true, status: 200, data: { hang_cho: { id: 'hc-1' } }, phatLai: false });
    const b = taoBanGhi({ loai: 'chuyen_tin', vanBan: 'cứu', nguon: 'zalo' }, 0);
    expect(await guiBanGhi(b, undefined, p)).toEqual({ ok: true, phatLai: false, maHangCho: 'hc-1' });
    expect(p.goi.mock.calls[0][0]).toMatchObject({
      url: '/workflow/ai/boc-tach',
      data: { van_ban: 'cứu', nguon: 'zalo', vao_hang_cho: true },
      headers: { 'Idempotency-Key': b.khoa },
    });
  });

  it('ảnh: tải tệp lên /workflow/tai-len/su-co/{id}/anh, xóa tệp khi xong', async () => {
    const p = pt({ ok: true, status: 201, data: { id: 'anh-1' }, phatLai: false });
    const b = taoBanGhi({ loai: 'anh', tuBanGhi: 'x', duongDan: '/d/a.jpg', contentType: 'image/jpeg' }, 0);
    expect(await guiBanGhi(b, 'inc-5', p)).toEqual({ ok: true, phatLai: false, maTin: 'inc-5', maAnh: 'anh-1' });
    expect(p.taiTep).toHaveBeenCalledWith(
      '/workflow/tai-len/su-co/inc-5/anh',
      { 'Content-Type': 'image/jpeg', 'Idempotency-Key': b.khoa },
      '/d/a.jpg',
    );
    expect(p.xoaTep).toHaveBeenCalledWith('/d/a.jpg');
  });

  it('ảnh không còn trên máy → lỗi vĩnh viễn, không gọi mạng', async () => {
    const p = pt({ ok: true, status: 201, data: {}, phatLai: false }, false);
    const b = taoBanGhi({ loai: 'anh', incidentId: 'inc-5', duongDan: '/d/a.jpg', contentType: 'image/jpeg' }, 0);
    expect(await guiBanGhi(b, 'inc-5', p)).toMatchObject({ ok: false, loai: 'vinh_vien', khoa: 'loi.anhMat' });
    expect(p.taiTep).not.toHaveBeenCalled();
  });

  it('vị trí đội: GraphQL vai cuu-ho, chỉ ghi khi mới hơn (không dùng _is_null: WAF chặn)', async () => {
    const p = pt({ ok: true, status: 200, data: { data: { update_rescue_teams: { affected_rows: 1 } } }, phatLai: false });
    const b = taoBanGhi({ loai: 'vi_tri_doi', doiId: 'doi-1', lat: 15.9, lon: 108.2, luc: '2026-10-26T01:00:00Z' }, 0);
    expect(await guiBanGhi(b, undefined, p)).toEqual({ ok: true, phatLai: false });
    const goi = p.goi.mock.calls[0][0];
    expect(goi.headers['X-Hasura-Role']).toBe('cuu-ho');
    expect(goi.data.query).toContain('location_updated_at: {_lt: $luc}');
    expect(goi.data.query).not.toContain('_is_null');
    expect(goi.data.variables).toEqual({ id: 'doi-1', p: { type: 'Point', coordinates: [108.2, 15.9] }, luc: '2026-10-26T01:00:00Z' });
  });

  it('vị trí đội: 0 dòng vì đã có vị trí mới hơn → bỏ qua; đội chưa có vị trí → ghi lần đầu', async () => {
    const b = taoBanGhi({ loai: 'vi_tri_doi', doiId: 'doi-1', lat: 15.9, lon: 108.2, luc: '2026-10-26T01:00:00Z' }, 0);
    const traLoi = (...ds: unknown[]) => {
      const goi = jest.fn();
      for (const d of ds) {
        goi.mockResolvedValueOnce({ ok: true, status: 200, data: d, phatLai: false });
      }
      return { ...pt({ ok: true, status: 200, data: {}, phatLai: false }), goi } as never;
    };
    const moiHon = traLoi(
      { data: { update_rescue_teams: { affected_rows: 0 } } },
      { data: { rescue_teams_by_pk: { location_updated_at: '2026-10-26T02:00:00Z' } } },
    );
    expect(await guiBanGhi(b, undefined, moiHon)).toEqual({ ok: true, phatLai: true });
    const lanDau = traLoi(
      { data: { update_rescue_teams: { affected_rows: 0 } } },
      { data: { rescue_teams_by_pk: { location_updated_at: null } } },
      { data: { update_rescue_teams: { affected_rows: 1 } } },
    );
    expect(await guiBanGhi(b, undefined, lanDau)).toEqual({ ok: true, phatLai: false });
    expect((lanDau as unknown as { goi: jest.Mock }).goi.mock.calls[2][0].data.query).toContain('ViTriDoiDau');
    const p2 = pt({ ok: true, status: 200, data: { errors: [{ message: 'permission' }] }, phatLai: false });
    expect(await guiBanGhi(b, undefined, p2)).toMatchObject({ ok: false, loai: 'vinh_vien' });
  });

  it('lỗi HTTP được phân loại (mất mạng tạm, 409 tin trùng vĩnh viễn)', async () => {
    const b = taoBanGhi({ loai: 'keu_cuu', tin: TIN }, 0);
    expect(await guiBanGhi(b, undefined, pt({ ok: false, status: 0, detail: null }))).toMatchObject({ loai: 'tam' });
    const tr = await guiBanGhi(b, undefined, pt({ ok: false, status: 409, detail: { ma: 'tin_trung', incident_id: 'i' } }));
    expect(tr).toMatchObject({ ok: false, loai: 'vinh_vien', maTinTrung: 'i' });
  });
});
