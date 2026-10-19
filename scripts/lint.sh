#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Lint mã nguồn: shellcheck cho mọi *.sh, yamllint cho mọi *.yml/*.yaml (cấu hình: .yamllint.yml).
# Dùng: scripts/lint.sh [shell|yaml|all]   (mặc định: all). Dùng trong CI và `make lint`.
set -euo pipefail
cd "$(dirname "$0")/.."

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Thiếu công cụ '$1'. Cài: $2" >&2
    exit 127
  }
}

lint_shell() {
  need shellcheck "brew install shellcheck | apt-get install shellcheck | pip install shellcheck-py"
  local files=()
  while IFS= read -r -d '' f; do files+=("$f"); done < <(git ls-files -z --cached --others --exclude-standard -- '*.sh')
  if [ "${#files[@]}" -eq 0 ]; then echo "shellcheck: không có file *.sh"; return 0; fi
  shellcheck "${files[@]}"
  echo "OK: shellcheck ${#files[@]} file"
}

lint_yaml() {
  need yamllint "pip install yamllint"
  yamllint --strict .
  echo "OK: yamllint"
}

case "${1:-all}" in
  shell) lint_shell ;;
  yaml)  lint_yaml ;;
  all)   lint_shell; lint_yaml ;;
  *) echo "Dùng: $0 [shell|yaml|all]" >&2; exit 2 ;;
esac
