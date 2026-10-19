# SPDX-License-Identifier: Apache-2.0
# Policy core-keycloak → AppRole "keycloak" (bao-agent-keycloak). Chỉ đọc.
# Agent này cũng render mật khẩu DB của Keycloak cho PostgreSQL (tạo role lần đầu).
path "secret/data/core/keycloak-db" {
  capabilities = ["read"]
}

path "secret/data/core/keycloak-admin" {
  capabilities = ["read"]
}

path "secret/data/core/gateway" {
  capabilities = ["read"]
}
