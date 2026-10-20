# SPDX-License-Identifier: Apache-2.0
# bao agent cho backend apps/cuu-tro (#29): AppRole "app-cuu-tro-workflow". Render chuỗi kết nối
# PostgreSQL bằng role dịch vụ cuu_tro_app (không phải superuser, không phải role hasura).
# Tên role/CSDL lấy từ biến môi trường của agent (apps/cuu-tro/compose.yaml).

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
  destination = "/out/cuu-tro/APP_DB_URL"
  perms       = "0444"
  contents    = "{{ with secret \"secret/data/app/cuu-tro/db\" }}postgres://{{ env \"APP_DB_USER\" }}:{{ .Data.data.password | urlquery }}@postgres:5432/{{ env \"POSTGRES_DB\" }}{{ end }}"
}
