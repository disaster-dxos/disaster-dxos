#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm tra mọi file mã nguồn đều có dòng SPDX-License-Identifier (yêu cầu PoF #1).
# Dùng trong CI. Thoát mã 1 nếu thiếu.
set -euo pipefail
cd "$(dirname "$0")/.."

missing=$(git ls-files --cached --others --exclude-standard \
  '*.py' '*.ts' '*.tsx' '*.js' '*.jsx' '*.mjs' '*.sql' '*.sh' \
  '*.yml' '*.yaml' '*.conf' 'Makefile' '.env.example' \
  | while read -r f; do head -n 5 "$f" | grep -q 'SPDX-License-Identifier' || echo "$f"; done)

if [ -n "$missing" ]; then
  echo "Thiếu header license ở các file sau — chạy scripts/add-license-header.sh:"
  echo "$missing"
  exit 1
fi
echo "OK: mọi file mã nguồn đều có SPDX header."
