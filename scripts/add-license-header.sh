#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Thêm header SPDX vào các file mã nguồn còn thiếu. Chạy trước khi commit.
set -euo pipefail
cd "$(dirname "$0")/.."
LICENSE_ID="${LICENSE_ID:-Apache-2.0}"

git ls-files --cached --others --exclude-standard \
  '*.py' '*.ts' '*.tsx' '*.js' '*.jsx' '*.mjs' '*.sql' '*.sh' \
  '*.yml' '*.yaml' '*.conf' 'Makefile' '.env.example' \
  | while read -r f; do
    head -n 5 "$f" | grep -q 'SPDX-License-Identifier' && continue
    case "$f" in
      *.py|*.sh|*.yml|*.yaml|*.conf|Makefile|.env.example) c="# SPDX-License-Identifier: $LICENSE_ID" ;;
      *.sql)     c="-- SPDX-License-Identifier: $LICENSE_ID" ;;
      *)         c="// SPDX-License-Identifier: $LICENSE_ID" ;;
    esac
    tmp=$(mktemp)
    if head -n 1 "$f" | grep -q '^#!'; then
      { head -n 1 "$f"; echo "$c"; tail -n +2 "$f"; } > "$tmp"
    else
      { echo "$c"; cat "$f"; } > "$tmp"
    fi
    cat "$tmp" > "$f" && rm "$tmp"
    echo "+ $f"
  done
