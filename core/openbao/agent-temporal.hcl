# SPDX-License-Identifier: Apache-2.0
# bao agent cho Temporal: AppRole "temporal" (policy core-temporal). Render mật khẩu role temporal
# (biến POSTGRES_PWD của image temporalio/auto-setup).

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
  destination = "/out/temporal/POSTGRES_PWD"
  perms       = "0444"
  contents    = "{{ with secret \"secret/data/core/temporal-db\" }}{{ .Data.data.password }}{{ end }}"
}
