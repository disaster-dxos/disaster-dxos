# SPDX-License-Identifier: Apache-2.0
# bao agent cho Keycloak: đăng nhập AppRole "keycloak" (policy core-keycloak), render bí mật
# thành file trên volume tmpfs. Tên file = tên biến môi trường; core/openbao/env-from-files.sh
# đọc và export trước khi chạy dịch vụ. Agent đọc lại KV mỗi 5 phút.

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

# --- Keycloak ---
template {
  destination = "/out/keycloak/KC_DB_PASSWORD"
  perms       = "0444"
  contents    = "{{ with secret \"secret/data/core/keycloak-db\" }}{{ .Data.data.password }}{{ end }}"
}

template {
  destination = "/out/keycloak/KC_BOOTSTRAP_ADMIN_PASSWORD"
  perms       = "0444"
  contents    = "{{ with secret \"secret/data/core/keycloak-admin\" }}{{ .Data.data.password }}{{ end }}"
}

# Realm import thay ${KC_GATEWAY_CLIENT_SECRET} trong apps/<app>/keycloak/realm.json
template {
  destination = "/out/keycloak/KC_GATEWAY_CLIENT_SECRET"
  perms       = "0444"
  contents    = "{{ with secret \"secret/data/core/gateway\" }}{{ .Data.data.client_secret }}{{ end }}"
}

# --- PostgreSQL: core/postgres/init tạo role keycloak bằng mật khẩu này (chỉ lần đầu) ---
template {
  destination = "/out/postgres/KEYCLOAK_DB_PASSWORD"
  perms       = "0444"
  contents    = "{{ with secret \"secret/data/core/keycloak-db\" }}{{ .Data.data.password }}{{ end }}"
}
