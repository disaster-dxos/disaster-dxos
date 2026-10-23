# SPDX-License-Identifier: Apache-2.0
# Policy core-centrifugo → AppRole "centrifugo" (bao-agent-centrifugo, #68).
# Khóa HS256 kiểm token kết nối và API key của HTTP API của Centrifugo, thuộc ứng dụng Tầng 2 đang
# chọn (secret/app/<DXOS_APP>/realtime): backend ứng dụng ký token / gọi API bằng cùng bí mật.
# Một đoạn đường dẫn bất kỳ, như core-ledger, core-nats.
path "secret/data/app/+/realtime" {
  capabilities = ["read"]
}
