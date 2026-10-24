#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Khởi động Scorpio all-in-one cho cả hai bản image gốc (#99), chạy sau env-from-files.sh (đã nạp DBPASS):
#  - bản native GraalVM (linux-amd64-*, thư mục làm việc /work): ./application — mặc định trên máy amd64;
#  - bản JVM (java-*, thư mục làm việc /usr/src/scorpio): java -jar quarkus-run.jar — Makefile chọn trên
#    arm64 (Apple Silicon), vì bản native cần AVX/AVX2 mà Rosetta trong VM không có.
# Không sửa image: chỉ chọn lệnh theo tệp có trong thư mục làm việc của image.
set -euo pipefail
if [ -x ./application ]; then
  exec ./application -Dquarkus.http.host=0.0.0.0 "$@"
elif [ -f quarkus-run.jar ]; then
  exec java -Dquarkus.http.host=0.0.0.0 --enable-native-access=ALL-UNNAMED -jar quarkus-run.jar "$@"
fi
echo "scorpio: không thấy ./application (bản native) hay quarkus-run.jar (bản JVM) trong $(pwd)" >&2
exit 1
