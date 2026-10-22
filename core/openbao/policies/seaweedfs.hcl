# SPDX-License-Identifier: Apache-2.0
# Policy core-seaweedfs → AppRole "seaweedfs" (bao-agent-seaweedfs). Khóa S3 của SeaweedFS.
path "secret/data/core/s3" {
  capabilities = ["read"]
}

# Khóa S3 của ứng dụng Tầng 2 đang chọn (secret/app/<DXOS_APP>/s3, #27): render thành định danh
# <DXOS_APP>-app chỉ được dùng bucket "<DXOS_APP>-*". Một đoạn đường dẫn bất kỳ, như core-postgres.
path "secret/data/app/+/s3" {
  capabilities = ["read"]
}
