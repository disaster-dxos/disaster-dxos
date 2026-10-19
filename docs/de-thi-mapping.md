# Đối chiếu yêu cầu đề thi ↔ thành phần

Trạng thái: ☐ chưa làm · ◐ đang làm · ☑ xong (ghi đường dẫn mã/tài liệu làm bằng chứng)

## A. Yêu cầu bắt buộc của đề
| # | Yêu cầu | Thành phần | Trạng thái | Bằng chứng |
|---|---|---|---|---|
| A1 | Lõi headless Tầng 1, không có UI | Keycloak, APISIX, PostgreSQL+PostGIS, OpenBao chế độ server tắt UI (core); Hasura CE tắt console, Temporal, SeaweedFS, NATS cùng profile `core` (#11). Két sắt bí mật: mọi mật khẩu DB (superuser + role riêng từng dịch vụ), admin Keycloak/Hasura, client secret gateway, khóa S3 lấy từ OpenBao qua bao agent + AppRole chỉ đọc, không nằm trong `.env` (#14, #11) | ◐ | `docker-compose.yml`, `core/openbao/`, `scripts/openbao-init.sh`, `scripts/smoke-openbao.sh`, `scripts/smoke-core.sh`, `docs/architecture.md` mục 8 |
| A2 | Identity / SSO (+MFA) | Keycloak 26.8.1, realm `disaster`, 3 vai trò `dieu-phoi`/`cuu-ho`/`tinh-nguyen`, client gateway/web/dev-cli. MFA: flow `browser-otp-dieu-phoi` bắt OTP với vai trò `dieu-phoi` (#13). Claim `https://hasura.io/jwt/claims` có vai trò mặc định ổn định. Mật khẩu DB, admin và secret client của Keycloak nằm trong OpenBao (#14) | ☑ | `apps/cuu-tro/keycloak/realm.json`, `scripts/smoke-jwt.sh` |
| A3 | API Gateway | APISIX 3.19 standalone (route trong git): `/graphql` → Hasura `/v1/graphql`, `/files/*` → SeaweedFS S3 (URL presigned + JWT, giới hạn 20 MiB), `/workflow/*` (giữ chỗ 503, chờ worker #29), `/api/v1/me`. `openid-connect` kiểm JWT bằng JWKS Keycloak; `/v1/metadata`, `/v2/query`, `/console` bị chặn từ ngoài; Coraza WAF + OWASP CRS chế độ chặn; limit-count theo IP; CORS theo `GW_CORS_ALLOW_ORIGINS` (#12) | ☑ | `core/apisix/`, `docs/architecture.md` mục 3.3, `scripts/smoke-gateway.sh` (401/200/503 từng route, 403 endpoint quản trị, 403 SQLi/XSS, 413, 429, CORS) |
| A4 | Quản trị dữ liệu có cấu trúc | PostgreSQL 17 + PostGIS 3.5; Hasura CE v2.51.0-ce chạy trong `core` bằng role `hasura` riêng (không superuser), console tắt, kiểm lại JWT Keycloak qua JWKS, đọc claim `https://hasura.io/jwt/claims`, chặn tự nâng vai trò (#11). Chưa có schema nghiệp vụ (#25, #26), chưa có route `/graphql` (#12) | ◐ | `docker-compose.yml` (`hasura`, `postgres-roles`), `core/postgres/sync-roles.sh`, `scripts/smoke-core.sh` |
| A5 | Quản trị dữ liệu phi cấu trúc | SeaweedFS 4.48 (S3) chạy trong `core`, bật xác thực S3 bằng khóa lấy từ OpenBao (`secret/core/s3`); smoke tạo bucket, ghi/đọc/xóa object, khóa sai → 403 (#11). Chưa có API tải ảnh (#27), route `/files` (#12), ClamAV | ◐ | `docker-compose.yml` (`seaweedfs`), `core/openbao/agent-seaweedfs.hcl`, `scripts/smoke-core.sh` |
| A6 | Workflow engine | Temporal 1.29.7 chạy trong `core` (CSDL riêng thuộc role `temporal`, namespace `default`), Temporal UI chỉ cho admin trên 127.0.0.1 (#11). Chưa có worker/workflow (#29), route `/workflow` (#12) | ◐ | `docker-compose.yml` (`temporal`, `temporal-ui`), `scripts/smoke-core.sh` |
| A7 | ≥1 ứng dụng Tầng 2 có giao diện (H-P-D-I) | | ☐ | |

## B. 4 nguyên lý kỹ thuật (điểm cộng nguyên gốc)
| # | Nguyên lý | Cách thể hiện | Trạng thái |
|---|---|---|---|
| B1 | Tách dữ liệu nóng / lịch sử (lakehouse) | | ☐ |
| B2 | Hội tụ IT/OT, bản sao số | | ☐ |
| B3 | Phả hệ & chất lượng dữ liệu | | ☐ |
| B4 | Zero-Trust + GitOps | Gateway kiểm JWT + Hasura kiểm lại JWT; kiểm dịch ở biên: Coraza WAF + OWASP CRS chặn SQLi/XSS trong URI, tham số, header và body JSON trước bước kiểm token, rate limit, giới hạn kích thước, endpoint quản trị Hasura không ra ngoài, header `X-Hasura-Admin-Secret` của client bị bỏ (#12); route APISIX khai báo trong git (standalone); bí mật trong OpenBao, mỗi dịch vụ một AppRole chỉ đọc phần của mình, policy nằm trong git (#14) | ◐ |

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
