# Đối chiếu yêu cầu đề thi ↔ thành phần

Trạng thái: ☐ chưa làm · ◐ đang làm · ☑ xong (ghi đường dẫn mã/tài liệu làm bằng chứng)

## A. Yêu cầu bắt buộc của đề
| # | Yêu cầu | Thành phần | Trạng thái | Bằng chứng |
|---|---|---|---|---|
| A1 | Lõi headless Tầng 1, không có UI | Keycloak, APISIX, PostgreSQL+PostGIS, OpenBao chế độ server tắt UI (core); Hasura CE tắt console, Temporal, SeaweedFS, NATS cùng profile `core` (#11); NATS JetStream + MQTT bắt buộc xác thực, user/mật khẩu từ OpenBao, lõi không biết topic nghiệp vụ (#30). Két sắt bí mật: mọi mật khẩu DB (superuser + role riêng từng dịch vụ), admin Keycloak/Hasura, client secret gateway, khóa S3 lấy từ OpenBao qua bao agent + AppRole chỉ đọc, không nằm trong `.env` (#14, #11) | ◐ | `docker-compose.yml`, `core/openbao/`, `scripts/openbao-init.sh`, `scripts/smoke-openbao.sh`, `scripts/smoke-core.sh`, `docs/architecture.md` mục 8 |
| A2 | Identity / SSO (+MFA) | Keycloak 26.8.1, realm `disaster`, 3 vai trò `dieu-phoi`/`cuu-ho`/`tinh-nguyen`, client gateway/web/dev-cli. MFA: flow `browser-otp-dieu-phoi` bắt OTP với vai trò `dieu-phoi` (#13). Claim `https://hasura.io/jwt/claims` có vai trò mặc định ổn định. Mật khẩu DB, admin và secret client của Keycloak nằm trong OpenBao (#14) | ☑ | `apps/cuu-tro/keycloak/realm.json`, `scripts/smoke-jwt.sh` |
| A3 | API Gateway | APISIX 3.19 standalone (route trong git): `/graphql` → Hasura `/v1/graphql`, `/files/*` → SeaweedFS S3 chỉ GET/HEAD (URL presigned + JWT, #27), `/workflow/tai-len/*` → API ứng dụng nhận tệp nhị phân (giới hạn `GW_UPLOAD_MAX_BODY_BYTES`, #27), `/workflow/*` → API workflow của ứng dụng (`<DXOS_APP>-api:8000`, biến `GW_WORKFLOW_UPSTREAM_*`, #29), `/api/v1/me`. `openid-connect` kiểm JWT bằng JWKS Keycloak; `/v1/metadata`, `/v2/query`, `/console` bị chặn từ ngoài; Coraza WAF + OWASP CRS chế độ chặn; limit-count theo IP; CORS theo `GW_CORS_ALLOW_ORIGINS` (#12) | ☑ | `core/apisix/`, `docs/architecture.md` mục 3.3, `scripts/smoke-gateway.sh` (401/200 từng route, 403 endpoint quản trị, 403 SQLi/XSS, 413, 429, CORS) |
| A4 | Quản trị dữ liệu có cấu trúc | PostgreSQL 17 + PostGIS 3.5; Hasura CE v2.51.0-ce chạy trong `core` bằng role `hasura` riêng (không superuser), console tắt, kiểm lại JWT Keycloak qua JWKS, đọc claim `https://hasura.io/jwt/claims`, chặn tự nâng vai trò (#11); route `/graphql` qua APISIX (#12). Cơ chế migration chung của lõi: container `migrate` áp SQL của `apps/<DXOS_APP>/db/` vào schema riêng, role chủ `NOLOGIN`, Hasura chỉ có DML, lịch sử + checksum (#25). Ứng dụng cứu trợ: schema `cuu_tro` 5 bảng PostGIS + phiếu nhập/xuất (#25). Metadata Hasura của ứng dụng trong git (`apps/<DXOS_APP>/hasura/metadata/`, image `-ce.cli-migrations-v3` tự áp khi khởi động, lệch DB thì dừng): track 7 bảng (không lộ bảng cấu hình), quan hệ, quyền theo 3 vai trò JWT: column-level (`tinh-nguyen` không thấy SĐT người báo), row-level theo session variable (`cuu-ho` chỉ thấy tin của đội mình qua `team_members`), không ai có quyền xóa tin, không quyền cho `anonymous`; truy vấn vị trí `_st_d_within` (#26) | ☑ | `docker-compose.yml` (`hasura`, `postgres-roles`, `migrate`), `core/postgres/sync-roles.sh`, `core/postgres/migrate.sh`, `apps/cuu-tro/db/`, `apps/cuu-tro/hasura/metadata/`, `docs/architecture.md` mục 3.4, 7.2, `scripts/smoke-core.sh`, `scripts/smoke-hasura.sh` |
| A5 | Quản trị dữ liệu phi cấu trúc | SeaweedFS 4.48 (S3) chạy trong `core`, bật xác thực S3 bằng khóa lấy từ OpenBao (`secret/core/s3`); smoke tạo bucket, ghi/đọc/xóa object, khóa sai → 403 (#11). Ảnh hiện trường (#27): bucket riêng tư do ứng dụng khai báo (`apps/cuu-tro/s3/buckets.conf`, container `s3-buckets` của lõi tạo); định danh S3 riêng của ứng dụng (`secret/app/cuu-tro/s3`) chỉ dùng bucket `cuu-tro-*`, không Admin; tải lên qua API `/workflow/tai-len/su-co/{id}/anh` (kiểm magic bytes JPEG/PNG/WebP, kích thước, SHA-256, quyền theo vai trò khớp Hasura), siêu dữ liệu bảng `incident_media`; xem bằng link presigned GET ngắn hạn qua `/files/*` (chỉ GET/HEAD) kèm JWT. Chưa có: ClamAV (cột `scan_status` chừa chỗ) | ◐ | `docker-compose.yml` (`seaweedfs`, `s3-buckets`), `core/seaweedfs/create-buckets.sh`, `core/openbao/agent-seaweedfs.hcl`, `apps/cuu-tro/workflow/cuu_tro_workflow/anh.py`, `s3.py`, `apps/cuu-tro/db/migrations/0005_anh_hien_truong.sql`, `scripts/smoke-core.sh`, `scripts/smoke-anh.sh`, `docs/architecture.md` mục 7.5 |
| A6 | Workflow engine | Temporal 1.29.7 chạy trong `core` (CSDL riêng thuộc role `temporal`, namespace `default`), Temporal UI chỉ cho admin trên 127.0.0.1 (#11). Worker Python (`temporalio` 1.34.0) của ứng dụng cứu trợ: workflow `PhanCongCuuHo` (tìm đội sẵn sàng gần nhất bằng PostGIS → gán đội → chờ signal "đã cứu" có hạn → đóng tin) và `Hello`; API FastAPI khởi chạy/signal/query qua APISIX `/workflow/*` (JWT + WAF), chỉ `dieu-phoi` khởi chạy phân công, `cuu-ho` chỉ xác nhận tin của đội mình (hỏi Hasura bằng JWT người dùng); worker ghi CSDL bằng role dịch vụ `cuu_tro_app` quyền theo cột, mật khẩu từ OpenBao qua bao agent; lõi nạp dịch vụ ứng dụng bằng `include apps/${DXOS_APP}/compose.yaml` (#29) | ☑ | `apps/cuu-tro/workflow/`, `apps/cuu-tro/compose.yaml`, `apps/cuu-tro/db/migrations/0003_quyen_workflow.sql`, `core/apisix/apisix.yaml` (route `workflow`), `docs/architecture.md` mục 7.3, `apps/cuu-tro/README.md` mục "Workflow", 36 test pytest (job CI `pytest`), `scripts/smoke-workflow.sh` (20 ca qua gateway: 401/403, gán đội gần nhất trong DB, xác nhận → đóng, COMPLETED trong Temporal CLI) |
| A7 | ≥1 ứng dụng Tầng 2 có giao diện (H-P-D-I) | | ☐ | |

## B. 4 nguyên lý kỹ thuật (điểm cộng nguyên gốc)
| # | Nguyên lý | Cách thể hiện | Trạng thái |
|---|---|---|---|
| B1 | Tách dữ liệu nóng / lịch sử (lakehouse) | | ☐ |
| B2 | Hội tụ IT/OT, bản sao số | Thiết bị (bộ giả lập trạm đo mực nước) gửi MQTT vào NATS của lõi có xác thực (user thiết bị chỉ gửi được vào `<DXOS_APP>.>`, chỉ qua MQTT) → JetStream lưu bền → consumer của ứng dụng ghi chuỗi đo vào PostgreSQL (`sensor_readings`, `sensors.last_*`) cùng nơi với dữ liệu nghiệp vụ, đọc qua `/graphql`; vượt ngưỡng → sự kiện cảnh báo trên NATS cho agent/Temporal (#30). Còn: bản sao số NGSI-LD trên Scorpio (tuần 4), bản đồ thời gian thực. Bằng chứng: `core/nats/`, `apps/cuu-tro/nats/streams.json`, `apps/cuu-tro/workflow/cuu_tro_workflow/cam_bien*.py`, `gia_lap.py`, `docs/architecture.md` mục 7.4, `scripts/smoke-cam-bien.sh` | ◐ |
| B3 | Phả hệ & chất lượng dữ liệu | | ☐ |
| B4 | Zero-Trust + GitOps | Gateway kiểm JWT + Hasura kiểm lại JWT; kiểm dịch ở biên: Coraza WAF + OWASP CRS chặn SQLi/XSS trong URI, tham số, header và body JSON trước bước kiểm token, rate limit, giới hạn kích thước, endpoint quản trị Hasura không ra ngoài, header `X-Hasura-Admin-Secret` của client bị bỏ (#12); route APISIX khai báo trong git (standalone); bí mật trong OpenBao, mỗi dịch vụ một AppRole chỉ đọc phần của mình, policy nằm trong git (#14) | ◐ |

## C. Không gian H-P-D-I trong ứng dụng
| Không gian | Tính năng | Trạng thái |
|---|---|---|
| [H] | | ☐ |
| [P] (có Poka-yoke) | Poka-yoke ở tầng dữ liệu (#25): tin kêu cứu bắt buộc tọa độ (`NOT NULL`); chặn tin trùng cùng SĐT trong bán kính 200 m, 6 giờ, khi tin cũ còn mở (trigger + khóa advisory, lỗi `unique_violation` kèm id tin cũ); đã phân công phải có đội; điểm trú ẩn không vượt sức chứa; xuất kho không vượt tồn, phiếu nhập/xuất không sửa/xóa được. Kiểm bằng `make test-db` (26 ca). Quy trình tiếp nhận → phân công → xác nhận → đóng chạy bằng Temporal (#29): chỉ phân công tin `tiep_nhan`, luồng trạng thái hợp lệ kiểm trong worker (`logic.CHUYEN_TRANG_THAI`), một tin chỉ một luồng phân công đang chạy (409), hai luồng giành một đội thì luồng thua chọn đội khác, quá hạn xác nhận được ghi nhận. Chưa có giao diện (tuần 3) | ◐ |
| [D] | Dữ liệu cảm biến thời gian thực (#30): bộ giả lập trạm đo MQTT → NATS JetStream → `sensor_readings` + `sensors.last_*`, kiểm payload (đơn vị, múi giờ, khoảng giá trị, trạm có thật), phân mức `binh_thuong`/`canh_bao`/`nguy_hiem` theo ngưỡng do điều phối chỉnh, sự kiện cảnh báo khi mức tăng; 3 vai trò đọc chuỗi đo qua `/graphql`. Ảnh hiện trường gắn tin kêu cứu (#27): tải qua API (magic bytes, kích thước), xem bằng link presigned ngắn hạn theo quyền vai trò. Chưa có: NGSI-LD/Scorpio, bản đồ realtime, transparency log, Parquet | ◐ |
| [I] (có Human-in-the-loop) | | ☐ |

## D. PoF – 50 điểm (rà trước khi nộp)
| # | Tiêu chí | Kiểm tra | Trạng thái |
|---|---|---|---|
| 1 | Kho mã công khai, có web viewer, dùng thật | | ☐ |
| 2 | LICENSE toàn văn + SPDX mọi file + tương thích giấy phép | `make check` (đã mở rộng sang yml/yaml/conf/Makefile); NOTICE đã xác minh D-004 | ◐ |
| 3 | Release đánh phiên bản, `.tar.gz`, trước hạn | | ☐ |
| 4 | Build từ mã nguồn, cấu hình qua .env, chạy ngoài thư mục mã | `.env.example`, image ghim phiên bản | ◐ |
| 5 | Không vendor/sửa thư viện, khai báo phụ thuộc | | ☐ |
| 6 | README, CHANGELOG, bug tracker | | ☐ |

## E. Cộng đồng & bền vững (tiêu chí 10, 11)
| Việc | Trạng thái |
|---|---|
| README song ngữ, CONTRIBUTING, CODE_OF_CONDUCT | ◐ |
| Hướng dẫn viết module cắm–rút + module mẫu | ☐ |
| Demo công khai trên Internet, người dùng thật thử | ☐ |
| Kênh trao đổi (Discussions/Telegram), bài giới thiệu | ☐ |
