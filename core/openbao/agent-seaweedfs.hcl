# SPDX-License-Identifier: Apache-2.0
# bao agent cho SeaweedFS: AppRole "seaweedfs" (policy core-seaweedfs). Render file định danh S3
# (-s3.config) từ secret/core/s3. Một định danh quản trị cho dịch vụ lõi; quyền theo bucket của
# ứng dụng làm ở #27. SeaweedFS chỉ đọc file này lúc khởi động: đổi khóa thì restart seaweedfs.

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
  destination = "/out/seaweedfs/s3.json"
  perms       = "0444"
  contents    = <<EOT
{{ with secret "secret/data/core/s3" }}{
  "identities": [
    {
      "name": "dxos-core",
      "credentials": [
        { "accessKey": "{{ .Data.data.access_key }}", "secretKey": "{{ .Data.data.secret_key }}" }
      ],
      "actions": ["Admin", "Read", "List", "Tagging", "Write"]
    }
  ]
}
{{ end }}
EOT
}
