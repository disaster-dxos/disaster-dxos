// SPDX-License-Identifier: Apache-2.0
// Kiểm giấy phép mọi gói npm (kể cả phụ thuộc bắc cầu) từ package-lock.json, không cần mạng.
// Đạt khi mỗi gói có giấy phép OSI tương thích Apache-2.0, hoặc nằm trong NGOAI_LE (có lý do).
// Biểu thức "A OR B": đạt nếu một vế đạt. Gặp GPL/AGPL/LGPL-only hay giấy phép lạ → thoát mã 1.
// Dùng: npm run licenses  (CI job web chạy lệnh này). Bảng tổng hợp: DEPENDENCIES.md mục Web.
import { readFileSync } from 'node:fs'

const OSI = new Set([
  'MIT', 'ISC', 'Apache-2.0', 'BSD-2-Clause', 'BSD-3-Clause', '0BSD', 'MPL-2.0', 'BlueOak-1.0.0', 'Python-2.0',
])

// Không phải giấy phép OSI nhưng là dữ liệu/công cụ chỉ dùng lúc build hoặc dev, không vào bản build
// (.output) và tương thích Apache-2.0. Thêm gói vào đây phải ghi lý do trong DEPENDENCIES.md.
const NGOAI_LE = {
  'caniuse-lite': 'CC-BY-4.0: dữ liệu trình duyệt cho autoprefixer lúc build',
  'mdn-data': 'CC0-1.0: dữ liệu CSS cho css-tree/csso lúc build',
  '@speed-highlight/core': 'CC0-1.0: tô màu mã trong trang lỗi của nuxt dev (youch)',
}

function dat(expr) {
  return expr.replace(/[()]/g, '').split(/\s+OR\s+/).some((x) => OSI.has(x.trim()))
}

const lock = JSON.parse(readFileSync(new URL('../package-lock.json', import.meta.url), 'utf8'))
const loi = []
const dem = new Map()
let ngoaiLe = 0
for (const [path, pkg] of Object.entries(lock.packages)) {
  if (!path) continue
  const name = path.slice(path.lastIndexOf('node_modules/') + 'node_modules/'.length)
  const lic = typeof pkg.license === 'string' ? pkg.license : 'KHÔNG RÕ'
  dem.set(lic, (dem.get(lic) ?? 0) + 1)
  if (dat(lic)) continue
  if (NGOAI_LE[name]) { ngoaiLe++; continue }
  loi.push(`${name}@${pkg.version}: ${lic}`)
}

for (const [lic, n] of [...dem].sort((a, b) => b[1] - a[1])) console.log(`${String(n).padStart(4)}  ${lic}`)
console.log(`${dem.size} loại giấy phép, ${[...dem.values()].reduce((a, b) => a + b, 0)} gói, ${ngoaiLe} gói ngoại lệ đã duyệt.`)
if (loi.length) {
  console.error(`\nGói có giấy phép không được phép (${loi.length}):\n  ${loi.join('\n  ')}`)
  process.exit(1)
}
console.log('OK: mọi gói npm có giấy phép tương thích Apache-2.0.')
