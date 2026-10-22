<!-- SPDX-License-Identifier: Apache-2.0 -->
# docs/images — Ảnh và sơ đồ của tài liệu

| Tệp | Nội dung | Nguồn |
|---|---|---|
| `banner.webp` | Ảnh bìa: đội cứu hộ trên xuồng, trạm đo mực nước, điểm điều phối trong vùng lũ (2000×667) | Đội DTU_DZ_1 tạo bằng công cụ AI tạo ảnh, không có chữ trong ảnh |
| `minh-bach-cuu-tro.webp` | Minh họa hàng cứu trợ được ghi thành chuỗi khối kiểm chứng được, người dân đứng xem (1672×941) | Đội DTU_DZ_1 tạo bằng công cụ AI tạo ảnh, không có chữ trong ảnh |
| `kien-truc.svg` | Sơ đồ kiến trúc: Tầng 1 `core/`, Tầng 2 `apps/cuu-tro`, 4 dịch vụ bắt buộc ①–④, luồng JWT, cảm biến, sổ cái, bí mật | Đội vẽ tay bằng SVG thuần theo `docker-compose.yml`, `core/`, `apps/cuu-tro/`, `docs/architecture.md` |
| `luong-cuu-tro.svg` | Luồng kêu cứu → phân công → xác nhận; luồng phiếu kho → sổ cái → kiểm chứng công khai | Đội vẽ tay bằng SVG thuần theo `apps/cuu-tro/README.md` |

Mọi tệp trong thư mục này cấp phép cùng repo: [Apache-2.0](../../LICENSE). Ảnh là tranh minh họa, không phải ảnh chụp sự kiện hay người thật.

Sửa sơ đồ: sửa trực tiếp tệp `.svg` (văn bản, có `viewBox`, font hệ thống), xem trước bằng trình duyệt. Hệ thống đổi (thêm dịch vụ, đổi luồng) thì cập nhật sơ đồ trong cùng PR.
