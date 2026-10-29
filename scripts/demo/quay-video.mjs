// SPDX-License-Identifier: Apache-2.0
// Quay video demo dự phòng (#130) bằng Playwright (Apache-2.0) trên stack THẬT, đi đúng 7 luồng của
// docs/trinh-bay/kich-ban-demo.md. Mọi dữ liệu trên màn hình là dữ liệu giả.
// Cần: make up && bash scripts/demo/luong.sh chuan-bi (Grafana, đội giả, tin nền, trận lũ mẫu), ffmpeg.
// Mỗi luồng mở bằng một thẻ tiêu đề; phần chạy bằng API (bước 2, 4, 5, 6) gọi scripts/demo/luong.sh và in đúng
// kết quả thật lên thẻ. Ba đoạn (điều phối → đội cứu hộ → điều phối) quay riêng rồi ghép bằng ffmpeg thành MP4.
// Video là sản phẩm, KHÔNG commit: mặc định ghi vào .data/demo/video/ (ngoài git), đổi bằng VIDEO_DIR.
// Dùng (từ gốc repo): cd scripts/demo && npm ci && npx playwright install chromium && node quay-video.mjs
import { exec as execCb, execFileSync } from 'node:child_process'
import { createHmac } from 'node:crypto'
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { promisify } from 'node:util'
import { chromium } from 'playwright'

const exec = promisify(execCb)
const GOC = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const env = docEnv(join(GOC, '.env'))
const GW = process.env.GATEWAY_PUBLIC_URL ?? env.GATEWAY_PUBLIC_URL ?? `http://localhost:${env.APISIX_PORT ?? 9080}`
const MAT_KHAU = process.env.KC_DEMO_USER_PASSWORD ?? env.KC_DEMO_USER_PASSWORD
const RA = resolve(process.env.VIDEO_DIR ?? join(GOC, '.data/demo/video'))
const TEP_TOTP = join(GOC, '.data/demo/totp-dieuphoi01.txt')
const KHUNG = { width: 1280, height: 720 }
const TAM = mkdtempSync(join(tmpdir(), 'quay-video-'))
// Tin nhắn tự do cho bước 1 (giả định, SĐT giả mỗi lần một số)
const TIN_NHAN = `Cuu voi!! nha toi o thon 2 xa An Lac nuoc len toi mai roi, co 3 nguoi trong do 1 ba cu 80 tuoi. Toa do 15.8461, 108.1158. SDT 090013${String(Math.floor(Math.random() * 1e4)).padStart(4, '0')}`

if (!MAT_KHAU) throw new Error('Thiếu KC_DEMO_USER_PASSWORD (.env)')

function docEnv(p) {
  if (!existsSync(p)) return {}
  return Object.fromEntries(readFileSync(p, 'utf8').split('\n')
    .filter((l) => /^[A-Z0-9_]+=/.test(l)).map((l) => [l.slice(0, l.indexOf('=')), l.slice(l.indexOf('=') + 1)]))
}
const cho = (ms) => new Promise((r) => setTimeout(r, ms))
const bo = (s) => s.replace(/\x1b\[[0-9;]*m/g, '')
const thoat = (s) => s.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[c])

/** Chạy một bước của luong.sh, trả các dòng kết quả (bỏ màu, bỏ log docker) */
async function luong(buoc) {
  const { stdout } = await exec(`bash scripts/demo/luong.sh ${buoc}`, { cwd: GOC, timeout: 180000, maxBuffer: 1 << 22 })
  return bo(stdout).split('\n').filter((l) => l.trim() && !/Container|^\{"topic"/.test(l))
}

/** TOTP RFC 6238 (SHA-1, 6 số, 30 giây) từ bí mật base32 Keycloak hiện cho người nhập tay */
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

/** Thẻ tiêu đề / kết quả, màu nhận diện Team 1 (navy #12355B, cam #F07B1D, xanh nước #1FA2C9) */
async function the(page, { so, tieuDe, dong = [], ghiChu = '', ms = 4500 }) {
  const ds = dong.map((l) => `<li>${thoat(l)}</li>`).join('')
  await page.setContent(`<!doctype html><html lang="vi"><meta charset="utf-8"><style>
    body{margin:0;height:100vh;display:flex;flex-direction:column;justify-content:center;padding:0 80px;
      background:#12355B;color:#fff;font:22px/1.45 "Be Vietnam Pro",system-ui,sans-serif}
    .so{color:#F07B1D;font-weight:800;font-size:28px;letter-spacing:.04em}
    h1{font-size:46px;margin:.2em 0 .5em;line-height:1.15}
    ul{margin:0;padding:0;list-style:none;font:17px/1.6 ui-monospace,Menlo,monospace;color:#d9ecf5}
    li{white-space:pre-wrap}
    p{color:#1FA2C9;font-size:20px;margin-top:1.2em}
    .chan{position:absolute;bottom:28px;left:80px;font-size:15px;color:#9fb6cc}</style>
    <div class="so">${thoat(so ?? '')}</div><h1>${thoat(tieuDe)}</h1><ul>${ds}</ul><p>${thoat(ghiChu)}</p>
    <div class="chan">Disaster DX-OS · stack thật, dữ liệu giả · Apache-2.0</div></html>`)
  await cho(ms)
}

let maCuoi = ''
async function maMoi(bi) {
  while (totp(bi) === maCuoi) await cho(1000)
  maCuoi = totp(bi)
  return maCuoi
}

async function dangNhap(page, nguoi) {
  await page.goto(`${GW}/`)
  await page.waitForSelector('#username')
  await page.locator('#username').pressSequentially(nguoi, { delay: 40 })
  await page.fill('#password', MAT_KHAU)
  await cho(600)
  await page.click('#kc-login')
  await page.waitForLoadState('domcontentloaded')
  if (await page.locator('#mode-manual').count()) {
    // Lần đầu: vai điều phối bị bắt cài ứng dụng xác thực (MFA)
    await cho(2500)
    await page.click('#mode-manual')
    const bi = (await page.locator('#kc-totp-secret-key').innerText()).replace(/\s/g, '')
    mkdirSync(dirname(TEP_TOTP), { recursive: true })
    writeFileSync(TEP_TOTP, bi, { mode: 0o600 })
    await page.fill('#totp', await maMoi(bi))
    await page.fill('#userLabel', 'video-demo')
    await cho(1200)
    await page.click('#saveTOTPBtn')
  } else if (await page.locator('#otp').count()) {
    await page.fill('#otp', await maMoi(readFileSync(TEP_TOTP, 'utf8').trim()))
    await cho(800)
    await page.click('#kc-login')
  }
  await page.waitForURL(`${GW}/`, { timeout: 30000 })
  await page.locator('canvas.maplibregl-canvas').waitFor({ timeout: 30000 })
  await page.waitForLoadState('networkidle').catch(() => {})
  await cho(2500)
}

async function moBanDo(page) {
  await page.goto(`${GW}/`)
  await page.locator('canvas.maplibregl-canvas').waitFor({ timeout: 30000 })
  await page.waitForLoadState('networkidle').catch(() => {})
  await cho(2500)
}

const doan = [] // tệp WebM theo thứ tự
async function quayDoan(trinhDuyet, ten, tuyChon, chay) {
  const dir = join(TAM, ten)
  const ctx = await trinhDuyet.newContext({
    viewport: KHUNG, locale: 'vi-VN', timezoneId: 'Asia/Ho_Chi_Minh', colorScheme: 'light',
    recordVideo: { dir, size: KHUNG }, ...tuyChon,
  })
  const page = await ctx.newPage()
  let kq
  try {
    kq = await chay(page, ctx)
  } finally {
    await ctx.close() // ghi xong video khi đóng context
  }
  const tep = readdirSync(dir).filter((f) => f.endsWith('.webm')).map((f) => join(dir, f))
  doan.push(...tep)
  console.log(`đoạn ${ten}: ${tep.length} tệp`)
  return kq
}

const trinhDuyet = await chromium.launch()
let phien
try {
  // ---------- Đoạn A: điều phối viên (bước 1, 2, 3a) ----------
  phien = await quayDoan(trinhDuyet, 'a-dieu-phoi', {}, async (page, ctx) => {
    await the(page, {
      so: 'OLP PMNM 2026 · DTU_DZ_1', tieuDe: 'Disaster DX-OS: demo 7 luồng trên stack thật', ms: 6000,
      dong: ['1. Dán tin → AI bóc tách → điều phối duyệt', '2. Bản đồ thời gian thực', '3. Phân công tự động',
        '4. App hiện trường mất mạng vẫn gửi được', '5. Trạm đo vượt ngưỡng → cảnh báo', '6. Minh bạch: tự kiểm sổ cái',
        '7. Dashboard Grafana (SSO)'],
      ghiChu: 'Video dự phòng: mọi bước chạy thật qua API Gateway, dữ liệu là dữ liệu giả.',
    })
    await the(page, { so: 'Bước 1 · [I] + [P]', tieuDe: 'Dán tin nhắn tự do → AI bóc tách → người duyệt',
      ghiChu: 'Điều phối viên đăng nhập Keycloak, vai này bắt buộc OTP.' })
    await dangNhap(page, 'dieuphoi01')
    await page.goto(`${GW}/hang-cho`)
    await page.locator('#van-ban').waitFor({ timeout: 20000 })
    await cho(1200)
    await page.locator('#van-ban').pressSequentially(TIN_NHAN, { delay: 18 })
    await cho(800)
    await page.getByRole('button', { name: /Bóc tách bằng AI/ }).click()
    await page.getByRole('button', { name: /Duyệt và tạo tin/ }).waitFor({ timeout: 60000 })
    await cho(5000) // đề xuất cạnh văn bản gốc, Poka-yoke
    await page.getByRole('button', { name: /Duyệt và tạo tin/ }).click()
    await cho(4500) // vết duyệt

    await the(page, { so: 'Bước 2 · [D]', tieuDe: 'Bản đồ thời gian thực',
      ghiChu: 'Một tin mới gửi từ API: bản đồ nhận qua GraphQL subscription, không tải lại trang.' })
    await moBanDo(page)
    const p2 = luong(2)
    await cho(7000)
    const kq2 = await p2
    await page.locator('ul.divide-y li button').first().click().catch(() => {})
    await cho(4500)
    await the(page, { so: 'Bước 2 · kết quả API', tieuDe: 'Poka-yoke chặn tin trùng', dong: kq2.filter((l) => !l.includes('🗣')), ms: 5000 })

    await the(page, { so: 'Bước 3 · [P]', tieuDe: 'Phân công tự động',
      ghiChu: 'Workflow Temporal tìm đội sẵn sàng gần nhất bằng PostGIS, chờ đội nhận có hạn.' })
    await page.goto(`${GW}/phan-cong`)
    await page.locator('a[href^="/phan-cong/"]').first().waitFor({ timeout: 20000 })
    await cho(4500)
    const daGiao = page.locator('a[href^="/phan-cong/"]').filter({ hasText: /Đội / })
    await ((await daGiao.count()) ? daGiao.first() : page.locator('a[href^="/phan-cong/"]').first()).click()
    await cho(5000)
    return ctx.storageState()
  })

  // ---------- Đoạn B: đội cứu hộ nhận việc trên điện thoại (bước 3b) ----------
  await quayDoan(trinhDuyet, 'b-cuu-ho', { viewport: { width: 1280, height: 720 } }, async (page) => {
    await the(page, { so: 'Bước 3 · đội cứu hộ', tieuDe: 'Đội ca nô nhận nhiệm vụ',
      ghiChu: 'Tài khoản cuuho01 chỉ thấy nhiệm vụ giao cho đội mình (Hasura lọc theo vai trong JWT).' })
    await dangNhap(page, 'cuuho01').catch(async () => { await page.goto(`${GW}/phan-cong`) })
    await page.goto(`${GW}/phan-cong`)
    await cho(3500)
    const nv = page.locator('a[href^="/phan-cong/"]').first()
    if (await nv.count()) {
      await nv.click()
      await cho(3000)
      const nhan = page.getByRole('button', { name: /^Nhận nhiệm vụ$/ })
      if (await nhan.count()) { await nhan.click(); await cho(4500) }
    } else {
      await cho(3000)
    }
  })

  // ---------- Đoạn C: điều phối viên (bước 4 → 7), dùng lại phiên đăng nhập của đoạn A ----------
  await quayDoan(trinhDuyet, 'c-dieu-phoi', { storageState: phien }, async (page) => {
    await the(page, { so: 'Bước 4 · [H]', tieuDe: 'App hiện trường: mất mạng vẫn gửi được',
      ghiChu: 'App React Native xếp mọi thao tác vào hàng đợi mã hóa; có mạng thì gửi lại kèm Idempotency-Key. Ở đây gửi lại 2 lần đúng như app.' })
    const kq4 = await luong(4)
    await the(page, { so: 'Bước 4 · kết quả API', tieuDe: 'Gửi lại 2 lần → đúng 1 tin', dong: kq4.filter((l) => !l.includes('🗣')), ms: 7000 })
    await moBanDo(page)
    await cho(2500)

    await the(page, { so: 'Bước 5 · [D] + [I]', tieuDe: 'Trạm đo vượt ngưỡng → cảnh báo',
      ghiChu: 'Bộ giả lập gửi bản tin MQTT vượt ngưỡng → NATS → workflow cảnh báo → Centrifugo tới web.' })
    await moBanDo(page)
    const kq5 = await luong(5)
    await cho(2500)
    await page.getByRole('button', { name: /Thông báo/ }).first().click()
    await cho(6000)
    await page.keyboard.press('Escape')
    await the(page, { so: 'Bước 5 · hộp thư cảnh báo', tieuDe: 'Mỗi bước của đợt báo đúng một lần', dong: kq5.filter((l) => !l.includes('🗣')), ms: 6000 })

    await the(page, { so: 'Bước 6 · [D]', tieuDe: 'Minh bạch: phiếu xuất kho lên sổ cái',
      ghiChu: 'Trang công khai, không cần đăng nhập; trình duyệt tự kiểm bằng WebCrypto.' })
    const kq6 = await luong(6)
    const ma = (kq6.join('\n').match(/minh-bach\/([0-9a-f-]{36})/) ?? [])[1]
    if (ma) {
      await page.goto(`${GW}/minh-bach/${ma}`)
      await page.getByTestId('ket-qua').waitFor({ timeout: 20000 }).catch(() => {})
      await cho(5000)
      await page.mouse.wheel(0, 600)
      await cho(4000)
    }
    await the(page, { so: 'Bước 6 · ledger-verify', tieuDe: 'Người ngoài tự kiểm bằng CLI', dong: kq6.filter((l) => /Checkpoint|Lá #|KẾT QUẢ|phiếu/.test(l)), ms: 7000 })

    await the(page, { so: 'Bước 7 · [D]', tieuDe: 'Dashboard điều hành Grafana',
      ghiChu: 'Đăng nhập SSO Keycloak: điều phối là Editor, cứu hộ là Viewer. Dữ liệu đọc bằng role chỉ đọc.' })
    await page.goto(`${GW}/grafana/`) // SSO: Keycloak nhận phiên sẵn có, quay về Grafana
    await page.waitForURL(/\/grafana\/(\?|d\/|$)/, { timeout: 60000 }).catch(() => {})
    await page.goto(`${GW}/grafana/d/cuu-tro-dieu-hanh/?orgId=1&theme=light`)
    await page.waitForLoadState('networkidle').catch(() => {})
    await cho(2500)
    // Hộp giới thiệu tính năng mới của Grafana (nếu có) che dashboard: đóng
    for (const nut of [page.getByRole('button', { name: /^(Close|Đóng|Dismiss|Got it)$/i }), page.getByLabel(/^(Close|Đóng)$/i)]) {
      if (await nut.count()) await nut.first().click().catch(() => {})
    }
    await page.keyboard.press('Escape')
    await cho(7000)
    await page.mouse.wheel(0, 500)
    await cho(4000)

    await the(page, { so: 'Disaster DX-OS', tieuDe: 'Lõi mở dùng lại được + ứng dụng cứu trợ', ms: 6000,
      dong: ['Tầng 1: Keycloak · APISIX · PostgreSQL/PostGIS + Hasura · SeaweedFS · Temporal', 'Tầng 2: web Nuxt, app React Native, AI có người duyệt, sổ cái Tessera',
        'github.com/disaster-dxos/disaster-dxos · Apache-2.0'] })
  })

  // ---------- Ghép MP4 ----------
  mkdirSync(RA, { recursive: true })
  const ds = join(TAM, 'doan.txt')
  writeFileSync(ds, doan.map((f) => `file '${f}'`).join('\n') + '\n')
  const mp4 = join(RA, 'disaster-dxos-demo.mp4')
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', ds,
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '23', '-pix_fmt', 'yuv420p', '-r', '25', '-movflags', '+faststart', mp4])
  const giay = Number(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', mp4]).toString().trim())
  console.log(`video ${mp4} · ${Math.floor(giay / 60)} phút ${Math.round(giay % 60)} giây · ${(statSync(mp4).size / 1024 / 1024).toFixed(1)} MB`)
} finally {
  await trinhDuyet.close()
  rmSync(TAM, { recursive: true, force: true })
}
