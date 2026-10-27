<!-- SPDX-License-Identifier: Apache-2.0 -->
# Kế hoạch Team 1 – Disaster DX-OS

Hạn nộp: **17:00 Chủ Nhật 06/12/2026**. Chấm kho mã 07–09/12, chung kết 10/12.

Mỗi dòng là một việc, sẽ thành **một issue** trên GitHub (nhãn `tuan-N` + vai), làm theo quy trình issue → nhánh → PR trong `CONTRIBUTING.md`. Đánh dấu [x] khi PR đã merge.

| Vai | Phạm vi | Nhãn |
|---|---|---|
| **V1** | Lõi headless Tầng 1, DevOps, bảo mật, CI, release | `vai-1-core` |
| **V2** | Dữ liệu, NGSI-LD, cảm biến, WebGIS, dashboard, sổ cái | `vai-2` |
| **V3** | App web/mobile, UX, AI bóc tách tin kêu cứu | `vai-3` |

## Tuần 1 · 15–21/10 · Nền móng → v0.0.1
- [x] [V1] Xác minh giấy phép stack (D-004): chọn Scorpio, loại immudb, Hasura chỉ tag `-ce` → `NOTICE`
- [x] [V1] `docs/architecture.md`: sơ đồ Tầng 1/Tầng 2 (Mermaid), luồng JWT, luồng kêu cứu và cảm biến
- [x] [V1] `docker-compose.yml` profile `core`: PostgreSQL+PostGIS, Keycloak (realm 3 vai trò), APISIX standalone + route JWT mẫu; `.env.example`
- [x] [V1] Repo GitHub công khai, bật Issues, nhãn, bảo vệ `main`/`develop`
- [x] [V1] Mẫu PR + CONTRIBUTING mô tả quy trình issue → nhánh → PR (#1, PR #6; quy trình phát hành thêm ở #109)
- [x] [V1] Script SPDX quét `.vue`, `.dart`, `Dockerfile*`, `.toml` (#2, PR #7; `.go` ở #34, mã native app ở #106)
- [x] [V2] `DEPENDENCIES.md`: phiên bản, giấy phép, nguồn gốc từng thành phần (#4, PR #9)
- [x] [V1] Gán vai cho từng dòng kế hoạch, tạo issue tuần 2 (#5, PR #10)
- [x] [V1] Release v0.0.1 (`.tar.gz`) (PR #23, #24; 19/10/2026)

## Tuần 2 · 22–28/10 · Lõi headless → v0.1.0
- [x] [V1] Tách `core/` (Tầng 1, không chứa nghiệp vụ) và `apps/` (nghiệp vụ thiên tai); cập nhật `docs/architecture.md`
- [x] [V1] Gộp Hasura CE, SeaweedFS, Temporal, NATS từ `core-next` vào `core` (OpenBao đã vào `core` ở #14), chạy được trên laptop 16 GB; chuyển `POSTGRES_PASSWORD`, secret Hasura, khóa S3 sang OpenBao (#11; RAM đo ~1,4–1,9 GB)
- [x] [V1] APISIX: route `/graphql`, `/files`, `/workflow` kiểm JWT Keycloak; bật Coraza WAF (#12; `/workflow` giữ chỗ 503 tới #29, cấp URL presigned S3 ở #27)
- [x] [V1] Keycloak: claim vai trò mặc định ổn định cho Hasura (sửa `realm_access.roles[0]`); bật OTP cho `dieu-phoi`
- [x] [V1] OpenBao giữ bí mật DB, client Keycloak, khóa S3 (bỏ chế độ dev) (#14: OpenBao server + AppRole; #11: superuser PostgreSQL, role Hasura/Temporal, admin secret Hasura, khóa S3)
- [x] [V2] Schema PostGIS trong `apps/`: incidents, rescue_teams, shelters, supplies, sensors (migration) (#25; schema `cuu_tro`, chặn tin trùng SĐT trong 200 m bằng trigger, `make seed`, `make test-db`)
- [x] [V2] Hasura trên schema `apps/`, phân quyền theo vai trò trong JWT (#26; metadata `apps/cuu-tro/hasura/metadata/` tự áp khi khởi động, `cuu-ho` lọc theo `team_members`, `tinh-nguyen` không thấy SĐT, `scripts/smoke-hasura.sh` 33 ca qua gateway)
- [x] [V2] SeaweedFS S3 + API tải ảnh hiện trường qua gateway (#27; bucket `cuu-tro-media` do ứng dụng khai báo, khóa S3 riêng của ứng dụng chỉ bucket `cuu-tro-*`, tải lên qua `/workflow/tai-len/*` kiểm magic bytes + kích thước, xem bằng link presigned ngắn hạn qua `/files/*` chỉ đọc, bảng `incident_media`, `scripts/smoke-anh.sh`; ClamAV để sau)
- [x] [V1] Chốt transparency log: Tessera, driver POSIX (D-007); tài liệu + SPDX cho Go (#34)
- [x] [V2] Dựng bản chạy thử `core/ledger` (Go + Tessera): ghi 1 phiếu, lấy proof, xác minh (#28; dịch vụ `ledger` trong `core`, khóa ký Ed25519 trong OpenBao, ghi chỉ trong mạng nội bộ bằng token dịch vụ, `/ledger/*` đọc công khai; phiếu nhập/xuất qua `POST /workflow/kho/phieu` → sổ cái → trang công khai `/workflow/minh-bach/phieu/{mã}`; CLI `ledger-verify` tự kiểm từ tile; `scripts/smoke-ledger.sh`; CI `go-test`, `go-licenses`)
- [x] [V3] Temporal worker Python "hello" gọi được qua gateway (#29; mở rộng thành khung `PhanCongCuuHo` + API `/workflow/*`, role DB `cuu_tro_app`, `scripts/smoke-workflow.sh` 20 ca)
- [x] [V3] NATS JetStream bật MQTT, gửi thử bản tin cảm biến (#30; MQTT + NATS bắt buộc xác thực từ OpenBao, bộ giả lập `gia_lap`, stream `CUU_TRO_CAM_BIEN` → `sensor_readings`, cảnh báo vượt ngưỡng lên `cuu-tro.canh-bao.cam-bien.*`, `scripts/smoke-cam-bien.sh`)
- [x] [V1] CI: lint/test cho từng thành phần (shellcheck, yamllint, pytest khi có mã Python)
- [x] [V1] README song ngữ: hướng dẫn chạy từ máy sạch · Release v0.1.0 (#32, PR #50, #52, #54, #55, #56; 22/10/2026)

## Tuần 3 · 29/10–04/11 · Luồng nghiệp vụ chính → v0.2.0 (phát hành 23/10/2026)
- [x] [V2] API kêu cứu + Poka-yoke (bắt buộc tọa độ, chặn trùng SĐT trong bán kính 200 m) (#66, PR #75)
- [x] [V1] Temporal workflow: tiếp nhận → phân công đội gần nhất → xác nhận đã cứu → đóng (khung #29; #67: tự khởi chạy khi có tin mới qua outbox PostgreSQL, quá hạn nhận / từ chối → phân công lại, hết lần → báo điều phối qua NATS, ưu tiên theo `urgency`)
- [x] [V3] Web Nuxt: đăng nhập Keycloak (PKCE), bản đồ MapLibre hiển thị sự cố realtime (subscription) (#59, #60, #77, #78: PR #69, #74, #79, #80)
- [x] [V3] Màn hình phân công + cập nhật trạng thái (#61, PR #76)
- [x] [V1] Centrifugo OSS: đẩy thông báo realtime (#68, PR #73)

## Tuần 4 · 05–11/11 · Tầng [D] + lên mạng → v0.3.0 (chốt 24/10/2026)
- [x] [V2] Mô phỏng cảm biến mực nước (Python → MQTT) (khung có từ #30; #84: 9 trạm ở Quảng Nam, Đà Nẵng, kịch bản `tran-lu` 48 giờ trong `du_lieu/tran_lu_mau.json`, `--phat-lai`, `--seed`)
- [x] [V2] NATS → Scorpio: thực thể trạm đo NGSI-LD (bản sao số) (#85: consumer `ban-sao-so` trên `CUU_TRO_CAM_BIEN`, Scorpio trong `core`, đọc qua `/ngsi-ld/v1/*`)
- [x] [V1] Cảnh báo vượt ngưỡng → Temporal → thông báo Telegram (#87: workflow `CanhBaoVuotNguong` mỗi đợt, báo 1 lần mỗi bước; kênh `gia-lap` mặc định, `telegram` khi đặt token trong OpenBao)
- [x] [V2] Sổ cái minh bạch: niêm phong nhập/xuất hàng, tiền cứu trợ + endpoint xác minh (#89: bút toán thu/chi, outbox + worker niêm phong bù, `/workflow/minh-bach/xac-minh/{mã}`, `so-cai`, `quy`; trang web là #63)
- [x] [V2] Xuất dữ liệu cũ ra Parquet + truy vấn DuckDB (#91: `make luu-tru`, `make luu-tru-truy-van`, bucket `cuu-tro-lakehouse`, phân vùng theo tháng, khử định danh, idempotent)
- [x] [V2] Grafana dashboard điều hành (#92: Grafana OSS profile `bi`, provisioning từ tệp, role chỉ đọc `cuu_tro_bi`, `/grafana/` qua APISIX; SSO Keycloak để sau)
- [x] [V3] Web: lớp trạm đo mực nước trên bản đồ (#62: NGSI-LD qua gateway, màu theo cấp báo động, popup + biểu đồ 24 giờ, tải lại khi có cảnh báo realtime)
- [x] [V3] Web: trang Minh bạch công khai cho phiếu kho + bút toán tiền, trình duyệt tự kiểm sổ cái (#63: `/workflow/minh-bach/xac-minh`, WebCrypto Ed25519 + Merkle)
- [ ] [V1] Thuê VPS + tên miền, HTTPS, CI tự triển khai từ `main` — **còn mở**: chờ người hướng dẫn (VPS, tên miền)
- [ ] [V3] Cuối tuần: mời 3–5 người dùng thật thử, ghi phản hồi thành issue `user-feedback` — **còn mở**: chờ người hướng dẫn (cần bản chạy trên VPS)
- [ ] [V1] Grafana đăng nhập SSO Keycloak (generic OAuth) thay tài khoản admin — **còn mở**, để sau #92 (realm chỉ import lần đầu: cần hướng dẫn thêm client cho máy đã chạy)
- [x] [V1] Release v0.3.0 (#94, PR #95, #96; tag `v0.3.0` trên `main`, Release kèm `.tar.gz` + `SHA256SUMS`, 24/10/2026)

## Tuần 5 · 12–18/11 · Tầng [I] + demo công khai
- [x] [V3] AI bóc tách tin kêu cứu tự do → JSON (địa chỉ, số người, mức khẩn cấp); `LLM_PROVIDER` chọn Ollama + Qwen2.5 7B hoặc API ngoài (#102)
- [x] [V3] Hàng chờ duyệt HITL trên web điều phối (#104: `vao_hang_cho` trên `/workflow/ai/boc-tach`, bảng vết `ai_intake_reviews`, `POST /workflow/hang-cho/{id}/duyet|huy` qua Poka-yoke của #66, trang web "Duyệt tin AI" có bản đồ chọn vị trí)
- [x] [V3] App hiện trường React Native (D-011, thay Flutter): gửi kêu cứu/cập nhật hiện trường, hàng đợi offline (#106: `apps/cuu-tro/mobile/`, đăng nhập Keycloak PKCE client `dxos-mobile`, MapLibre, hàng đợi mã hóa trong Keychain/Keystore, API nhận `Idempotency-Key` cho kêu cứu/ảnh/chuyển tin, job CI `mobile`)
- [ ] [V1] Demo công khai trên tên miền, bật GitHub Discussions — Discussions **đã bật**; demo trên tên miền còn chờ người hướng dẫn (VPS, tên miền)

## Tuần 6 · 19–25/11 · Tuần UX + cộng đồng → v0.4.0
- [ ] [V3] Sửa theo phản hồi người dùng (mỗi phản hồi một issue `user-feedback`)
- [ ] [V3] Rà soát UX hiện trường: thao tác một tay, mạng yếu, chữ lớn, tương phản
- [ ] [V2] Công bố bộ mô phỏng cảm biến + mô hình dữ liệu NGSI-LD trạm đo cho cộng đồng (tài liệu + ví dụ)
- [ ] [V1] README song ngữ đầy đủ, hướng dẫn viết module cắm–rút trong `apps/` + 1 module mẫu
- [ ] [V1][V2][V3] **Tập trình bày lần 1** (15 phút, có giám khảo thử)
- [ ] [V1] Release v0.4.0

## Tuần 7 · 26/11–06/12 · Nộp bài → v1.0.0
- [ ] [V1] Rà 6 tiêu chí PoF đạt toàn bộ · đóng băng tính năng · release v1.0.0
- [ ] [V1] Gửi email nộp bài trước 17:00 06/12
- [ ] [V3] Slide 15 phút + video demo dự phòng
- [ ] [V1][V2][V3] **Tập trình bày lần 2**

## 07–10/12 · Trước chung kết
- [ ] [V1][V2][V3] Tập trình bày lần cuối
- [ ] [V1] Kiểm tra demo trên VPS, bản chạy local dự phòng
