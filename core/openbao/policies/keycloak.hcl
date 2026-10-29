# SPDX-License-Identifier: Apache-2.0
# Policy core-keycloak → AppRole "keycloak" (bao-agent-keycloak). Chỉ đọc.
# core/grafana-oauth: secret client dxos-grafana (#126), keycloak-grafana-client ghi vào Keycloak.
path "secret/data/core/keycloak-db" {
  capabilities = ["read"]
}

path "secret/data/core/keycloak-admin" {
  capabilities = ["read"]
}

path "secret/data/core/gateway" {
  capabilities = ["read"]
}

path "secret/data/core/grafana-oauth" {
  capabilities = ["read"]
}
