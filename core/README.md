<!-- SPDX-License-Identifier: Apache-2.0 -->
# core/ — Tầng 1 (lõi headless)

Cấu hình các dịch vụ dùng chung của DX-OS. Mỗi dịch vụ chạy bằng image Docker gốc, khai báo trong `docker-compose.yml` ở gốc repo.

| Thư mục | Dịch vụ |
|---|---|
| `openbao/` | Két sắt bí mật: `openbao.hcl` (server, raft), `agent-*.hcl` (bao agent từng dịch vụ), `policies/` (policy chỉ đọc), `env-from-files.sh`, `dev-auto-unseal.sh`. Khởi tạo: `scripts/openbao-init.sh` |
| `apisix/` | API Gateway: `config.yaml` (chế độ standalone), `apisix.yaml` (route lõi, kiểm JWT) |
| `postgres/` | `init/`: khởi tạo lần đầu (CSDL Keycloak, PostGIS); `sync-roles.sh`: role riêng cho Keycloak, Hasura, Temporal (container `postgres-roles`) |
| `nats/` | NATS JetStream + MQTT |

**Quy tắc:** không đặt vào đây bảng, vai trò, quy trình, dữ liệu mẫu hay giao diện của một đề tài cụ thể. Những thứ đó thuộc `apps/<tên>/`. Xem `docs/architecture.md` mục 7.
