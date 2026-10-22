#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Bọc lệnh khởi động của dịch vụ: đọc bí mật do bao agent render (mỗi file một biến,
# tên file = tên biến), export rồi exec lệnh gốc. Bí mật không nằm trong .env hay
# `docker inspect`, chỉ có trong môi trường của tiến trình dịch vụ.
# Dùng: env-from-files.sh <thư mục> <lệnh gốc> [tham số...]
# Biến: SECRETS_REQUIRED (danh sách file phải có), SECRETS_WAIT_SECONDS (mặc định 120).
set -euo pipefail

dir=$1
shift
wait_max=${SECRETS_WAIT_SECONDS:-120}

for name in ${SECRETS_REQUIRED:-}; do
  waited=0
  until [ -s "$dir/$name" ]; do
    if [ "$waited" -ge "$wait_max" ]; then
      echo "env-from-files: chưa có $dir/$name sau ${wait_max}s. OpenBao đã init/unseal chưa? Chạy: make bao-init" >&2
      exit 1
    fi
    sleep 2
    waited=$((waited + 2))
  done
done

for f in "$dir"/*; do
  [ -f "$f" ] || continue
  name=$(basename "$f")
  [[ $name =~ ^[A-Z_][A-Z0-9_]*$ ]] || continue
  export "$name=$(cat "$f")"
done

exec "$@"
