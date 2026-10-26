// SPDX-License-Identifier: Apache-2.0
// GraphQL qua gateway /graphql (Hasura). Vai gửi kèm header X-Hasura-Role: Hasura lọc theo hàng
// (tinh-nguyen chỉ thấy tin mình tạo, cuu-ho chỉ thấy tin của đội mình; apps/cuu-tro/README.md).
import type { DoiCuaToi, MucKhan, TinCuaToi, TrangThaiTin, VaiTro } from '@/types/api';
import { api, type KetQuaGoi } from './api';

export class LoiGraphql extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function hoiGraphql<T>(
  query: string,
  variables: Record<string, unknown>,
  vai: VaiTro,
  goi = api.goi,
): Promise<T> {
  const r: KetQuaGoi<{ data?: T; errors?: Array<{ message?: string }> }> = await goi({
    method: 'POST',
    url: '/graphql',
    data: { query, variables },
    headers: { 'Content-Type': 'application/json', 'X-Hasura-Role': vai },
  });
  if (!r.ok) {
    throw new LoiGraphql(r.status, `HTTP ${r.status}`);
  }
  if (r.data.errors?.length || !r.data.data) {
    throw new LoiGraphql(200, r.data.errors?.[0]?.message ?? 'GraphQL');
  }
  return r.data.data;
}

/** Cột mà cả tinh-nguyen và cuu-ho được đọc (metadata Hasura của incidents); không hỏi SĐT */
export const Q_TIN_CUA_TOI = `query TinCuaToi {
  incidents(order_by: {created_at: desc}, limit: 50, where: {status: {_nin: ["dong"]}}) {
    id status urgency description address_text people_count created_at location
  }
}`;

export const Q_DOI_CUA_TOI = `query DoiCuaToi { team_members { team { id name status location_updated_at } } }`;

/**
 * Chỉ ghi khi vị trí mới hơn vị trí đang có: bản ghi cũ trong hàng đợi gửi muộn không đè vị trí mới.
 * Không dùng `_is_null` trong điều kiện: WAF (OWASP CRS) ở gateway coi "is_null" là dấu hiệu SQL injection và
 * chặn 403. Đội chưa từng có vị trí (không ghi được 0 dòng) thì hỏi mốc rồi ghi lần đầu (M_VI_TRI_DOI_DAU).
 */
export const M_VI_TRI_DOI = `mutation ViTriDoi($id: uuid!, $p: geography!, $luc: timestamptz!) {
  update_rescue_teams(
    where: {id: {_eq: $id}, location_updated_at: {_lt: $luc}},
    _set: {location: $p, location_updated_at: $luc}
  ) { affected_rows }
}`;

export const Q_MOC_VI_TRI_DOI = `query MocViTriDoi($id: uuid!) { rescue_teams_by_pk(id: $id) { location_updated_at } }`;

export const M_VI_TRI_DOI_DAU = `mutation ViTriDoiDau($id: uuid!, $p: geography!, $luc: timestamptz!) {
  update_rescue_teams(where: {id: {_eq: $id}}, _set: {location: $p, location_updated_at: $luc}) { affected_rows }
}`;

const MUC: readonly string[] = ['khan_cap', 'cao', 'trung_binh', 'thap'];
const TRANG_THAI: readonly string[] = ['tiep_nhan', 'phan_cong', 'dang_cuu', 'da_cuu', 'dong'];

function toaDo(v: unknown): [number, number] | null {
  const c = (v as { coordinates?: unknown } | null)?.coordinates;
  return Array.isArray(c) && typeof c[0] === 'number' && typeof c[1] === 'number' ? [c[0], c[1]] : null;
}

/** Hàng GraphQL → TinCuaToi; hàng thiếu trường hoặc giá trị lạ bị bỏ */
export function tinTuHang(rows: unknown): TinCuaToi[] {
  if (!Array.isArray(rows)) {
    return [];
  }
  return rows.flatMap((h: Record<string, unknown>) => {
    if (typeof h?.id !== 'string' || !MUC.includes(String(h.urgency)) || !TRANG_THAI.includes(String(h.status))) {
      return [];
    }
    return [
      {
        id: h.id,
        status: h.status as TrangThaiTin,
        urgency: h.urgency as MucKhan,
        description: typeof h.description === 'string' ? h.description : '',
        address_text: typeof h.address_text === 'string' ? h.address_text : null,
        people_count: typeof h.people_count === 'number' ? h.people_count : 1,
        created_at: typeof h.created_at === 'string' ? h.created_at : '',
        toaDo: toaDo(h.location),
      },
    ];
  });
}

export async function layTinCuaToi(vai: VaiTro): Promise<TinCuaToi[]> {
  const d = await hoiGraphql<{ incidents: unknown }>(Q_TIN_CUA_TOI, {}, vai);
  return tinTuHang(d.incidents);
}

export async function layDoiCuaToi(): Promise<DoiCuaToi | null> {
  const d = await hoiGraphql<{ team_members: Array<{ team: DoiCuaToi | null }> }>(Q_DOI_CUA_TOI, {}, 'cuu-ho');
  return d.team_members[0]?.team ?? null;
}
