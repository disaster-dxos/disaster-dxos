# SPDX-License-Identifier: Apache-2.0
# Policy core-ledger → AppRole "ledger" (bao-agent-ledger, #28).
# Khóa ký checkpoint Tessera (D-007): signing_key dạng note Ed25519, scripts/openbao-init.sh sinh một lần.
path "secret/data/core/ledger" {
  capabilities = ["read"]
}

# Token ghi sổ cái của backend ứng dụng Tầng 2 đang chọn (secret/app/<DXOS_APP>/ledger, write_token):
# ledger chỉ nhận POST /ledger/entries kèm token này. Một đoạn đường dẫn bất kỳ, như core-nats.
path "secret/data/app/+/ledger" {
  capabilities = ["read"]
}
