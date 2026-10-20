# SPDX-License-Identifier: Apache-2.0
# bao agent cho NATS (#30): AppRole "nats" (policy core-nats). Render file cấu hình xác thực
# auth.conf mà core/nats/nats.conf include. Lõi chỉ biết quy ước, không biết topic nghiệp vụ:
#   <DXOS_APP>-app       backend của ứng dụng, chỉ kết nối NATS thường (STANDARD): pub/sub trong
#                        <DXOS_APP>.>, gọi JetStream API, nhận trả lời qua _INBOX.>
#   <DXOS_APP>-thiet-bi  thiết bị/giả lập, chỉ kết nối MQTT: chỉ gửi vào <DXOS_APP>.> (topic
#                        <DXOS_APP>/...), không đăng ký nhận gì
# Mật khẩu ở secret/app/<DXOS_APP>/nats (scripts/openbao-init.sh sinh ngẫu nhiên lần đầu).
# NATS đọc mật khẩu dạng rõ trong file tmpfs (log có cảnh báo "Plaintext passwords"); chuyển
# sang bcrypt/nkey là việc sau.

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
  # Template riêng (core/nats/auth.conf.ctmpl) cho dễ đọc; mount vào cùng thư mục với file này
  source      = "/openbao/config/auth.conf.ctmpl"
  destination = "/out/nats/auth.conf"
  perms       = "0444"
}
