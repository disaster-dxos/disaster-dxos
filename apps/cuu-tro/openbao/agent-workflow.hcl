# SPDX-License-Identifier: Apache-2.0
# bao agent cho backend apps/cuu-tro (#29): AppRole "app-cuu-tro-workflow". Render chuỗi kết nối
# PostgreSQL bằng role dịch vụ cuu_tro_app (không phải superuser, không phải role hasura), và (#30)
# NATS_URL cho backend (user cuu-tro-app), MQTT_PASSWORD cho bộ giả lập (user cuu-tro-thiet-bi,
# volume riêng /out/cuu-tro-thiet-bi: worker/API/consumer không mount, không thấy mật khẩu thiết bị).
# Ảnh hiện trường (#27): volume riêng /out/cuu-tro-api cho cuu-tro-api: APP_DB_URL + khóa S3 của ứng
# dụng (định danh cuu-tro-app trên SeaweedFS, chỉ bucket cuu-tro-*), không có mật khẩu NATS/MQTT.
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

template {
  destination = "/out/cuu-tro/NATS_URL"
  perms       = "0444"
  contents    = "{{ with secret \"secret/data/app/cuu-tro/nats\" }}nats://cuu-tro-app:{{ .Data.data.app_password | urlquery }}@nats:4222{{ end }}"
}

template {
  destination = "/out/cuu-tro-thiet-bi/MQTT_PASSWORD"
  perms       = "0444"
  contents    = "{{ with secret \"secret/data/app/cuu-tro/nats\" }}{{ .Data.data.device_password }}{{ end }}"
}

template {
  destination = "/out/cuu-tro-api/APP_DB_URL"
  perms       = "0444"
  contents    = "{{ with secret \"secret/data/app/cuu-tro/db\" }}postgres://{{ env \"APP_DB_USER\" }}:{{ .Data.data.password | urlquery }}@postgres:5432/{{ env \"POSTGRES_DB\" }}{{ end }}"
}

template {
  destination = "/out/cuu-tro-api/S3_ACCESS_KEY"
  perms       = "0444"
  contents    = "{{ with secret \"secret/data/app/cuu-tro/s3\" }}{{ .Data.data.access_key }}{{ end }}"
}

template {
  destination = "/out/cuu-tro-api/S3_SECRET_KEY"
  perms       = "0444"
  contents    = "{{ with secret \"secret/data/app/cuu-tro/s3\" }}{{ .Data.data.secret_key }}{{ end }}"
}
