# SPDX-License-Identifier: Apache-2.0
# Policy core-seaweedfs → AppRole "seaweedfs". Khóa S3 cho SeaweedFS; nối vào dịch vụ ở #11.
path "secret/data/core/s3" {
  capabilities = ["read"]
}
