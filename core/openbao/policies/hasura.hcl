# SPDX-License-Identifier: Apache-2.0
# Policy core-hasura → AppRole "hasura" (bao-agent-hasura). Mật khẩu role hasura + admin secret.
path "secret/data/core/hasura-db" {
  capabilities = ["read"]
}

path "secret/data/core/hasura" {
  capabilities = ["read"]
}
