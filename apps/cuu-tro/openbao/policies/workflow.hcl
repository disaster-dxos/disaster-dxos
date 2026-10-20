# SPDX-License-Identifier: Apache-2.0
# Policy app-cuu-tro-workflow → AppRole "app-cuu-tro-workflow" (bao-agent-cuu-tro, #29).
# scripts/openbao-init.sh nạp mọi file apps/<DXOS_APP>/openbao/policies/*.hcl. Chỉ đọc mật khẩu
# role DB dịch vụ cuu_tro_app; không đọc được bí mật nào của lõi.
path "secret/data/app/cuu-tro/db" {
  capabilities = ["read"]
}
