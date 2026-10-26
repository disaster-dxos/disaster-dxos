// SPDX-License-Identifier: Apache-2.0
// Kiểm giấy phép mọi gói npm đã cài (kể cả phụ thuộc bắc cầu, node_modules lồng nhau) của app hiện trường,
// không cần mạng. Đạt khi mỗi gói có giấy phép OSI tương thích Apache-2.0, hoặc nằm trong NGOAI_LE (có lý do).
// Biểu thức "A OR B": đạt nếu một vế đạt. Gặp GPL/AGPL/LGPL-only hay giấy phép lạ → thoát mã 1.
// Dùng: yarn install && yarn licenses (job CI mobile chạy lệnh này). Bảng tổng hợp: DEPENDENCIES.md mục App.
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

const OSI = new Set([
  'MIT', 'ISC', 'Apache-2.0', 'BSD-2-Clause', 'BSD-3-Clause', '0BSD', 'MPL-2.0', 'BlueOak-1.0.0', 'Python-2.0',
  'Unlicense',
])

// Không phải giấy phép OSI nhưng là dữ liệu/công cụ chỉ dùng lúc build hoặc test, không vào bản app, tương thích
// Apache-2.0. Thêm gói vào đây phải ghi lý do trong DEPENDENCIES.md.
const NGOAI_LE = {
  'caniuse-lite': 'CC-BY-4.0: dữ liệu trình duyệt cho browserslist (Babel) lúc build',
  'mdn-data': 'CC0-1.0 (hiến tặng công cộng): dữ liệu thuộc tính CSS cho css-tree, phụ thuộc của react-native-svg',
}

function dat(expr) {
  return expr.replace(/[()]/g, '').split(/\s+OR\s+/).some(x => OSI.has(x.trim()))
}

function giayPhep(pkg) {
  if (typeof pkg.license === 'string') return pkg.license
  if (pkg.license && typeof pkg.license.type === 'string') return pkg.license.type
  if (Array.isArray(pkg.licenses)) return pkg.licenses.map(l => l.type ?? l).join(' OR ')
  return 'KHÔNG RÕ'
}

const goi = new Map()
function duyet(thuMuc) {
  if (!existsSync(thuMuc)) return
  for (const ten of readdirSync(thuMuc)) {
    if (ten.startsWith('.')) continue
    if (ten.startsWith('@')) {
      for (const con of readdirSync(join(thuMuc, ten))) xem(join(thuMuc, ten, con), `${ten}/${con}`)
    } else {
      xem(join(thuMuc, ten), ten)
    }
  }
}
function xem(dir, ten) {
  const p = join(dir, 'package.json')
  if (!existsSync(p)) return
  const pkg = JSON.parse(readFileSync(p, 'utf8'))
  goi.set(`${ten}@${pkg.version}`, { ten, lic: giayPhep(pkg) })
  duyet(join(dir, 'node_modules'))
}

duyet(new URL('../node_modules', import.meta.url).pathname)
if (goi.size === 0) {
  console.error('Chưa có node_modules: chạy yarn install trước')
  process.exit(1)
}
const loi = []
const dem = new Map()
let ngoaiLe = 0
for (const [id, { ten, lic }] of goi) {
  dem.set(lic, (dem.get(lic) ?? 0) + 1)
  if (dat(lic)) continue
  if (NGOAI_LE[ten]) {
    ngoaiLe++
    continue
  }
  loi.push(`${id}: ${lic}`)
}

for (const [lic, n] of [...dem].sort((a, b) => b[1] - a[1])) console.log(`${String(n).padStart(4)}  ${lic}`)
console.log(`${dem.size} loại giấy phép, ${goi.size} gói, ${ngoaiLe} gói ngoại lệ đã duyệt.`)
if (loi.length) {
  console.error(`\nGói có giấy phép không được phép (${loi.length}):\n  ${loi.join('\n  ')}`)
  process.exit(1)
}
console.log('OK: mọi gói npm có giấy phép tương thích Apache-2.0.')
