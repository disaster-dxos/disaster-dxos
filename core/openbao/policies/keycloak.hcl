# SPDX-License-Identifier: Apache-2.0
# Policy core-keycloak → AppRole "keycloak" (bao-agent-keycloak). Chỉ đọc.
path "secret/data/core/keycloak-db" {
  capabilities = ["read"]
}

path "secret/data/core/keycloak-admin" {
  capabilities = ["read"]
}

path "secret/data/core/gateway" {
  capabilities = ["read"]
}
