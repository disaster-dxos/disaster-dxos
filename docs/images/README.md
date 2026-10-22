<!-- SPDX-License-Identifier: Apache-2.0 -->
# docs/images — Ảnh và sơ đồ của tài liệu

| Tệp | Nội dung | Dùng ở | Nguồn |
|---|---|---|---|
| `banner.webp` | Ảnh bìa có tiêu đề "DTU_DZ_1 · OLP PMNM 2026 · DISASTER DX-OS": đội cứu hộ trên xuồng, trạm đo mực nước, điểm điều phối trong vùng lũ (2000×667) | `README.md` | Đội tạo bằng công cụ AI tạo ảnh |
| `minh-bach-cuu-tro.webp` | Minh họa hàng cứu trợ được ghi thành chuỗi khối kiểm chứng được, người dân đứng xem (1672×941) | `README.md` | Đội tạo bằng công cụ AI tạo ảnh |
| `vong-chuc-nang.webp` | Vòng tròn 6 chức năng, nhãn tiếng Việt: kêu cứu, bản đồ thời gian thực, phân công cứu hộ, cảnh báo mực nước, sổ cái minh bạch, AI bóc tách tin kêu cứu (1672×941) | `README.md` | Đội tạo bằng công cụ AI tạo ảnh |
| `kien-truc-tong-quan.webp` | Kiến trúc tổng quan dạng biểu tượng, nhãn tiếng Anh: người dùng → APISIX + WAF / Keycloak → Hasura, SeaweedFS, Temporal, sổ cái → PostgreSQL + PostGIS; OpenBao cấp bí mật; trạm đo → MQTT → NATS → cảnh báo (1672×941) | `README.md` | Đội tạo bằng công cụ AI tạo ảnh |
| `luong-keu-cuu.webp` | Luồng kêu cứu 5 bước: báo tin → kiểm tra → điều phối → đội gần nhất → đã cứu (1672×941) | `README.md` | Đội tạo bằng công cụ AI tạo ảnh |
| `luong-minh-bach.webp` | Luồng minh bạch 4 bước: phiếu cứu trợ → băm → sổ cái công khai → ai cũng kiểm chứng được (1672×941) | `README.md` | Đội tạo bằng công cụ AI tạo ảnh |
| `kien-truc.svg` | Sơ đồ kiến trúc chi tiết: Tầng 1 `core/`, Tầng 2 `apps/cuu-tro`, 4 dịch vụ bắt buộc ①–④, luồng JWT, cảm biến, sổ cái, bí mật | `docs/architecture.md` mục 1 | Đội vẽ tay bằng SVG thuần theo `docker-compose.yml`, `core/`, `apps/cuu-tro/` |
| `luong-cuu-tro.svg` | Luồng kêu cứu → phân công → xác nhận; luồng phiếu kho → sổ cái → kiểm chứng công khai, chi tiết theo API | `docs/architecture.md` mục 6 | Đội vẽ tay bằng SVG thuần theo `apps/cuu-tro/README.md` |

Mọi tệp trong thư mục này do đội DTU_DZ_1 tạo và cấp phép cùng repo: [Apache-2.0](../../LICENSE). Ảnh `.webp` là tranh minh họa, không phải ảnh chụp sự kiện hay người thật.

**Biểu tượng trong `kien-truc-tong-quan.webp` là hình minh họa do công cụ AI vẽ lại, không phải logo chính thức** của các dự án. Tên và nhãn hiệu (Apache APISIX, Keycloak, Hasura, SeaweedFS, Temporal, Tessera, OpenBao, NATS, PostgreSQL, PostGIS) thuộc dự án hoặc tổ chức tương ứng; dùng ở đây chỉ để chỉ thành phần mà hệ thống sử dụng. Ảnh này là tổng quan giản lược; kiến trúc chính xác xem `kien-truc.svg` và [`docs/architecture.md`](../architecture.md).

Sửa sơ đồ: sửa trực tiếp tệp `.svg` (văn bản, có `viewBox`, font hệ thống), xem trước bằng trình duyệt. Hệ thống đổi (thêm dịch vụ, đổi luồng) thì cập nhật sơ đồ trong cùng PR.
