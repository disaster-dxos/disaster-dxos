// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest'
import {
  SUB_BAN_DO, chiTietTuKetQua, choKetNoiLai, httpGraphqlUrl, phanLoaiDong, queryChiTiet, tinTuHang, tinTuKetQua,
  toaDoTuGeoJson, wsGraphqlUrl,
} from '~/utils/tin-graphql'

const ID = 'd0000000-0000-4000-8000-000000000001'
// Hasura trả cột geography dạng GeoJSON kèm crs
const DIEM = { type: 'Point', crs: { type: 'name', properties: { name: 'urn:ogc:def:crs:EPSG::4326' } }, coordinates: [108.2212, 15.9785] }
const HANG = { id: ID, location: DIEM, urgency: 'khan_cap', status: 'tiep_nhan', created_at: '2026-10-29T07:56:00.123+00:00' }

describe('subscription bản đồ', () => {
  it('chỉ xin trường cần cho bản đồ, không SĐT, tên người gọi, mô tả', () => {
    const truong = /incidents\([^)]*\)\s*\{([^}]*)\}/.exec(SUB_BAN_DO)![1]!.trim().split(/\s+/)
    expect(truong.sort()).toEqual(['created_at', 'id', 'location', 'status', 'urgency'])
    expect(SUB_BAN_DO).toMatch(/^subscription /)
    expect(SUB_BAN_DO).not.toMatch(/reporter|description|created_by/)
  })
  it('query chi tiết: cột liên hệ chỉ với dieu-phoi, cuu-ho', () => {
    expect(queryChiTiet('dieu-phoi')).toContain('reporter_phone reporter_name assigned_team { name }')
    expect(queryChiTiet('cuu-ho')).toContain('reporter_phone')
    for (const v of ['tinh-nguyen', undefined, 'la']) {
      expect(queryChiTiet(v)).not.toMatch(/reporter|assigned_team|created_by/)
      expect(queryChiTiet(v)).toContain('description address_text people_count source')
    }
  })
  it('URL WebSocket và HTTP qua gateway', () => {
    expect(wsGraphqlUrl('http://localhost:9080')).toBe('ws://localhost:9080/graphql')
    expect(wsGraphqlUrl('https://cuutro.example.vn/x?y=1#z')).toBe('wss://cuutro.example.vn/graphql')
    expect(httpGraphqlUrl('http://localhost:9080/')).toBe('http://localhost:9080/graphql')
    expect(() => wsGraphqlUrl('ftp://x')).toThrow()
  })
})

describe('chuyển dữ liệu GraphQL → tin', () => {
  it('đọc tọa độ GeoJSON [kinh độ, vĩ độ], bỏ tọa độ hỏng', () => {
    expect(toaDoTuGeoJson(DIEM)).toEqual([108.2212, 15.9785])
    expect(toaDoTuGeoJson({ type: 'Point', coordinates: [181, 0] })).toBeNull()
    expect(toaDoTuGeoJson({ type: 'Point', coordinates: [108, '16'] })).toBeNull()
    expect(toaDoTuGeoJson({ type: 'LineString', coordinates: [[1, 2], [3, 4]] })).toBeNull()
    expect(toaDoTuGeoJson({ type: 'Point', coordinates: [Number.NaN, 1] })).toBeNull()
    expect(toaDoTuGeoJson(null)).toBeNull()
  })
  it('một hàng hợp lệ → tin, bỏ trường thừa', () => {
    expect(tinTuHang({ ...HANG, reporter_phone: '0900000001' })).toEqual({
      id: ID, location: [108.2212, 15.9785], urgency: 'khan_cap', status: 'tiep_nhan', created_at: HANG.created_at,
    })
  })
  it('hàng hỏng bị bỏ qua: thiếu id, urgency/status lạ, thời gian sai', () => {
    expect(tinTuHang({ ...HANG, id: 1 })).toBeNull()
    expect(tinTuHang({ ...HANG, urgency: 'rat_cao' })).toBeNull()
    expect(tinTuHang({ ...HANG, status: 'xoa' })).toBeNull()
    expect(tinTuHang({ ...HANG, created_at: 'hom qua' })).toBeNull()
    expect(tinTuHang({ ...HANG, location: null })).toBeNull()
    expect(tinTuHang('x')).toBeNull()
  })
  it('kết quả subscription: bỏ hàng hỏng và trùng id; dữ liệu lạ → rỗng', () => {
    const id2 = ID.replace(/1$/, '2')
    const ds = tinTuKetQua({ incidents: [HANG, { ...HANG, urgency: '?' }, HANG, { ...HANG, id: id2, status: 'dang_cuu' }] })
    expect(ds.map((t) => [t.id, t.status])).toEqual([[ID, 'tiep_nhan'], [id2, 'dang_cuu']])
    expect(tinTuKetQua(null)).toEqual([])
    expect(tinTuKetQua({ incidents: 'x' })).toEqual([])
  })
  it('chi tiết của dieu-phoi có liên hệ và đội; của tinh-nguyen không có khóa liên hệ', () => {
    const dp = chiTietTuKetQua({ incidents_by_pk: {
      ...HANG, updated_at: '2026-10-29T07:58:00Z', description: 'Nước ngập tới mái', address_text: null, people_count: 3,
      source: 'dien_thoai', reporter_phone: '0900000001', reporter_name: null, assigned_team: null,
    } })
    expect(dp).toMatchObject({ description: 'Nước ngập tới mái', people_count: 3, reporter_phone: '0900000001', team_name: null })
    const tn = chiTietTuKetQua({ incidents_by_pk: { ...HANG, description: 'x', people_count: 1, source: 'web' } })
    expect(tn).not.toBeNull()
    expect('reporter_phone' in tn!).toBe(false)
    expect('team_name' in tn!).toBe(false)
    expect(chiTietTuKetQua({ incidents_by_pk: null })).toBeNull()
  })
})

describe('kết nối lại', () => {
  it('phân loại lý do đóng: token hết hạn, bị từ chối, lỗi mạng', () => {
    expect(phanLoaiDong(4400, 'Could not verify JWT: JWTExpired')).toBe('het-han-token')
    expect(phanLoaiDong(4400, 'Could not verify JWT: JWSError JWSInvalidSignature')).toBe('tu-choi')
    expect(phanLoaiDong(4401, 'Unauthorized')).toBe('tu-choi')
    expect(phanLoaiDong(4403, '')).toBe('tu-choi')
    // Hasura v2.51 thật (smoke #60): JWT sai chữ ký hoặc xin vai ngoài allowed-roles
    expect(phanLoaiDong(4403, '{"server_error_msg":"4403: Forbidden"}')).toBe('tu-choi')
    expect(phanLoaiDong(1006, '')).toBe('mang')
    expect(phanLoaiDong(undefined, 'field \'incidents\' not found in type: \'subscription_root\'')).toBe('mang')
  })
  it('chờ tăng dần 0,5 s → 20 s, có nhiễu ≤ 30%', () => {
    expect([0, 1, 2, 3].map((n) => choKetNoiLai(n, 0))).toEqual([500, 1000, 2000, 4000])
    expect(choKetNoiLai(10, 0)).toBe(20_000)
    expect(choKetNoiLai(10, 1)).toBe(26_000)
    expect(choKetNoiLai(-1, 0)).toBe(500)
  })
})
