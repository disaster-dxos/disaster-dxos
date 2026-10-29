# SPDX-License-Identifier: Apache-2.0
# bao agent cho Grafana (#92): AppRole "grafana" (policy core-grafana). Render mật khẩu admin (Grafana đọc qua
# GF_SECURITY_ADMIN_PASSWORD__FILE), mật khẩu role chỉ đọc <schema>_bi (datasource đọc qua $__file{...}) và
# secret client Keycloak dxos-grafana (GF_AUTH_GENERIC_OAUTH_CLIENT_SECRET__FILE, #126).

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
  destination = "/out/grafana/admin_password"
  perms       = "0444"
  contents    = "{{ with secret \"secret/data/core/grafana\" }}{{ .Data.data.admin_password }}{{ end }}"
}

template {
  destination = "/out/grafana/bi_db_password"
  perms       = "0444"
  contents    = "{{ with secret (printf \"secret/data/app/%s/bi-db\" (env \"DXOS_APP\")) }}{{ .Data.data.password }}{{ end }}"
}

template {
  destination = "/out/grafana/oauth_client_secret"
  perms       = "0444"
  contents    = "{{ with secret \"secret/data/core/grafana-oauth\" }}{{ .Data.data.client_secret }}{{ end }}"
}
