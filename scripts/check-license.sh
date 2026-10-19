#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm tra mọi file mã nguồn/cấu hình đều có dòng SPDX-License-Identifier (yêu cầu PoF).
# Loại file: xem scripts/spdx-files.sh. Dùng trong CI. Thoát mã 1 nếu thiếu.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=scripts/spdx-files.sh
. scripts/spdx-files.sh

missing=$(spdx_files | while read -r f; do
  head -n 5 "$f" | grep -q 'SPDX-License-Identifier' || echo "$f"
done)

if [ -n "$missing" ]; then
  echo "Thiếu header license ở các file sau — chạy: make license"
  echo "$missing"
  exit 1
fi
echo "OK: mọi file mã nguồn đều có SPDX header ($(spdx_files | wc -l | tr -d ' ') file)."
