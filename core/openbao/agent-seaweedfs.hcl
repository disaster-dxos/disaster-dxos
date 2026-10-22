# SPDX-License-Identifier: Apache-2.0
# bao agent cho SeaweedFS: AppRole "seaweedfs" (policy core-seaweedfs). Render file định danh S3
# (-s3.config). SeaweedFS chỉ đọc file này lúc khởi động: đổi khóa thì restart seaweedfs.
# Hai định danh, không có định danh nặc danh (mọi bucket riêng tư: request không ký → 403):
#   dxos-core        secret/core/s3, quản trị (smoke, vận hành). Không cấp cho ứng dụng Tầng 2.
#   <DXOS_APP>-app   secret/app/<DXOS_APP>/s3 (#27): chỉ Read/Write/List trên bucket có tên bắt đầu
#                    bằng "<DXOS_APP>-" (vd cuu-tro-media). Lõi chỉ biết quy ước tiền tố, không biết
#                    tên bucket nghiệp vụ; bucket do ứng dụng khai báo (apps/<DXOS_APP>/s3/buckets).
#                    Không có Admin: không tạo/xóa bucket, không đổi chính sách bucket.

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
{
  "identities": [{{ with secret "secret/data/core/s3" }}
    {
      "name": "dxos-core",
      "credentials": [
        { "accessKey": "{{ .Data.data.access_key }}", "secretKey": "{{ .Data.data.secret_key }}" }
      ],
      "actions": ["Admin", "Read", "List", "Tagging", "Write"]
    }{{ end }}{{ $app := env "DXOS_APP" }}{{ with secret (printf "secret/data/app/%s/s3" $app) }},
    {
      "name": "{{ $app }}-app",
      "credentials": [
        { "accessKey": "{{ .Data.data.access_key }}", "secretKey": "{{ .Data.data.secret_key }}" }
      ],
      "actions": ["Read:{{ $app }}-*", "Write:{{ $app }}-*", "List:{{ $app }}-*"]
    }{{ end }}
  ]
}
EOT
}
