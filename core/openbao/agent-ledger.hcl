# SPDX-License-Identifier: Apache-2.0
# bao agent cho sổ cái core/ledger (#28): AppRole "ledger" (policy core-ledger). Render 2 file vào
# volume tmpfs secrets-ledger (ledger đọc thẳng file, image scratch không có shell):
#   signing_key  khóa ký checkpoint Ed25519 dạng note (secret/core/ledger). Chỉ ledger mount volume này.
#   writers      "<DXOS_APP>-api <token>": dịch vụ được POST /ledger/entries (secret/app/<DXOS_APP>/ledger).
# ledger đọc lại writers ở mỗi request ghi: đổi token trong OpenBao có hiệu lực sau lần render kế tiếp.
# Khóa ký chỉ đọc lúc khởi động: đổi khóa (hiếm, phải công bố verifier mới) thì restart ledger.

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
  destination = "/out/ledger/signing_key"
  perms       = "0444"
  contents    = "{{ with secret \"secret/data/core/ledger\" }}{{ .Data.data.signing_key }}{{ end }}"
}

template {
  destination = "/out/ledger/writers"
  perms       = "0444"
  contents    = <<EOT
{{ $app := env "DXOS_APP" }}{{ with secret (printf "secret/data/app/%s/ledger" $app) }}{{ $app }}-api {{ .Data.data.write_token }}
{{ end }}
EOT
}
