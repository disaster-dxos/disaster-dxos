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
