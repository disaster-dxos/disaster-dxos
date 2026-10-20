#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Tạo bucket S3 do ứng dụng Tầng 2 khai báo (#27). Chạy một lần mỗi lần up (container s3-buckets,
# image SeaweedFS gốc, sh của busybox). Lõi không biết tên bucket nghiệp vụ: chỉ đọc quy ước
#   apps/${DXOS_APP}/s3/buckets.conf   mỗi dòng một tên bucket, dòng trống và "#" bỏ qua
# và chỉ nhận tên bắt đầu bằng "${DXOS_APP}-" (định danh S3 của ứng dụng chỉ dùng được các bucket đó,
# core/openbao/agent-seaweedfs.hcl). Bucket đã có thì giữ nguyên: chạy lại không lỗi, không xóa gì.
# Dùng "weed shell" nói chuyện trực tiếp với master/filer trong mạng nội bộ, không cần khóa S3.
set -eu

APP=${DXOS_APP:?Thiếu DXOS_APP}
FILE=${S3_BUCKETS_FILE:-/opt/dxos/app-s3/buckets.conf}
MASTER=${SEAWEEDFS_MASTER:-seaweedfs:9333}
FILER=${SEAWEEDFS_FILER:-seaweedfs:8888}

if [ ! -f "$FILE" ]; then
  echo "s3-buckets: apps/$APP/s3/buckets.conf không có, bỏ qua"
  exit 0
fi

weed_sh() { printf '%s\n' "$1" | weed shell -master="$MASTER" -filer="$FILER" 2>&1; }

existing=$(weed_sh "s3.bucket.list") || { echo "s3-buckets: LỖI: không liệt kê được bucket: $existing" >&2; exit 1; }

n=0
# shellcheck disable=SC2013 # đọc theo từ: mỗi dòng đúng một tên, bỏ phần comment bên dưới
for b in $(sed -e 's/#.*//' "$FILE"); do
  case $b in
    "$APP"-*) ;;
    *) echo "s3-buckets: LỖI: bucket '$b' phải bắt đầu bằng '$APP-'" >&2; exit 1 ;;
  esac
  # Quy tắc tên bucket S3: 3-63 ký tự, chữ thường, số, gạch ngang
  if ! printf '%s' "$b" | grep -Eq '^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$'; then
    echo "s3-buckets: LỖI: tên bucket '$b' không hợp lệ" >&2
    exit 1
  fi
  n=$((n + 1))
  if printf '%s\n' "$existing" | grep -Eq "^[[:space:]]*$b([[:space:]]|$)"; then
    echo "s3-buckets: $b đã có, giữ nguyên"
    continue
  fi
  out=$(weed_sh "s3.bucket.create -name $b")
  # weed shell trả mã 0 cả khi lệnh lỗi: kiểm lại bằng danh sách bucket
  if weed_sh "s3.bucket.list" | grep -Eq "^[[:space:]]*$b([[:space:]]|$)"; then
    echo "s3-buckets: đã tạo $b"
  else
    echo "s3-buckets: LỖI: không tạo được $b: $out" >&2
    exit 1
  fi
done
echo "s3-buckets: xong ($n bucket của $APP)"
