# SPDX-License-Identifier: Apache-2.0
# Policy core-temporal → AppRole "temporal" (bao-agent-temporal). Mật khẩu role temporal.
path "secret/data/core/temporal-db" {
  capabilities = ["read"]
}
