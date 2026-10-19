<!-- SPDX-License-Identifier: Apache-2.0 -->
# apps/cuu-tro — Ứng phó thiên tai & cứu trợ cộng đồng

Ứng dụng Tầng 2 cho chính quyền xã (điều phối), đội cứu hộ, tình nguyện viên và người dân cần cứu.

| Thư mục | Nội dung | Trạng thái |
|---|---|---|
| `keycloak/realm.json` | Realm `disaster`: vai trò `dieu-phoi`, `cuu-ho`, `tinh-nguyen`; client `dxos-gateway`, `dxos-web`, `dxos-dev-cli` (chỉ dev); 3 người dùng mẫu, mật khẩu lấy từ `.env` | Có |
| `db/migrations/` | Bảng `incidents`, `rescue_teams`, `shelters`, `supplies`, `sensors` (PostGIS) | Tuần 2 |
| `workflows/` | Kêu cứu: tiếp nhận → phân công → xác nhận → đóng | Tuần 3 |
| `web/` | Web điều phối Nuxt 3 + MapLibre | Tuần 3 |
| `mobile/` | App hiện trường Flutter | Tuần 5 |
