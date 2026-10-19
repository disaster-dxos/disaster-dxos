# SPDX-License-Identifier: Apache-2.0
# bao agent cho Hasura: AppRole "hasura" (policy core-hasura). Render chuỗi kết nối CSDL bằng
# role hasura (không phải superuser) và admin secret. Tên user/CSDL lấy từ biến môi trường của agent.

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
  destination = "/out/hasura/HASURA_GRAPHQL_DATABASE_URL"
  perms       = "0444"
  contents    = "{{ with secret \"secret/data/core/hasura-db\" }}postgres://{{ env \"HASURA_DB_USER\" }}:{{ .Data.data.password | urlquery }}@postgres:5432/{{ env \"POSTGRES_DB\" }}{{ end }}"
}

template {
  destination = "/out/hasura/HASURA_GRAPHQL_ADMIN_SECRET"
  perms       = "0444"
  contents    = "{{ with secret \"secret/data/core/hasura\" }}{{ .Data.data.admin_secret }}{{ end }}"
}
