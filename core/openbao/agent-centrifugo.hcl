# SPDX-License-Identifier: Apache-2.0
# bao agent cho Centrifugo OSS (#68): AppRole "centrifugo" (policy core-centrifugo). Render file cấu
# hình CHỈ chứa bí mật vào volume tmpfs secrets-centrifugo; mọi tùy chọn khác đặt bằng biến môi trường
# CENTRIFUGO_* trong docker-compose.yml (biến môi trường ghi đè file):
#   client.token.hmac_secret_key  kiểm chữ ký token kết nối do <DXOS_APP>-api cấp (HS256)
#   http_api.key                  header X-API-Key của HTTP API (chỉ mạng nội bộ; APISIX không route /api)
# Đổi bí mật trong OpenBao: agent render lại sau static_secret_render_interval, rồi restart centrifugo.

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
  destination = "/out/centrifugo/config.json"
  perms       = "0444"
  contents    = <<EOT
{{ with secret (printf "secret/data/app/%s/realtime" (env "DXOS_APP")) }}{"client": {"token": {"hmac_secret_key": {{ .Data.data.token_hmac_secret | toJSON }}}}, "http_api": {"key": {{ .Data.data.api_key | toJSON }}}}{{ end }}
EOT
}
