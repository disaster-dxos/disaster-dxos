// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest'
import {
  docCheckpoint, docKhoa, hex, jsonChuanTac, ketLuan, leafHash, nodeHash, rootTuProof, sha256, sha256BanGhi, tuKiem,
  type DuLieuKiem,
} from '~/utils/tu-kiem'

const enc = new TextEncoder()
const b64 = (b: Uint8Array) => btoa(String.fromCharCode(...b))

// ---------- Cây Merkle tham chiếu (RFC 6962 mục 2.1) để sinh proof cho test ----------
const k = (n: number) => { let x = 1; while (x * 2 < n) x *= 2; return x }   // lũy thừa 2 lớn nhất < n
async function mth(la: Uint8Array[]): Promise<Uint8Array> {
  if (la.length === 1) return la[0]!
  const m = k(la.length)
  return nodeHash(await mth(la.slice(0, m)), await mth(la.slice(m)))
}
async function path(i: number, la: Uint8Array[]): Promise<Uint8Array[]> {
  if (la.length === 1) return []
  const m = k(la.length)
  return i < m ? [...await path(i, la.slice(0, m)), await mth(la.slice(m))] : [...await path(i - m, la.slice(m)), await mth(la.slice(0, m))]
}

// ---------- Sổ cái giả lập: khóa Ed25519, checkpoint signed note ----------
async function taoKhoa(ten: string) {
  const kp = (await crypto.subtle.generateKey({ name: 'Ed25519' }, true, ['sign', 'verify'])) as CryptoKeyPair
  const pub = new Uint8Array(await crypto.subtle.exportKey('raw', kp.publicKey))
  const raw = new Uint8Array([1, ...pub])
  const hash4 = (await sha256(new Uint8Array([...enc.encode(`${ten}\n`), ...raw]))).slice(0, 4)
  return { ten, hash4, vkey: `${ten}+${hex(hash4)}+${b64(raw)}`, priv: kp.privateKey }
}
async function kyCheckpoint(khoa: Awaited<ReturnType<typeof taoKhoa>>, origin: string, size: number, root: Uint8Array) {
  const than = `${origin}\n${size}\n${b64(root)}\n`
  const sig = new Uint8Array(await crypto.subtle.sign({ name: 'Ed25519' }, khoa.priv, enc.encode(than)))
  return `${than}\n— ${khoa.ten} ${b64(new Uint8Array([...khoa.hash4, ...sig]))}\n`
}

const MA = 'e0000000-0000-4000-8000-000000000003'
const BAN_GHI = {
  loai: 'cuu-tro.khoan-tien/v1', id: MA, direction: 'thu', amount: '50000000', currency: 'VND', category: 'ung_ho',
  purpose: 'Ủng hộ đợt lũ (dữ liệu giả)', shelter_id: null, supply_movement_id: null, created_at: '2026-10-24T02:00:00.000Z',
}

/** Một sổ cái 6 lá, lá số 3 là bút toán MA; trả dữ liệu đúng như API /minh-bach/xac-minh */
async function soCaiMau(sua?: { banGhi?: Record<string, string | null>; la?: Record<string, unknown> }) {
  const khoa = await taoKhoa('dxos.local/ledger')
  const la = JSON.stringify({ type: 'cuu-tro.khoan-tien', ref: MA, sha256: await sha256BanGhi(BAN_GHI), attrs: { direction: 'thu' }, ...sua?.la })
  const cacLa = await Promise.all([0, 1, 2, 3, 4, 5].map((i) => leafHash(i === 3 ? la : `la-khac-${i}`)))
  const root = await mth(cacLa)
  const d: DuLieuKiem = {
    loai: 'khoan_tien', ma: MA, ban_ghi_chuan_hoa: sua?.banGhi ?? BAN_GHI, la,
    bang_chung: {
      leaf_index: 3, leaf_hash: hex(cacLa[3]!), tree_size: 6,
      inclusion_proof: (await path(3, cacLa)).map(hex), checkpoint: await kyCheckpoint(khoa, khoa.ten, 6, root),
    },
  }
  return { d, khoa }
}

describe('JSON chuẩn tắc + băm (khớp Go leaf.CanonicalJSON và Python so_cai.json_chuan_tac)', () => {
  it('vector chung với core/ledger/leaf/leaf_test.go', () => {
    expect(jsonChuanTac({ quantity: '1500.00', note: 'Tiếp nhận <từ> huyện & "đội"', id: 'e0000000-0000-4000-8000-000000000001', shelter_id: null }))
      .toBe('{"id":"e0000000-0000-4000-8000-000000000001","note":"Tiếp nhận <từ> huyện & \\"đội\\"","quantity":"1500.00","shelter_id":null}')
  })
  it('U+2028/U+2029 viết \\u như Go; chỉ nhận chuỗi hoặc null', () => {
    expect(jsonChuanTac({ a: 'x y ' })).toBe('{"a":"x\\u2028y\\u2029"}')
    expect(() => jsonChuanTac({ a: 1 } as never)).toThrow(/chuỗi hoặc null/)
  })
  it('leaf hash RFC 6962 của lá rỗng', async () => {
    expect(hex(await leafHash(''))).toBe('6e340b9cffb37a989ca544e6bb780a2c78901d3fb33738768511a30617afa01d')
  })
})

describe('inclusion proof (RFC 9162 mục 2.1.3.2)', () => {
  it('mọi chỉ số của cây 1–11 lá: proof dẫn tới đúng root', async () => {
    for (let n = 1; n <= 11; n++) {
      const la = await Promise.all(Array.from({ length: n }, (_, i) => leafHash(`la ${i}`)))
      const root = hex(await mth(la))
      for (let i = 0; i < n; i++) {
        const r = await rootTuProof(i, n, la[i]!, await path(i, la))
        expect(r && hex(r), `n=${n} i=${i}`).toBe(root)
      }
    }
  })
  it('proof sai, thiếu, thừa hoặc chỉ số ngoài cây → không ra root', async () => {
    const la = await Promise.all(Array.from({ length: 7 }, (_, i) => leafHash(`la ${i}`)))
    const root = hex(await mth(la))
    const p = await path(5, la)
    expect(hex((await rootTuProof(5, 7, la[4]!, p))!)).not.toBe(root)
    expect(await rootTuProof(5, 7, la[5]!, p.slice(1))).toBeNull()
    expect(await rootTuProof(5, 7, la[5]!, [...p, p[0]!])).toBeNull()
    expect(await rootTuProof(7, 7, la[5]!, p)).toBeNull()
    expect(await rootTuProof(-1, 7, la[5]!, p)).toBeNull()
  })
})

describe('checkpoint và khóa công khai (signed note C2SP)', () => {
  it('đọc checkpoint: origin, kích thước, root, chữ ký', async () => {
    const { d, khoa } = await soCaiMau()
    const cp = docCheckpoint(d.bang_chung!.checkpoint)
    expect(cp.origin).toBe('dxos.local/ledger')
    expect(cp.size).toBe(6)
    expect(cp.root).toHaveLength(32)
    expect(cp.chuKy).toHaveLength(1)
    expect(cp.chuKy[0]!.ten).toBe(khoa.ten)
    expect(() => docCheckpoint('dxos.local/ledger\n6\nAAAA\n')).toThrow(/chữ ký/)
  })
  it('khóa: kiểm hash4, từ chối khóa sai dạng', async () => {
    const { khoa } = await soCaiMau()
    expect((await docKhoa(khoa.vkey)).raw).toHaveLength(32)
    const [ten, h] = khoa.vkey.split('+')
    await expect(docKhoa(khoa.vkey.replace(`+${h}+`, '+00000000+'))).rejects.toThrow(/hash/)
    // base64 của khóa chứa dấu + vẫn đọc đúng (chỉ tách ở 2 dấu + đầu)
    expect((await docKhoa(`${ten}+${hex((await sha256(new Uint8Array([...enc.encode(`${ten}\n`), 1, ...new Uint8Array(32).fill(0xfb)]))).slice(0, 4))}+${b64(new Uint8Array([1, ...new Uint8Array(32).fill(0xfb)]))}`)).raw[0]).toBe(0xfb)
    await expect(docKhoa('khong-phai-khoa')).rejects.toThrow(/note/)
  })
})

describe('tự kiểm chứng đủ 5 bước', () => {
  it('bằng chứng đúng → 5/5 đạt, kết luận hợp lệ', async () => {
    const { d, khoa } = await soCaiMau()
    const b = await tuKiem(d, khoa.vkey)
    expect(b.map((x) => [x.khoa, x.ok])).toEqual([['ban-ghi', true], ['la', true], ['leaf-hash', true], ['inclusion', true], ['chu-ky', true]])
    expect(ketLuan(b)).toBe('hop_le')
  })
  it('bản ghi trong CSDL bị sửa sau khi ghi sổ (số tiền) → bước băm sai', async () => {
    const { d, khoa } = await soCaiMau({ banGhi: { ...BAN_GHI, amount: '5000000' } })
    const b = await tuKiem(d, khoa.vkey)
    expect(b[0]!.ok).toBe(false)
    expect(ketLuan(b)).toBe('khong_hop_le')
  })
  it('lá của mã khác → bước "lá đúng mã" sai', async () => {
    const { d, khoa } = await soCaiMau({ la: { ref: 'e0000000-0000-4000-8000-000000000009' } })
    expect((await tuKiem(d, khoa.vkey))[1]!.ok).toBe(false)
  })
  it('leaf hash trong bằng chứng bị sửa → bước leaf hash sai', async () => {
    const { d, khoa } = await soCaiMau()
    d.bang_chung!.leaf_hash = '00'.repeat(32)
    expect((await tuKiem(d, khoa.vkey))[2]!.ok).toBe(false)
  })
  it('proof bị sửa một hash → inclusion sai', async () => {
    const { d, khoa } = await soCaiMau()
    d.bang_chung!.inclusion_proof[1] = 'ff'.repeat(32)
    expect((await tuKiem(d, khoa.vkey))[3]!.ok).toBe(false)
  })
  it('checkpoint ký bằng khóa khác (sổ cái giả) → chữ ký sai', async () => {
    const { d } = await soCaiMau()
    const khac = await taoKhoa('dxos.local/ledger')
    const b = await tuKiem(d, khac.vkey)
    expect(b[4]!.ok).toBe(false)
    expect(ketLuan(b)).toBe('khong_hop_le')
  })
  it('kích thước cây trong bằng chứng khác checkpoint → inclusion sai', async () => {
    const { d, khoa } = await soCaiMau()
    d.bang_chung!.tree_size = 7
    expect((await tuKiem(d, khoa.vkey))[3]!.ok).toBe(false)
  })
  it('không tải được khóa công khai → bước chữ ký "không kiểm được", chưa đủ kết luận', async () => {
    const { d } = await soCaiMau()
    const b = await tuKiem(d, null)
    expect(b[4]!.ok).toBeNull()
    expect(ketLuan(b)).toBe('chua_du')
  })
  it('chưa ghi lên sổ cái → không bước nào đạt hay sai', async () => {
    const { d, khoa } = await soCaiMau()
    const b = await tuKiem({ ...d, bang_chung: null, la: null }, khoa.vkey)
    expect(b).toHaveLength(5)
    expect(b.every((x) => x.ok === null)).toBe(true)
    expect(b[0]!.chiTiet).toContain(await sha256BanGhi(BAN_GHI))
    expect(ketLuan(b)).toBe('chua_du')
  })
})
