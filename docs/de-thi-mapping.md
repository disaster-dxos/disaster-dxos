# Đối chiếu yêu cầu đề thi ↔ thành phần

Trạng thái: ☐ chưa làm · ◐ đang làm · ☑ xong (ghi đường dẫn mã/tài liệu làm bằng chứng)

## A. Yêu cầu bắt buộc của đề
| # | Yêu cầu | Thành phần | Trạng thái | Bằng chứng |
|---|---|---|---|---|
| A1 | Lõi headless Tầng 1, không có UI | Keycloak, APISIX, PostgreSQL+PostGIS (core); Hasura CE tắt console, Temporal, SeaweedFS, NATS, OpenBao (core-next) | ◐ | `docker-compose.yml`, `docs/architecture.md` |
| A2 | Identity / SSO (+MFA) | Keycloak 26.8.1, realm `disaster`, 3 vai trò `dieu-phoi`/`cuu-ho`/`tinh-nguyen`, client gateway/web/dev-cli. Chưa bật MFA | ◐ | `deploy/keycloak/realm-disaster.json`, `scripts/smoke-jwt.sh` |
| A3 | API Gateway | APISIX 3.19 standalone (route trong git), `openid-connect` kiểm JWT bằng JWKS Keycloak, limit-count. Mới có route mẫu `/api/v1/me`; chưa có Coraza WAF | ◐ | `deploy/apisix/`, `scripts/smoke-jwt.sh` (401 không token / 200 có token) |
| A4 | Quản trị dữ liệu có cấu trúc | PostgreSQL 17 + PostGIS 3.5 chạy; Hasura CE v2.51.0-ce khai báo (core-next) | ◐ | `docker-compose.yml` |
| A5 | Quản trị dữ liệu phi cấu trúc | SeaweedFS 4.48 (S3) khai báo (core-next) | ☐ | |
| A6 | Workflow engine | Temporal 1.29.7 khai báo (core-next) | ☐ | |
| A7 | ≥1 ứng dụng Tầng 2 có giao diện (H-P-D-I) | | ☐ | |

## B. 4 nguyên lý kỹ thuật (điểm cộng nguyên gốc)
| # | Nguyên lý | Cách thể hiện | Trạng thái |
|---|---|---|---|
| B1 | Tách dữ liệu nóng / lịch sử (lakehouse) | | ☐ |
| B2 | Hội tụ IT/OT, bản sao số | | ☐ |
| B3 | Phả hệ & chất lượng dữ liệu | | ☐ |
| B4 | Zero-Trust + GitOps | Gateway kiểm JWT + Hasura kiểm lại JWT; route APISIX khai báo trong git (standalone) | ◐ |

## C. Không gian H-P-D-I trong ứng dụng
| Không gian | Tính năng | Trạng thái |
|---|---|---|
| [H] | | ☐ |
| [P] (có Poka-yoke) | | ☐ |
| [D] | | ☐ |
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
