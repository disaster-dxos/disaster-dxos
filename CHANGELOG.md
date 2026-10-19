# Changelog

Định dạng theo [Keep a Changelog](https://keepachangelog.com/vi/1.1.0/), phiên bản theo [SemVer](https://semver.org/lang/vi/).

## [Unreleased]
### Added
- Khung dự án: LICENSE (Apache-2.0), NOTICE, CONTRIBUTING, CODE_OF_CONDUCT, CI kiểm tra giấy phép, mẫu issue.
- `docs/architecture.md`: sơ đồ Mermaid Tầng 1/Tầng 2, ánh xạ 4 dịch vụ bắt buộc, luồng xác thực JWT, chia profile compose, so sánh Tessera/Trillian.
- `docker-compose.yml` profile `core` (PostgreSQL 17 + PostGIS 3.5, Keycloak 26.8.1, APISIX 3.19 standalone) có healthcheck; profile `core-next` khai báo Hasura CE, SeaweedFS, Temporal, NATS (JetStream + MQTT), OpenBao.
- Realm Keycloak `disaster` (3 vai trò `dieu-phoi`, `cuu-ho`, `tinh-nguyen`; client `dxos-gateway`, `dxos-web`, `dxos-dev-cli`) và route mẫu APISIX `/api/v1/me` kiểm JWT.
- `scripts/smoke-jwt.sh`, `make smoke`, `make up-next`.
- Mẫu PR `.github/PULL_REQUEST_TEMPLATE.md`; CONTRIBUTING mô tả quy trình issue → nhánh → PR → duyệt, đặt tên nhánh, Conventional Commits (#1).
- `DEPENDENCIES.md`: phiên bản, giấy phép, nguồn gốc, cách dùng của mọi image và thư viện; danh sách thành phần không dùng kèm lý do (#4).

### Changed
- Áp D-004: loại immudb (BSL 1.1) → transparency log (đề xuất Tessera, chờ đội chốt); chốt Scorpio làm broker NGSI-LD; Hasura bắt buộc tag `-ce`; Centrifugo OSS; Qwen2.5 chỉ 7B/14B. NOTICE chuyển trạng thái "Đã xác minh 17/10/2026 (D-004)".
- `make check` kiểm mọi profile compose, dùng `.env.example` khi chưa có `.env`; kiểm SPDX mở rộng sang `*.yml`, `*.yaml`, `*.conf`, `Makefile`, `.env.example`.
- Script SPDX quét thêm `.vue`, `.dart`, `.toml`, `.cjs`, `Dockerfile*` và `Makefile`/`.env.example` ở mọi thư mục; danh sách loại file dùng chung trong `scripts/spdx-files.sh`; giữ nguyên shebang và chỉ thị `# syntax=` của Dockerfile khi chèn header (#2).
- Tách `core/` (Tầng 1, không chứa nghiệp vụ) và `apps/cuu-tro/` (Tầng 2): `deploy/apisix`, `deploy/nats`, `deploy/postgres` → `core/`; realm Keycloak → `apps/cuu-tro/keycloak/realm.json`; chọn ứng dụng bằng biến `DXOS_APP`; `docs/architecture.md` thêm mục 7 giải thích vì sao lõi độc lập với nghiệp vụ (#3).
