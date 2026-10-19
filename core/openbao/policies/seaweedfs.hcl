# SPDX-License-Identifier: Apache-2.0
# Policy core-seaweedfs → AppRole "seaweedfs" (bao-agent-seaweedfs). Khóa S3 của SeaweedFS.
path "secret/data/core/s3" {
  capabilities = ["read"]
}
