# SPDX-License-Identifier: Apache-2.0
# Policy core-nats → AppRole "nats" (bao-agent-nats, #30). Chỉ đọc mật khẩu NATS/MQTT của ứng dụng
# Tầng 2 đang chọn (secret/app/<DXOS_APP>/nats): một đoạn đường dẫn bất kỳ, như core-postgres.
path "secret/data/app/+/nats" {
  capabilities = ["read"]
}
