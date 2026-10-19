#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Thêm header SPDX vào các file còn thiếu. Chạy trước khi commit (make license).
# Giữ shebang và chỉ thị parser của Dockerfile ở đầu file.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=scripts/spdx-files.sh
. scripts/spdx-files.sh
LICENSE_ID="${LICENSE_ID:-Apache-2.0}"

spdx_files | while read -r f; do
  head -n 5 "$f" | grep -q 'SPDX-License-Identifier' && continue
  c=$(spdx_comment "$f" "$LICENSE_ID")
  keep=$(spdx_keep_lines "$f")
  tmp=$(mktemp)
  # head -n 0 không chạy trên macOS/BSD nên chỉ gọi khi có dòng cần giữ
  { if [ "$keep" -gt 0 ]; then head -n "$keep" "$f"; fi; echo "$c"; tail -n +"$((keep + 1))" "$f"; } > "$tmp"
  cat "$tmp" > "$f" && rm "$tmp"
  echo "+ $f"
done
