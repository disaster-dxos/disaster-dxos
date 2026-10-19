#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# CHỈ DÙNG CHO MÁY DEV. Tự mở khóa OpenBao sau khi khởi động lại (reboot, make down/up)
# bằng unseal key do scripts/openbao-init.sh ghi ra $OPENBAO_LOCAL_DIR/unseal/ (ngoài repo).
# Giữ key trên cùng máy với OpenBao làm mất ý nghĩa của seal: trên VPS/production đặt
# OPENBAO_DEV_AUTO_UNSEAL=false và mở khóa thủ công (make bao-unseal) hoặc dùng auto-unseal
# bằng KMS/transit.
set -eu

if [ "${OPENBAO_DEV_AUTO_UNSEAL:-false}" != "true" ]; then
  echo "dev-auto-unseal: tắt (OPENBAO_DEV_AUTO_UNSEAL=${OPENBAO_DEV_AUTO_UNSEAL:-false})"
  exit 0
fi

keys=/openbao/unseal/unseal.keys
while :; do
  rc=0
  bao status >/dev/null 2>&1 || rc=$?
  # bao status: 0 = đã mở khóa, 2 = sealed (hoặc chưa init), 1 = không kết nối được
  if [ "$rc" -eq 2 ] && [ -s "$keys" ]; then
    while read -r k; do
      bao status >/dev/null 2>&1 && break
      bao operator unseal "$k" >/dev/null || true
    done < "$keys"
    if bao status >/dev/null 2>&1; then echo "dev-auto-unseal: đã mở khóa OpenBao"; fi
  fi
  sleep 10
done
