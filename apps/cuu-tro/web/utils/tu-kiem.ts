// SPDX-License-Identifier: Apache-2.0
// Trình duyệt TỰ kiểm chứng một phiếu kho / bút toán tiền trên sổ cái minh bạch (#63), không tin kết luận
// của máy chủ: chỉ dùng dữ liệu công khai (bản ghi chuẩn hóa, lá, inclusion proof, checkpoint đã ký) và khóa
// công khai của sổ cái (GET /ledger/verifier). Cùng thuật toán với máy chủ (cuu_tro_workflow/so_cai.py) và
// CLI core/ledger/cmd/ledger-verify:
//   1. JSON chuẩn tắc của bản ghi (khóa sắp xếp, không khoảng trắng, UTF-8, U+2028/U+2029 viết \u) → SHA-256,
//      phải bằng trường sha256 trong lá;
//   2. lá đúng loại và đúng mã;
//   3. leaf hash = SHA-256(0x00 ‖ lá) (RFC 6962);
//   4. inclusion proof dẫn từ leaf hash tới root của checkpoint (RFC 9162 mục 2.1.3.2);
//   5. chữ ký Ed25519 của checkpoint (signed note, C2SP) hợp lệ với khóa công khai, origin = tên khóa.
// Dùng WebCrypto (crypto.subtle): SHA-256 có ở mọi trình duyệt; Ed25519 có ở Chrome 137+, Firefox 129+,
// Safari 17+. Trình duyệt cũ không có Ed25519 thì bước 5 báo "không kiểm được", các bước khác vẫn chạy.

export type KetQuaBuoc = boolean | null

export interface BuocKiem {
  khoa: 'ban-ghi' | 'la' | 'leaf-hash' | 'inclusion' | 'chu-ky'
  ten: string
  ok: KetQuaBuoc
  chiTiet: string
}

export interface DuLieuKiem {
  loai: 'phieu_kho' | 'khoan_tien'
  ma: string
  ban_ghi_chuan_hoa: Record<string, string | null>
  bang_chung: {
    leaf_index: number
    leaf_hash: string
    tree_size: number
    inclusion_proof: string[]
    checkpoint: string
  } | null
  /** Lá nguyên văn trên sổ cái (chuỗi JSON) */
  la: string | null
}

/** Loại lá trên sổ cái theo loại mã (so_cai.LOAI_LA, LOAI_LA_TIEN) */
export const LOAI_LA: Record<DuLieuKiem['loai'], string> = {
  phieu_kho: 'cuu-tro.phieu-kho',
  khoan_tien: 'cuu-tro.khoan-tien',
}

const enc = new TextEncoder()

export function hex(b: Uint8Array): string {
  return Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('')
}

export function tuHex(s: string): Uint8Array {
  if (!/^(?:[0-9a-f]{2})*$/i.test(s)) throw new Error('chuỗi hex không hợp lệ')
  const b = new Uint8Array(s.length / 2)
  for (let i = 0; i < b.length; i++) b[i] = Number.parseInt(s.slice(2 * i, 2 * i + 2), 16)
  return b
}

export function tuBase64(s: string): Uint8Array {
  if (!/^[A-Za-z0-9+/]*={0,2}$/.test(s) || s.length % 4) throw new Error('chuỗi base64 không hợp lệ')
  const nhi = atob(s)
  return Uint8Array.from(nhi, (c) => c.charCodeAt(0))
}

function noi(...ds: Uint8Array[]): Uint8Array {
  const kq = new Uint8Array(ds.reduce((n, d) => n + d.length, 0))
  let i = 0
  for (const d of ds) { kq.set(d, i); i += d.length }
  return kq
}

export async function sha256(b: Uint8Array): Promise<Uint8Array> {
  return new Uint8Array(await crypto.subtle.digest('SHA-256', b as BufferSource))
}

/** JSON chuẩn tắc như so_cai.json_chuan_tac (Python) và leaf.CanonicalJSON (Go). */
export function jsonChuanTac(banGhi: Record<string, string | null>): string {
  const khoa = Object.keys(banGhi).sort()
  for (const k of khoa) {
    const v = banGhi[k]
    if (v !== null && typeof v !== 'string') throw new Error(`trường ${k}: bản ghi chuẩn hóa chỉ gồm chuỗi hoặc null`)
  }
  const s = `{${khoa.map((k) => `${JSON.stringify(k)}:${JSON.stringify(banGhi[k])}`).join(',')}}`
  return s.replaceAll('\u2028', '\\u2028').replaceAll('\u2029', '\\u2029')
}

export async function sha256BanGhi(banGhi: Record<string, string | null>): Promise<string> {
  return hex(await sha256(enc.encode(jsonChuanTac(banGhi))))
}

/** RFC 6962: SHA-256(0x00 ‖ lá) */
export async function leafHash(la: string): Promise<Uint8Array> {
  return sha256(noi(new Uint8Array([0]), enc.encode(la)))
}

export async function nodeHash(trai: Uint8Array, phai: Uint8Array): Promise<Uint8Array> {
  return sha256(noi(new Uint8Array([1]), trai, phai))
}

/** Root tính từ inclusion proof (RFC 9162 mục 2.1.3.2); null nếu proof sai độ dài/chỉ số. */
export async function rootTuProof(index: number, size: number, lh: Uint8Array, proof: Uint8Array[]): Promise<Uint8Array | null> {
  if (!Number.isInteger(index) || !Number.isInteger(size) || index < 0 || index >= size) return null
  // Dùng BigInt: chỉ số lá có thể vượt 2^31 (toán tử bit của JS chỉ 32 bit)
  let fn = BigInt(index)
  let sn = BigInt(size - 1)
  let r = lh
  for (const p of proof) {
    if (sn === 0n) return null
    if ((fn & 1n) === 1n || fn === sn) {
      r = await nodeHash(p, r)
      if ((fn & 1n) === 0n) {
        while ((fn & 1n) === 0n && fn !== 0n) { fn >>= 1n; sn >>= 1n }
      }
    } else {
      r = await nodeHash(r, p)
    }
    fn >>= 1n
    sn >>= 1n
  }
  return sn === 0n ? r : null
}

export interface Checkpoint {
  origin: string
  size: number
  root: Uint8Array
  /** Phần thân đã ký (kể cả dòng trống cuối) */
  than: string
  chuKy: Array<{ ten: string; sig: Uint8Array }>
}

/** Đọc checkpoint dạng signed note: "<origin>\n<size>\n<root b64>\n[mở rộng]\n\n— <tên> <b64(hash4 ‖ chữ ký)>\n" */
export function docCheckpoint(vanBan: string): Checkpoint {
  const i = vanBan.indexOf('\n\n')
  if (i < 0) throw new Error('checkpoint thiếu phần chữ ký')
  const than = `${vanBan.slice(0, i)}\n`
  const dong = than.split('\n')
  if (dong.length < 4) throw new Error('checkpoint thiếu dòng')
  const [origin, size, rootB64] = dong as [string, string, string]
  if (!/^[0-9]+$/.test(size)) throw new Error('kích thước cây không hợp lệ')
  const chuKy: Checkpoint['chuKy'] = []
  for (const d of vanBan.slice(i + 2).split('\n')) {
    if (!d.startsWith('— ')) continue
    const p = d.slice(2).split(' ')
    if (p.length !== 2) continue
    try { chuKy.push({ ten: p[0]!, sig: tuBase64(p[1]!) }) } catch { /* bỏ dòng chữ ký hỏng */ }
  }
  return { origin, size: Number(size), root: tuBase64(rootB64), than, chuKy }
}

export interface KhoaSoCai {
  ten: string
  hash4: Uint8Array
  /** Khóa Ed25519 32 byte */
  raw: Uint8Array
}

/** Khóa công khai dạng note: <tên>+<8 hex>+<base64(0x01 ‖ khóa 32 byte)>; kiểm hash4. */
export async function docKhoa(vkey: string): Promise<KhoaSoCai> {
  // Tách ở 2 dấu + đầu tiên: base64 của khóa có thể chứa + (như split("+", 2) bên Python)
  const v = vkey.trim()
  const i = v.indexOf('+')
  const j = i < 0 ? -1 : v.indexOf('+', i + 1)
  if (i <= 0 || j < 0) throw new Error('khóa công khai không đúng dạng note')
  const [ten, h, b64] = [v.slice(0, i), v.slice(i + 1, j), v.slice(j + 1)]
  const hash4 = tuHex(h)
  const raw = tuBase64(b64)
  if (hash4.length !== 4 || raw.length !== 33 || raw[0] !== 1) throw new Error('khóa công khai không phải Ed25519 dạng note')
  const tinh = (await sha256(noi(enc.encode(`${ten}\n`), raw))).slice(0, 4)
  if (hex(tinh) !== hex(hash4)) throw new Error('hash của khóa công khai không khớp')
  return { ten, hash4, raw: raw.slice(1) }
}

/** true/false: chữ ký hợp lệ hay không; null: trình duyệt không hỗ trợ Ed25519. */
export async function kiemChuKy(cp: Checkpoint, khoa: KhoaSoCai): Promise<KetQuaBuoc> {
  let k: CryptoKey
  try {
    k = await crypto.subtle.importKey('raw', khoa.raw as BufferSource, { name: 'Ed25519' }, false, ['verify'])
  } catch {
    return null
  }
  for (const c of cp.chuKy) {
    if (c.ten !== khoa.ten || c.sig.length !== 68 || hex(c.sig.slice(0, 4)) !== hex(khoa.hash4)) continue
    if (await crypto.subtle.verify({ name: 'Ed25519' }, k, c.sig.slice(4) as BufferSource, enc.encode(cp.than) as BufferSource)) return true
  }
  return false
}

const loiThanh = (e: unknown) => (e instanceof Error ? e.message : String(e))

/**
 * Chạy đủ 5 bước. `vkey`: khóa công khai của sổ cái (null nếu không tải được → bước chữ ký "không kiểm được").
 * Bản ghi chưa lên sổ cái (không có bằng chứng): chỉ có bước băm, các bước sau null.
 */
export async function tuKiem(d: DuLieuKiem, vkey: string | null): Promise<BuocKiem[]> {
  const buoc: BuocKiem[] = []
  let shaTinh = ''
  try { shaTinh = await sha256BanGhi(d.ban_ghi_chuan_hoa) } catch { shaTinh = '' }
  let la: Record<string, unknown> | null = null
  try { la = d.la ? (JSON.parse(d.la) as Record<string, unknown>) : null } catch { la = null }

  if (!d.bang_chung || !d.la) {
    buoc.push({ khoa: 'ban-ghi', ten: 'Băm lại bản ghi', ok: null, chiTiet: shaTinh ? `SHA-256 ${shaTinh}; chưa có lá trên sổ cái để so` : 'Không băm được bản ghi' })
    for (const [khoa, ten] of [['la', 'Lá đúng mã'], ['leaf-hash', 'Leaf hash'], ['inclusion', 'Inclusion proof'], ['chu-ky', 'Chữ ký checkpoint']] as const) {
      buoc.push({ khoa, ten, ok: null, chiTiet: 'Chưa ghi lên sổ cái' })
    }
    return buoc
  }
  const bc = d.bang_chung

  // 1. Bản ghi → SHA-256 = trường sha256 trong lá
  const shaLa = typeof la?.sha256 === 'string' ? la.sha256 : ''
  buoc.push({
    khoa: 'ban-ghi', ten: 'Băm lại bản ghi',
    ok: !!shaTinh && shaTinh === shaLa,
    chiTiet: shaTinh === shaLa ? `SHA-256 ${shaTinh} khớp lá` : `Trình duyệt tính ${shaTinh || '(lỗi)'}, lá ghi ${shaLa || '(không có)'}`,
  })
  // 2. Lá đúng loại, đúng mã
  const dungLa = la?.type === LOAI_LA[d.loai] && la?.ref === d.ma
  buoc.push({ khoa: 'la', ten: 'Lá đúng mã', ok: dungLa, chiTiet: dungLa ? `${LOAI_LA[d.loai]} · ${d.ma}` : `Lá là ${String(la?.type)} · ${String(la?.ref)}` })
  // 3. Leaf hash
  const lh = await leafHash(d.la)
  buoc.push({
    khoa: 'leaf-hash', ten: 'Leaf hash', ok: hex(lh) === bc.leaf_hash.toLowerCase(),
    chiTiet: hex(lh) === bc.leaf_hash.toLowerCase() ? hex(lh) : `Trình duyệt tính ${hex(lh)}, bằng chứng ghi ${bc.leaf_hash}`,
  })
  // 4 + 5. Checkpoint: inclusion proof và chữ ký
  let cp: Checkpoint | null = null
  try { cp = docCheckpoint(bc.checkpoint) } catch (e) {
    buoc.push({ khoa: 'inclusion', ten: 'Inclusion proof', ok: false, chiTiet: `Checkpoint sai định dạng: ${loiThanh(e)}` })
    buoc.push({ khoa: 'chu-ky', ten: 'Chữ ký checkpoint', ok: false, chiTiet: 'Checkpoint sai định dạng' })
    return buoc
  }
  let root: Uint8Array | null = null
  try {
    root = cp.size === bc.tree_size ? await rootTuProof(bc.leaf_index, cp.size, lh, bc.inclusion_proof.map(tuHex)) : null
  } catch { root = null }
  const khopRoot = !!root && hex(root) === hex(cp.root)
  buoc.push({
    khoa: 'inclusion', ten: 'Inclusion proof', ok: khopRoot,
    chiTiet: khopRoot
      ? `Lá số ${bc.leaf_index} nằm trong cây ${cp.size} lá (${bc.inclusion_proof.length} hash), root ${hex(cp.root)}`
      : `Proof không dẫn tới root của checkpoint (${hex(cp.root)})`,
  })
  if (!vkey) {
    buoc.push({ khoa: 'chu-ky', ten: 'Chữ ký checkpoint', ok: null, chiTiet: 'Không tải được khóa công khai của sổ cái' })
    return buoc
  }
  try {
    const khoa = await docKhoa(vkey)
    const ck = cp.origin === khoa.ten ? await kiemChuKy(cp, khoa) : false
    buoc.push({
      khoa: 'chu-ky', ten: 'Chữ ký checkpoint', ok: ck,
      chiTiet: ck === null ? 'Trình duyệt này chưa hỗ trợ Ed25519: dùng ledger-verify để kiểm chữ ký'
        : ck ? `Ed25519 hợp lệ, ký bởi ${khoa.ten}` : `Chữ ký không hợp lệ với khóa ${khoa.ten}`,
    })
  } catch (e) {
    buoc.push({ khoa: 'chu-ky', ten: 'Chữ ký checkpoint', ok: false, chiTiet: loiThanh(e) })
  }
  return buoc
}

/** Tổng kết: mọi bước đạt → hợp lệ; có bước sai → không hợp lệ; còn lại → chưa đủ để kết luận. */
export function ketLuan(buoc: BuocKiem[]): 'hop_le' | 'khong_hop_le' | 'chua_du' {
  if (buoc.some((b) => b.ok === false)) return 'khong_hop_le'
  return buoc.length > 0 && buoc.every((b) => b.ok === true) ? 'hop_le' : 'chua_du'
}
