# SPDX-License-Identifier: Apache-2.0
# Policy core-apisix → AppRole "apisix" (bao-agent-apisix). Chỉ đọc secret client dxos-gateway.
path "secret/data/core/gateway" {
  capabilities = ["read"]
}
