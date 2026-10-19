# SPDX-License-Identifier: Apache-2.0
# bao agent cho PostgreSQL: AppRole "postgres" (policy core-postgres). Render mật khẩu superuser
# (initdb lần đầu) và mật khẩu role của từng dịch vụ cho postgres + postgres-roles
# (core/postgres/sync-roles.sh tạo/đồng bộ role keycloak, hasura, temporal).

vault {
  address = "http://openbao:8200"
  retry {
    num_retries = -1
  }
}

auto_auth {
  method "approle" {
    mount_path = "auth/approle"
    config = {
      role_id_file_path                   = "/openbao/approle/role_id"
      secret_id_file_path                 = "/openbao/approle/secret_id"
      remove_secret_id_file_after_reading = false
    }
  }
}

template_config {
  static_secret_render_interval = "5m"
  exit_on_retry_failure         = false
}

template {
  destination = "/out/postgres/POSTGRES_PASSWORD"
  perms       = "0444"
  contents    = "{{ with secret \"secret/data/core/postgres\" }}{{ .Data.data.password }}{{ end }}"
}

template {
  destination = "/out/postgres/KEYCLOAK_DB_PASSWORD"
  perms       = "0444"
  contents    = "{{ with secret \"secret/data/core/keycloak-db\" }}{{ .Data.data.password }}{{ end }}"
}

template {
  destination = "/out/postgres/HASURA_DB_PASSWORD"
  perms       = "0444"
  contents    = "{{ with secret \"secret/data/core/hasura-db\" }}{{ .Data.data.password }}{{ end }}"
}

template {
  destination = "/out/postgres/TEMPORAL_DB_PASSWORD"
  perms       = "0444"
  contents    = "{{ with secret \"secret/data/core/temporal-db\" }}{{ .Data.data.password }}{{ end }}"
}
