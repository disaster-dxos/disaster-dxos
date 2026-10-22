# SPDX-License-Identifier: Apache-2.0
# OpenBao chế độ server (không -dev): dữ liệu bền trên volume, khởi động ở trạng thái sealed.
# Khởi tạo + mở khóa: make bao-init (scripts/openbao-init.sh). Kiến trúc: docs/architecture.md mục 8.

# Tầng 1 headless: tắt giao diện web, chỉ dùng API/CLI
ui = false

# Raft tích hợp, một nút. /openbao/file có sẵn trong image, thuộc user openbao.
storage "raft" {
  path    = "/openbao/file"
  node_id = "openbao-1"
}

# Chỉ lắng nghe trong mạng Docker và 127.0.0.1 của máy host (xem docker-compose.yml).
# TLS tắt cho laptop dev; bật khi lên VPS (tuần 4).
listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true
}

api_addr     = "http://openbao:8200"
cluster_addr = "http://openbao:8201"

# Raft khuyên tắt mlock (mlock không áp cho dữ liệu raft đã mmap)
disable_mlock = true
log_level     = "info"
