# SPDX-License-Identifier: Apache-2.0
# Policy core-ledger → AppRole "ledger". Khóa ký checkpoint Tessera (D-007); dùng khi có core/ledger (#28).
path "secret/data/core/ledger" {
  capabilities = ["read"]
}
