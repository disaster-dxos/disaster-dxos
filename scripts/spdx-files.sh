#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Danh sách file phải có header SPDX, dùng chung cho check-license.sh và add-license-header.sh.
# In ra đường dẫn (tương đối gốc repo) của file đã theo dõi hoặc chưa theo dõi nhưng không bị .gitignore.
# Go: quét `*.go` và `go.mod` (comment `//`); bỏ qua `go.sum` vì định dạng không cho phép comment.

spdx_files() {
  git ls-files --cached --others --exclude-standard -- \
    '*.py' '*.sh' '*.sql' \
    '*.ts' '*.tsx' '*.js' '*.jsx' '*.mjs' '*.cjs' '*.vue' \
    '*.dart' '*.go' ':(glob)**/go.mod' \
    '*.yml' '*.yaml' '*.toml' '*.conf' '*.hcl' \
    ':(glob)**/Dockerfile' ':(glob)**/Dockerfile.*' ':(glob)**/*.Dockerfile' \
    ':(glob)**/Makefile' ':(glob)**/.env.example' \
  | while read -r f; do [ -f "$f" ] && echo "$f"; done
}

# Dòng comment SPDX phù hợp với định dạng của file
spdx_comment() {
  local f="$1" id="${2:-Apache-2.0}"
  case "$f" in
    *.sql)                        echo "-- SPDX-License-Identifier: $id" ;;
    *.vue)                        echo "<!-- SPDX-License-Identifier: $id -->" ;;
    *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs|*.dart|*.go|go.mod|*/go.mod) echo "// SPDX-License-Identifier: $id" ;;
    *)                            echo "# SPDX-License-Identifier: $id" ;;
  esac
}

# Số dòng đầu file phải giữ nguyên trước header:
# shebang (#!) và chỉ thị parser của Dockerfile (# syntax=, # escape=, # check=)
# shellcheck disable=SC2094 # basename chỉ xử lý chuỗi tên file, không ghi vào "$f"
spdx_keep_lines() {
  local f="$1" n=0 line
  while IFS= read -r line || [ -n "$line" ]; do
    if [ "$n" -eq 0 ] && [[ "$line" == '#!'* ]]; then n=1; continue; fi
    case "$(basename "$f")" in
      Dockerfile|Dockerfile.*|*.Dockerfile)
        if [[ "$line" =~ ^#[[:space:]]*(syntax|escape|check)= ]]; then n=$((n + 1)); continue; fi ;;
    esac
    break
  done < "$f"
  echo "$n"
}
