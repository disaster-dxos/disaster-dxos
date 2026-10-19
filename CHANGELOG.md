# Changelog

Định dạng theo [Keep a Changelog](https://keepachangelog.com/vi/1.1.0/), phiên bản theo [SemVer](https://semver.org/lang/vi/).

## [Unreleased]
### Added
- Keycloak: claim `https://hasura.io/jwt/claims` (`x-hasura-allowed-roles`, `x-hasura-default-role` từ thuộc tính user `hasura_default_role`, `x-hasura-user-id`) bằng mapper có sẵn trên client `dxos-web`, `dxos-dev-cli`; thuộc tính khai báo trong user profile của realm (#13).
- Keycloak: flow trình duyệt `browser-otp-dieu-phoi` bắt cài/nhập OTP với vai trò `dieu-phoi`; `scripts/smoke-jwt.sh` kiểm claim Hasura của 3 user mẫu và luồng OTP qua đăng nhập web (#13).
- CI thêm job `shellcheck`, `yamllint` (cấu hình `.yamllint.yml`) và `pytest` (tự bỏ qua khi chưa có mã Python); `scripts/lint.sh`, `make lint`; ghim phiên bản action (#31).

### Changed
- Áp D-007: chốt Tessera (driver POSIX) cho sổ cái minh bạch, Trillian là dự phòng; `docs/architecture.md` thêm mục `core/ledger` (API, không đưa dữ liệu cá nhân lên sổ cái, khóa ký trong OpenBao, trang "Minh bạch cứu trợ"); cập nhật `NOTICE`, `DEPENDENCIES.md`; script SPDX quét thêm `*.go` và `go.mod` (#34).

### Fixed
- Sửa cảnh báo lint trong mã cũ: chú thích bỏ qua SC2094 (dương tính giả) ở `scripts/spdx-files.sh`, cho phép dòng `#END` bắt buộc của APISIX trong `core/apisix/apisix.yaml` (#31).

## [0.0.1] - 2026-10-19
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
- `docs/PLAN.md` theo lộ trình mới: VPS + tên miền tuần 4, tuần UX tuần 6, 2 lần tập trình bày, công bố bộ mô phỏng cảm biến và mô hình NGSI-LD; gán vai V1/V2/V3 cho từng việc (#5).

[Unreleased]: https://github.com/disaster-dxos/disaster-dxos/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/disaster-dxos/disaster-dxos/releases/tag/v0.0.1
