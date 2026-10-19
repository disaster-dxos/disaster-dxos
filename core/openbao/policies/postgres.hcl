# SPDX-License-Identifier: Apache-2.0
# Policy core-postgres → AppRole "postgres" (bao-agent-postgres). Chỉ đọc.
# Mật khẩu superuser (initdb lần đầu, postgres-roles) và mật khẩu role của từng dịch vụ:
# postgres-roles tạo/đồng bộ role keycloak, hasura, temporal bằng các giá trị này.
path "secret/data/core/postgres" {
  capabilities = ["read"]
}

path "secret/data/core/keycloak-db" {
  capabilities = ["read"]
}

path "secret/data/core/hasura-db" {
  capabilities = ["read"]
}

path "secret/data/core/temporal-db" {
  capabilities = ["read"]
}
