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
| `web-dieu-phoi.png` | Ảnh chụp web điều phối (#60): bản đồ + danh sách tin kêu cứu thời gian thực qua GraphQL subscription, cụm điểm, tin vừa đến nhấp nháy và nổi lên đầu danh sách; tin mẫu (dữ liệu giả) trong stack thật, đăng nhập bằng tài khoản mẫu (1440×900) | Mô tả PR #60, `apps/cuu-tro/web/README.md` | Đội chụp bằng Chrome headless từ bản build. Bản đồ nền: OpenFreeMap, dữ liệu © những người đóng góp OpenStreetMap (ODbL-1.0), ghi công ở góc ảnh |
| `web-ban-do-chi-tiet.png` | Ảnh chụp (#60): bấm một tin vừa đến → ô chi tiết (mô tả, đội được phân công tự động, SĐT che giữa), bản đồ bay tới điểm (1440×900) | Mô tả PR #60, `apps/cuu-tro/web/README.md` | Như trên |
| `web-mat-ket-noi.png` | Ảnh chụp (#60): Hasura dừng → băng "Mất kết nối tới máy chủ", nút Thử lại, dữ liệu cũ kèm giờ cập nhật cuối (1440×900) | Mô tả PR #60, `apps/cuu-tro/web/README.md` | Như trên |
| `web-phan-cong-dieu-phoi.png` | Ảnh chụp màn phân công (#61), vai điều phối: 4 nhóm Cần xử lý · Chờ phân công · Đang phân công · Đang cứu, đội đang giao, đếm ngược hạn nhận, tin seed và tin mới (1440×900) | Mô tả PR #61, `apps/cuu-tro/web/README.md` | Đội chụp bằng Chrome headless trên stack thật (project tạm, volume trống), tin mẫu là dữ liệu giả tạo qua `POST /workflow/keu-cuu`, đăng nhập bằng tài khoản mẫu; tin "Cần xử lý" là sự kiện thật của workflow (không còn đội sau 3 lần giao) |
| `web-phan-cong-doi-doi.png` | Ảnh chụp (#61): điều phối bấm Đổi đội kèm lý do → thông báo thành công, đội mới + hạn nhận mới, lịch sử ghi lần từ chối do điều phối (1440×900) | Như trên | Như trên |
| `web-phan-cong-cuu-ho.png` | Ảnh chụp (#61), vai cứu hộ trên điện thoại: chi tiết nhiệm vụ, SĐT che giữa, hạn nhận còn lại, nút Nhận nhiệm vụ / Từ chối cố định cuối màn hình (390×844, @2x) | Như trên | Như trên |
| `web-phan-cong-nhan-muon.png` | Ảnh chụp (#61): đội cũ bấm Nhận sau khi điều phối đã đổi đội → API 403, thông báo tiếng Việt (390×844, @2x) | Như trên | Như trên |
| `web-nen-nuxt-ui-ban-do.png` | Ảnh ghép trước/sau (#77): trang bản đồ điều phối trong khung Nuxt UI mới (thanh bên, thanh đầu, font Be Vietnam Pro), thân màn chưa đổi (2 × 1440×900, thu nhỏ 1/1,5) | Mô tả PR #77 | Đội chụp bằng Chrome headless trên `nuxt dev` với gateway giả lập và JWT giả (dữ liệu giả, không chạy stack). Bản đồ nền như trên |
| `web-nen-nuxt-ui-phan-cong.png` | Như trên, màn phân công vai điều phối | Như trên | Như trên |
| `web-nen-nuxt-ui-cuu-ho.png` | Như trên, chi tiết nhiệm vụ vai cứu hộ trên điện thoại (2 × 390×844) | Như trên | Như trên |
| `web-nuxt-ui-ban-do.png` | Ảnh ghép trước/sau (#78): bản đồ điều phối dựng lại bằng Nuxt UI, ngăn chi tiết nổi trên bản đồ, chú thích gọn (2 × 1440×900, thu nhỏ 1/1,5) | Mô tả PR #78, `apps/cuu-tro/web/README.md` | Đội chụp bằng Chrome headless trên `nuxt dev` với gateway giả lập và JWT giả (dữ liệu giả, không chạy stack). Bản đồ nền như trên |
| `web-nuxt-ui-phan-cong.png` | Như trên, kanban phân công vai điều phối | Như trên | Như trên |
| `web-nuxt-ui-toi.png` | Bản đồ và phân công ở chế độ tối (#78, 2 × 1440×900, thu nhỏ) | Như trên | Như trên; bản đồ nền OpenFreeMap kiểu `dark` |
| `web-nuxt-ui-cuu-ho.png` | Ảnh ghép trước/sau (#78): chi tiết nhiệm vụ vai cứu hộ trên điện thoại (2 × 390×844) | Như trên | Như trên |
| `web-nuxt-ui-minh-bach.png` | Trang Minh bạch cứu trợ công khai (#78): trước (chưa có trang), sau ở 1440 và 390 | Như trên | Như trên |
| `web-demo-dieu-phoi.gif` | GIF demo web điều phối (#65, ~13 giây, 960×600): đăng nhập Keycloak → bản đồ tin kêu cứu + trạm đo → popup trạm (mực nước, biểu đồ 24 giờ) → chi tiết tin → màn phân công → chi tiết phân công → trang Minh bạch trình duyệt tự kiểm sổ cái | `README.md` mục "Sản phẩm", `apps/cuu-tro/web/README.md` | Đội chụp bằng Playwright (`scripts/chup-anh/chup.mjs`) trên stack thật (project tạm, volume trống), ghép bằng ffmpeg. Dữ liệu giả: seed + `scripts/chup-anh/du-lieu-demo.sh` (8 tin kêu cứu bịa, SĐT 0900065xxx, trận lũ mẫu giả lập tới giờ 30). Bản đồ nền: OpenFreeMap, dữ liệu © những người đóng góp OpenStreetMap (ODbL-1.0) |
| `web-ban-do-tram-do.webp`, `web-ban-do-tram-do-toi.webp` | Bản đồ điều phối sáng/tối (#62, #65): tin kêu cứu, trạm đo theo cấp báo động, popup trạm Hội An (1440×900) | Như trên | Như trên; chế độ tối: kiểu `dark` của OpenFreeMap |
| `web-phan-cong.webp`, `web-phan-cong-toi.webp` | Màn phân công vai điều phối sáng/tối (#65, 1440×900) | Như trên | Như trên |
| `web-minh-bach.webp`, `web-minh-bach-toi.webp` | Trang Minh bạch công khai sáng/tối (#63, #65): phiếu xuất kho, máy chủ xác minh, trình duyệt tự kiểm 5 bước (1440×900) | Như trên | Như trên |

Chụp lại toàn bộ ảnh `web-demo-*`, `web-ban-do-tram-do*`, `web-phan-cong*.webp`, `web-minh-bach*` (cần stack đang chạy, ffmpeg, ImageMagick):

```bash
make up && make seed && bash scripts/chup-anh/du-lieu-demo.sh
cd scripts/chup-anh && npm ci && npx playwright install chromium && node chup.mjs
```

Lần đầu kịch bản tự cài TOTP cho tài khoản `dieuphoi01` (bí mật lưu ở `.data/chup-anh-totp.txt`, ngoài git); dựng lại stack thì xóa tệp đó.

Mọi tệp trong thư mục này do đội DTU_DZ_1 tạo và cấp phép cùng repo: [Apache-2.0](../../LICENSE), trừ phần bản đồ nền trong các ảnh chụp `web-*` (dữ liệu OpenStreetMap, ODbL-1.0). Ảnh `.webp` là tranh minh họa, không phải ảnh chụp sự kiện hay người thật.

**Biểu tượng trong `kien-truc-tong-quan.webp` là hình minh họa do công cụ AI vẽ lại, không phải logo chính thức** của các dự án. Tên và nhãn hiệu (Apache APISIX, Keycloak, Hasura, SeaweedFS, Temporal, Tessera, OpenBao, NATS, PostgreSQL, PostGIS) thuộc dự án hoặc tổ chức tương ứng; dùng ở đây chỉ để chỉ thành phần mà hệ thống sử dụng. Ảnh này là tổng quan giản lược; kiến trúc chính xác xem `kien-truc.svg` và [`docs/architecture.md`](../architecture.md).

Sửa sơ đồ: sửa trực tiếp tệp `.svg` (văn bản, có `viewBox`, font hệ thống), xem trước bằng trình duyệt. Hệ thống đổi (thêm dịch vụ, đổi luồng) thì cập nhật sơ đồ trong cùng PR.

## `logo/` — Logo và bộ nhận diện

Logo do đội tạo bằng công cụ AI (ChatGPT) theo prompt của đội, đội và người hướng dẫn đã duyệt (22/10/2026). Logo ngang (biểu tượng + chữ tên + khẩu hiệu) do ChatGPT vẽ trọn; các cỡ biểu tượng, favicon và ảnh xem trước được cắt, thu nhỏ và ghép từ đó bằng ImageMagick. Biểu tượng: khiên, mái nhà, sóng tín hiệu, sóng lũ, phao cứu sinh. Màu: navy `#12355B` (chữ tên, viền), cam cứu hộ `#F07B1D`, xanh nước `#1FA2C9`.

| Tệp | Nội dung | Dùng ở |
|---|---|---|
| `logo/mark.png` | Biểu tượng gốc, nền trong suốt (1024×1024) | Nguồn để xuất cỡ khác |
| `logo/mark-512.png` | Biểu tượng 512×512 | Ảnh đại diện org GitHub |
| `logo/mark-180.png` | Biểu tượng 180×180 | `apple-touch-icon` của web |
| `logo/mark-64.png`, `logo/mark-32.png` | Biểu tượng 64×64 và 32×32 | Favicon PNG của web |
| `logo/favicon.ico` | Favicon nhiều cỡ | Web điều phối Nuxt (tuần 3) |
| `logo/logo-ngang.png` | Logo ngang, nền trong suốt (1836×610) | Đầu `README.md` ở chế độ sáng, slide, chân tài liệu |
| `logo/logo-ngang-nen-trang.png` | Logo ngang trên nền trắng (1856×630) | Đầu `README.md` ở chế độ tối (chữ navy khó đọc trên nền tối), Word, slide không hỗ trợ nền trong suốt |
| `logo/xem-truoc.png` | Ảnh xem trước 1280×640 | Social preview của repo GitHub (Settings → Social preview, tải lên bằng tay) |

Quy tắc dùng: không đổi màu, kéo méo, thêm bóng hoặc gradient; logo ngang rộng ít nhất 240 px, biểu tượng ít nhất 32 px; trên nền tối dùng bản nền trắng hoặc đặt biểu tượng trong ô trắng.
