# SPDX-License-Identifier: Apache-2.0
# Policy core-grafana → AppRole "grafana" (bao-agent-grafana, #92). Mật khẩu admin Grafana và mật khẩu role
# chỉ đọc <schema>_bi của ứng dụng (datasource PostgreSQL).
path "secret/data/core/grafana" {
  capabilities = ["read"]
}

path "secret/data/app/+/bi-db" {
  capabilities = ["read"]
}
