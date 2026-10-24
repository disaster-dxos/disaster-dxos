# SPDX-License-Identifier: Apache-2.0
# bao agent cho Scorpio NGSI-LD (#85): AppRole "scorpio" (policy core-scorpio). Render mật khẩu role scorpio
# (biến DBPASS của Scorpio, đọc theo ${dbpass} trong cấu hình Quarkus của image).

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
  destination = "/out/scorpio/DBPASS"
  perms       = "0444"
  contents    = "{{ with secret \"secret/data/core/scorpio-db\" }}{{ .Data.data.password }}{{ end }}"
}
