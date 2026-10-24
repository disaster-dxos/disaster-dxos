# SPDX-License-Identifier: Apache-2.0
# Policy core-scorpio → AppRole "scorpio" (bao-agent-scorpio, #85). Mật khẩu role scorpio.
path "secret/data/core/scorpio-db" {
  capabilities = ["read"]
}
