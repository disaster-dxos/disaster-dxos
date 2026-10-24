// SPDX-License-Identifier: Apache-2.0
// Chụp ảnh và GIF demo web điều phối cho README (#65) bằng Playwright (Apache-2.0), trên stack THẬT đã chạy
// `make up && make seed && bash scripts/chup-anh/du-lieu-demo.sh`. Mọi dữ liệu trên màn hình là dữ liệu giả.
// Kịch bản: đăng nhập (Keycloak, điều phối có MFA TOTP) → bản đồ tin kêu cứu + trạm đo → popup trạm →
// chi tiết tin → màn phân công → trang Minh bạch công khai tự kiểm sổ cái. Chế độ sáng và tối.
// Kết quả: docs/images/web-demo-*.gif, web-*.webp (ảnh tĩnh). GIF ghép bằng ffmpeg (bảng màu riêng).
// Dùng (từ gốc repo): cd scripts/chup-anh && npm ci && npx playwright install chromium && node chup.mjs
import { execFileSync } from 'node:child_process'
import { createHmac } from 'node:crypto'
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'

const GOC = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const env = docEnv(join(GOC, '.env'))
const GW = process.env.GATEWAY_PUBLIC_URL ?? env.GATEWAY_PUBLIC_URL ?? `http://localhost:${env.APISIX_PORT ?? 9080}`
const MAT_KHAU = process.env.KC_DEMO_USER_PASSWORD ?? env.KC_DEMO_USER_PASSWORD
const NGUOI_DUNG = process.env.NGUOI_DUNG ?? 'dieuphoi01'
const RA = join(GOC, 'docs/images')
// Bí mật TOTP của tài khoản mẫu trên stack đang chạy (tạo ở lần đăng nhập đầu), giữ ngoài git
const TEP_TOTP = join(GOC, '.data/chup-anh-totp.txt')
const KHUNG = { width: 1440, height: 900 }
const KHUNG_GIF = { width: 1280, height: 800 }
// Tâm và mức zoom mặc định của bản đồ (apps/cuu-tro/web/utils/ban-do.ts)
const TAM = [108.2, 15.92]
const ZOOM = 10.5
const TRAM_POPUP = [108.333, 15.877] // QN-HA-01 Hội An (seed)

if (!MAT_KHAU) throw new Error('Thiếu KC_DEMO_USER_PASSWORD (.env)')

function docEnv(p) {
  if (!existsSync(p)) return {}
  return Object.fromEntries(readFileSync(p, 'utf8').split('\n')
    .filter((l) => /^[A-Z0-9_]+=/.test(l)).map((l) => [l.slice(0, l.indexOf('=')), l.slice(l.indexOf('=') + 1)]))
}

let maCuoi = ''
/** Mã TOTP chưa dùng: Keycloak không nhận lại mã vừa dùng trong cùng 30 giây → chờ sang khung kế tiếp */
async function maMoi(bi) {
  while (totp(bi) === maCuoi) await cho(1000)
  maCuoi = totp(bi)
  return maCuoi
}

/** TOTP RFC 6238 (SHA-1, 6 số, 30 giây) từ bí mật base32 */
function totp(base32, now = Date.now()) {
  const bang = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
  let bit = ''
  for (const c of base32.replace(/[\s=]/g, '').toUpperCase()) bit += bang.indexOf(c).toString(2).padStart(5, '0')
  const khoa = Buffer.from(bit.match(/.{8}/g).map((b) => parseInt(b, 2)))
  const dem = Buffer.alloc(8)
  dem.writeBigUInt64BE(BigInt(Math.floor(now / 30000)))
  const h = createHmac('sha1', khoa).update(dem).digest()
  const o = h[h.length - 1] & 0xf
  return String((h.readUInt32BE(o) & 0x7fffffff) % 1_000_000).padStart(6, '0')
}

/** Tọa độ pixel (trong khung bản đồ) của một điểm khi bản đồ đang ở tâm/zoom mặc định (Web Mercator, ô 512) */
function diemTrenBanDo(hop, [lon, lat]) {
  const tile = 512 * 2 ** ZOOM
  const x = (l) => ((l + 180) / 360) * tile
  const y = (p) => (1 - Math.log(Math.tan(Math.PI / 4 + (p * Math.PI) / 360)) / Math.PI) / 2 * tile
  return { x: hop.x + hop.width / 2 + x(lon) - x(TAM[0]), y: hop.y + hop.height / 2 + y(lat) - y(TAM[1]) }
}

const cho = (ms) => new Promise((r) => setTimeout(r, ms))

async function dangNhap(page, khungHinh) {
  await page.goto(`${GW}/`)
  await page.waitForSelector('#username')
  await page.fill('#username', NGUOI_DUNG)
  await page.fill('#password', MAT_KHAU)
  await khungHinh?.('dang-nhap', 1500)
  await page.click('#kc-login')
  await page.waitForLoadState('domcontentloaded')
  // Lần đầu: Keycloak bắt cài ứng dụng xác thực (vai điều phối bắt buộc MFA) → đọc bí mật, nhập mã
  if (await page.locator('#mode-manual').count()) {
    await page.click('#mode-manual')
    const bi = (await page.locator('#kc-totp-secret-key').innerText()).replace(/\s/g, '')
    mkdirSync(dirname(TEP_TOTP), { recursive: true })
    writeFileSync(TEP_TOTP, bi, { mode: 0o600 })
    await page.fill('#totp', await maMoi(bi))
    await page.fill('#userLabel', 'chup-anh-readme')
    await page.click('#saveTOTPBtn')
  } else if (await page.locator('#otp').count()) {
    if (!existsSync(TEP_TOTP)) throw new Error(`Tài khoản đã có TOTP nhưng thiếu ${TEP_TOTP} (dựng lại stack)`)
    await page.fill('#otp', await maMoi(readFileSync(TEP_TOTP, 'utf8').trim()))
    await page.click('#kc-login')
  }
  await page.waitForURL(`${GW}/`, { timeout: 30000 })
  await page.getByText('Trực tiếp').first().waitFor({ timeout: 30000 })
  await page.locator('canvas.maplibregl-canvas').waitFor()
  await page.waitForLoadState('networkidle').catch(() => {})
  await cho(3500) // ô bản đồ nền, biểu tượng trạm
}

async function moPopupTram(page) {
  const hop = await page.locator('canvas.maplibregl-canvas').boundingBox()
  const p = diemTrenBanDo(hop, TRAM_POPUP)
  await page.mouse.click(p.x, p.y)
  await page.getByTestId('popup-tram').locator('svg').waitFor({ timeout: 10000 })
  await cho(600)
}

async function maPhieuMinhBach(page) {
  // Phiếu xuất kho đã niêm phong (hàng từ kho tới điểm nhận), không có thì phiếu bất kỳ
  const r = await page.request.get(`${GW}/workflow/minh-bach/so-cai?loai=phieu_kho&gioi_han=50`)
  const d = await r.json()
  const ds = Array.isArray(d.muc) ? d.muc : []
  const ma = (ds.find((x) => x.chieu === 'xuat') ?? ds[0])?.ma
  if (!ma) throw new Error(`Không lấy được mã phiếu từ sổ cái: ${JSON.stringify(d).slice(0, 300)}`)
  return ma
}

async function trangMinhBach(page, ma) {
  await page.goto(`${GW}/minh-bach/${ma}`)
  await page.getByTestId('ket-qua').waitFor({ timeout: 20000 })
  await page.getByText(/tự kiểm/i).first().waitFor()
  await cho(2500) // trình duyệt chạy 5 bước WebCrypto
}

/** Ảnh tĩnh 1440×900 → WebP */
async function chupTinh(page, ten) {
  const png = join(TAM_DIR, `${ten}.png`)
  await page.screenshot({ path: png })
  execFileSync('magick', [png, '-quality', '86', join(RA, `${ten}.webp`)])
  console.log(`ảnh ${ten}.webp ${(statSync(join(RA, `${ten}.webp`)).size / 1024).toFixed(0)} KB`)
}

const TAM_DIR = mkdtempSync(join(tmpdir(), 'chup-anh-'))
const trinhDuyet = await chromium.launch()
try {
  // ---------- GIF demo, chế độ sáng ----------
  const khung = []
  const ctxGif = await trinhDuyet.newContext({ viewport: KHUNG_GIF, colorScheme: 'light', locale: 'vi-VN', timezoneId: 'Asia/Ho_Chi_Minh' })
  const pg = await ctxGif.newPage()
  const khungHinh = async (ten, ms) => {
    const p = join(TAM_DIR, `gif-${String(khung.length).padStart(2, '0')}-${ten}.png`)
    await pg.screenshot({ path: p })
    khung.push({ p, ms })
  }
  await dangNhap(pg, khungHinh)
  await khungHinh('ban-do', 2000)
  await moPopupTram(pg)
  await khungHinh('popup-tram', 2000)
  await pg.keyboard.press('Escape')
  await pg.locator('ul.divide-y li button').first().click()
  await cho(2200)
  await khungHinh('chi-tiet-tin', 2000)
  await pg.goto(`${GW}/phan-cong`)
  await pg.locator('a[href^="/phan-cong/"]').first().waitFor({ timeout: 20000 })
  await cho(1500)
  await khungHinh('phan-cong', 1800)
  // Tin đã giao cho một đội (có đồng hồ hạn nhận), không có thì tin đầu tiên
  const daGiao = pg.locator('a[href^="/phan-cong/"]').filter({ hasText: /Đội / })
  await ((await daGiao.count()) ? daGiao.first() : pg.locator('a[href^="/phan-cong/"]').first()).click()
  await cho(2500)
  await khungHinh('phan-cong-chi-tiet', 1800)
  const ma = await maPhieuMinhBach(pg)
  await trangMinhBach(pg, ma)
  await khungHinh('minh-bach', 2400)
  await ctxGif.close()

  // Ghép GIF: concat theo thời lượng từng khung, thu về 960 px, bảng màu chung sinh từ chính các khung
  const ds = join(TAM_DIR, 'khung.txt')
  writeFileSync(ds, khung.map((k) => `file '${k.p}'\nduration ${k.ms / 1000}`).join('\n') + '\n')
  const gif = join(RA, 'web-demo-dieu-phoi.gif')
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', ds, '-vf',
    'fps=10,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=full[p];[b][p]paletteuse=dither=bayer:bayer_scale=4',
    gif])
  console.log(`GIF web-demo-dieu-phoi.gif ${(statSync(gif).size / 1024 / 1024).toFixed(2)} MB, ${khung.length} khung, ${khung.reduce((s, k) => s + k.ms, 0) / 1000} giây`)

  // ---------- Ảnh tĩnh sáng và tối ----------
  for (const che of ['light', 'dark']) {
    const hau = che === 'dark' ? '-toi' : ''
    const ctx = await trinhDuyet.newContext({ viewport: KHUNG, colorScheme: che, locale: 'vi-VN', timezoneId: 'Asia/Ho_Chi_Minh' })
    const page = await ctx.newPage()
    await dangNhap(page)
    await moPopupTram(page)
    await chupTinh(page, `web-ban-do-tram-do${hau}`)
    await page.goto(`${GW}/phan-cong`)
    await page.locator('a[href^="/phan-cong/"]').first().waitFor({ timeout: 20000 })
    await cho(1500)
    await chupTinh(page, `web-phan-cong${hau}`)
    await trangMinhBach(page, ma)
    await chupTinh(page, `web-minh-bach${hau}`)
    await ctx.close()
  }
} finally {
  await trinhDuyet.close()
  rmSync(TAM_DIR, { recursive: true, force: true })
}
