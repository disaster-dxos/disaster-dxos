# SPDX-License-Identifier: Apache-2.0
# Policy app-cuu-tro-workflow → AppRole "app-cuu-tro-workflow" (bao-agent-cuu-tro, #29).
# scripts/openbao-init.sh nạp mọi file apps/<DXOS_APP>/openbao/policies/*.hcl. Chỉ đọc mật khẩu
# role DB dịch vụ cuu_tro_app và mật khẩu NATS/MQTT của ứng dụng; không đọc được bí mật nào của lõi.
path "secret/data/app/cuu-tro/db" {
  capabilities = ["read"]
}

# NATS (#30): bao-agent-cuu-tro render NATS_URL (user cuu-tro-app) cho consumer cuu-tro-cam-bien và
# MQTT_PASSWORD (user cuu-tro-thiet-bi) cho bộ giả lập, mỗi thứ một volume tmpfs riêng.
path "secret/data/app/cuu-tro/nats" {
  capabilities = ["read"]
}

# S3 (#27): bao-agent-cuu-tro render khóa S3 của ứng dụng cho cuu-tro-api (volume secrets-cuu-tro-api).
# Định danh này trên SeaweedFS chỉ Read/Write/List bucket cuu-tro-* (core/openbao/agent-seaweedfs.hcl).
path "secret/data/app/cuu-tro/s3" {
  capabilities = ["read"]
}

# Sổ cái (#28): bao-agent-cuu-tro render token ghi sổ cái cho cuu-tro-api. Khóa ký checkpoint
# (secret/core/ledger) KHÔNG đọc được: chỉ dịch vụ ledger của lõi có.
path "secret/data/app/cuu-tro/ledger" {
  capabilities = ["read"]
}

# Thông báo realtime (#68): bao-agent-cuu-tro render khóa ký token kết nối Centrifugo cho cuu-tro-api
# và API key Centrifugo + NATS_URL cho cầu nối cuu-tro-thong-bao (mỗi dịch vụ một volume tmpfs riêng).
path "secret/data/app/cuu-tro/realtime" {
  capabilities = ["read"]
}

# Thông báo cảnh báo (#87): token bot Telegram + chat id (trống = chỉ kênh gia-lap). bao-agent-cuu-tro render
# cho cuu-tro-worker (volume riêng secrets-cuu-tro-worker), không cho dịch vụ nào khác.
path "secret/data/app/cuu-tro/telegram" {
  capabilities = ["read"]
}
