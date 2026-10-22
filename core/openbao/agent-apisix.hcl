# SPDX-License-Identifier: Apache-2.0
# bao agent cho APISIX: AppRole "apisix" (policy core-apisix) chỉ đọc được secret của client
# dxos-gateway. APISIX đọc biến qua $env://KC_GATEWAY_CLIENT_SECRET (core/apisix/config.yaml).

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
  destination = "/out/apisix/KC_GATEWAY_CLIENT_SECRET"
  perms       = "0444"
  contents    = "{{ with secret \"secret/data/core/gateway\" }}{{ .Data.data.client_secret }}{{ end }}"
}
