<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/logo/logo-ngang-nen-trang.png">
    <img src="docs/images/logo/logo-ngang.png" width="480" alt="Logo Disaster DX-OS: khiên che mái nhà trên sóng lũ, có sóng tín hiệu và phao cứu sinh; khẩu hiệu Ứng phó Thiên tai và Cứu trợ Cộng đồng">
  </picture>
</p>

![DTU_DZ_1 · Disaster DX-OS: Hệ điều hành Ứng phó Thiên tai & Cứu trợ Cộng đồng](docs/images/banner.webp)

# Disaster DX-OS

**Hệ điều hành Ứng phó Thiên tai & Cứu trợ Cộng đồng**: nền tảng nguồn mở giúp chính quyền xã, đội cứu hộ và tình nguyện viên tiếp nhận tin kêu cứu, điều phối cứu hộ theo vị trí thật và công khai hàng cứu trợ để ai cũng kiểm chứng được.

**Disaster Response & Community Relief OS**: an open-source platform that helps commune authorities, rescue teams and volunteers collect SOS reports, dispatch rescue by real location, and publish relief goods and funds so that anyone can verify them.

[![Giấy phép Apache-2.0](https://img.shields.io/badge/gi%E1%BA%A5y%20ph%C3%A9p-Apache--2.0-blue)](LICENSE)
[![Phiên bản](https://img.shields.io/github/v/release/disaster-dxos/disaster-dxos?label=phi%C3%AAn%20b%E1%BA%A3n)](https://github.com/disaster-dxos/disaster-dxos/releases)
[![CI](https://github.com/disaster-dxos/disaster-dxos/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/disaster-dxos/disaster-dxos/actions/workflows/ci.yml)

Bài dự thi OLP Phần mềm Nguồn mở 2026, đề tài DX-OS Open-Core, đội DTU_DZ_1.
*Entry for the Vietnam Open Source Software Olympiad (OLP PMNM) 2026, topic "DX-OS Open-Core", team DTU_DZ_1.*

**English readers:** every section below has an English part. To run the system, jump to [Quick start (English)](#-quick-start-english).

**Mục lục · Contents:** [Giới thiệu](#-giới-thiệu--introduction) · [Thách thức](#️-thách-thức--challenges) · [Giải pháp](#-giải-pháp--solution) · [Đối tượng](#-đối-tượng--users) · [Chức năng](#-chức-năng--features) · [Sản phẩm](#-sản-phẩm--product-demo) · [Kiến trúc](#️-kiến-trúc--architecture) · [Công nghệ](#️-công-nghệ--technology) · [Luồng nghiệp vụ](#-luồng-nghiệp-vụ--business-flows) · [Hướng phát triển](#-hướng-phát-triển--roadmap) · [Cài đặt](#️-cài-đặt-từ-máy-sạch) · [Quick start](#-quick-start-english) · [Nâng cấp](#️-nâng-cấp--upgrading) · [Đóng góp](#-đóng-góp--contributing) · [Báo lỗi](#-báo-lỗi--reporting-bugs) · [Giấy phép](#-giấy-phép--license) · [CHANGELOG](#-changelog)

## 🧭 Giới thiệu · Introduction

Miền Trung mỗi năm hứng nhiều cơn bão và lũ. Trong vài giờ nước lên, cán bộ xã phải cùng lúc nghe điện thoại kêu cứu, tìm đội ca nô còn rảnh, theo dõi mực nước và chia hàng cứu trợ, phần lớn bằng sổ tay, nhóm chat và trí nhớ. Disaster DX-OS đưa tất cả việc đó lên một hệ thống chung: một lõi nguồn mở dùng lại được, và một ứng dụng cứu trợ chạy trên lõi đó.

Central Vietnam is hit by several storms and floods every year. In the few hours while the water rises, commune officers have to answer SOS calls, find a free boat team, watch water levels and hand out relief goods all at once, mostly with notebooks, chat groups and memory. Disaster DX-OS puts all of this on one shared system: a reusable open-source core, and a relief application that runs on top of it.

## ⚠️ Thách thức · Challenges

- **Tin kêu cứu rải rác:** đến qua điện thoại, mạng xã hội, người quen báo hộ; nhiều tin thiếu vị trí.
- **Cứu trợ trùng hoặc sót:** cùng một nhà được báo nhiều lần, trong khi nhà khác không ai tới.
- **Thiếu bức tranh thời gian thực:** người điều phối không biết mực nước đang ra sao, đội nào đang rảnh, đội nào ở gần.
- **Tiền và hàng thiếu minh bạch:** hàng đi qua nhiều tay, người dân và nhà tài trợ khó biết hàng đã đến đâu.

English:

- **Scattered SOS reports:** they arrive by phone, social media or through neighbours, and many have no location.
- **Duplicated or missed rescues:** one house is reported many times while another gets no one.
- **No real-time picture:** coordinators do not know the current water level, which team is free, or which team is close.
- **Opaque money and goods:** relief passes through many hands; residents and donors cannot tell where it went.

## 💡 Giải pháp · Solution

- **Chặn sai ngay từ đầu (Poka-yoke):** tin kêu cứu bắt buộc có tọa độ; tin trùng số điện thoại trong 200 m và 6 giờ bị chặn ngay trong CSDL.
- **Phân công theo vị trí thật:** workflow tìm đội sẵn sàng gần nhất, gán đội, chờ đội xác nhận có hạn, quá hạn thì tìm lại.
- **Số liệu hiện trường tự động:** trạm đo mực nước gửi dữ liệu liên tục, vượt ngưỡng thì phát cảnh báo.
- **Minh bạch kiểm chứng được:** mỗi phiếu nhập/xuất hàng và mỗi khoản tiền được ghi vào sổ cái chỉ-thêm; ai cũng tự kiểm được, không cần tài khoản, không cần tin máy chủ.

English:

- **Stop mistakes at the source (Poka-yoke):** an SOS report must have coordinates; a report with the same phone number within 200 m and 6 hours is rejected by the database itself.
- **Dispatch by real location:** a workflow finds the nearest available team, assigns it, waits for confirmation with a deadline, and re-assigns when the deadline passes.
- **Automatic field data:** water-level stations send readings continuously and raise an alert when a threshold is crossed.
- **Verifiable transparency:** every goods receipt/issue and every money entry goes into an append-only ledger; anyone can verify it without an account and without trusting the server.

![Hàng cứu trợ được ghi thành chuỗi khối kiểm chứng được, người dân đứng xem](docs/images/minh-bach-cuu-tro.webp)

## 👥 Đối tượng · Users

| Ai · *Who* | Dùng để làm gì · *Uses it to* | Vai trò trong hệ thống · *Role* |
|---|---|---|
| Chính quyền xã, người điều phối · *Commune authority, coordinators* | Nhận tin, duyệt tin AI, phân công đội, quản lý kho và quỹ cứu trợ · *Receive and review reports, dispatch teams, manage stock and relief funds* | `dieu-phoi` (bắt buộc OTP · *OTP required*) |
| Đội cứu hộ · *Rescue teams* | Nhận việc, cập nhật hiện trường, xác nhận đã cứu · *Accept tasks, update the field situation, confirm rescues* | `cuu-ho` |
| Tình nguyện viên · *Volunteers* | Báo tin kêu cứu hộ người dân, gửi ảnh hiện trường, kể cả khi mất mạng · *Report SOS on behalf of residents, send field photos, even offline* | `tinh-nguyen` |
| Người dân · *Residents* | Gửi kêu cứu, xem cảnh báo · *Ask for help, receive alerts* | qua tình nguyện viên và app hiện trường; bot Telegram cho người dân chưa có · *via volunteers and the field app; a resident Telegram bot is not built yet* |
| Nhà tài trợ, báo chí · *Donors, press* | Tự kiểm chứng tiền và hàng cứu trợ · *Verify relief money and goods themselves* | công khai, không cần tài khoản · *public, no account* |

## 📱 Chức năng · Features

![Sáu chức năng chính: kêu cứu, bản đồ thời gian thực, phân công cứu hộ, cảnh báo mực nước, sổ cái minh bạch, AI bóc tách tin kêu cứu](docs/images/vong-chuc-nang.webp)

| Chức năng | Trạng thái (v0.5.0) |
|---|---|
| **Kêu cứu** có tọa độ, chặn tin trùng | ✅ Từ v0.1: API GraphQL phân quyền theo vai trò · từ v0.2 (#66): API `POST /workflow/keu-cuu` báo lỗi theo từng trường (422), tin trùng 200 m trả 409 |
| **Phân công cứu hộ** đội gần nhất, chờ xác nhận | ✅ Từ v0.1: workflow Temporal, API `/workflow` · từ v0.2 (#67): tự khởi chạy khi có tin mới, ưu tiên theo mức khẩn, đội không nhận trong hạn thì giao đội kế tiếp |
| **Cảnh báo mực nước** từ trạm đo | ✅ Từ v0.1: trạm đo (giả lập) → MQTT → sự kiện vượt ngưỡng · từ v0.3 (#84, #85): 9 trạm ở Quảng Nam, Đà Nẵng với trận lũ mẫu 48 giờ (giả lập), mỗi trạm là một bản sao số NGSI-LD trên Scorpio, đọc qua gateway `/ngsi-ld/v1/*` · từ v0.3 (#87): mỗi đợt vượt ngưỡng là một workflow Temporal, báo đúng 1 lần khi vượt ngưỡng, khi lên nguy hiểm và khi về dưới ngưỡng, vào hộp thư nội bộ + web điều phối, hoặc Telegram khi đặt token bot |
| **Sổ cái minh bạch** tiền và hàng cứu trợ | ✅ Từ v0.1 cho hàng (Tessera, trang công khai, CLI tự kiểm) · từ v0.3 (#89): tiền thu/chi lên sổ cái, worker tự niêm phong bù khi sổ cái tạm dừng, API xác minh theo mã phiếu hoặc mã bút toán kèm bằng chứng · trang web Minh bạch (#63): trình duyệt tự kiểm bằng WebCrypto |
| **Bản đồ thời gian thực** cho người điều phối | ✅ Từ v0.2: web Nuxt 4 + Nuxt UI + MapLibre, GraphQL subscription qua gateway, màn phân công cho điều phối và đội cứu hộ, thông báo Centrifugo · lớp trạm đo mực nước (#62) |
| **Dashboard điều hành, dữ liệu lịch sử** | ✅ Từ v0.3 (#91, #92): Grafana OSS (`make up-bi`, http://localhost:9080/grafana/) với tin kêu cứu theo trạng thái, thời gian phản hồi, mực nước, tồn kho, quỹ; đọc bằng role chỉ đọc nên không thấy SĐT, họ tên; dữ liệu cũ xuất ra Parquet theo tháng trên SeaweedFS (`make luu-tru`), truy vấn bằng DuckDB (`make luu-tru-truy-van`) · sau v0.4.0 (#126, trên `develop`): đăng nhập SSO Keycloak, điều phối là Editor, cứu hộ là Viewer |
| **AI bóc tách tin kêu cứu** tự do, người duyệt lại | ✅ Từ v0.4 (#102): SMS, tin Zalo dán vào, viết không dấu → đề xuất có địa chỉ, tọa độ (nếu tin có), SĐT, số người, mức khẩn, nhu cầu; qua cùng Poka-yoke và chặn trùng của API kêu cứu; AI không tự tạo tin. Chọn mô hình bằng `LLM_PROVIDER`: Qwen2.5 7B qua Ollama (`make up-ai`), API ngoài chuẩn OpenAI, hoặc bộ luật không cần mô hình (mặc định) · **hàng chờ duyệt** (#104): đề xuất hiện cạnh văn bản gốc, người duyệt sửa, chọn vị trí trên bản đồ rồi duyệt mới tạo tin; lưu vết AI đề xuất gì, người sửa trường nào, ai duyệt, lúc nào |
| **App hiện trường** cho tình nguyện viên, đội cứu hộ | ✅ Từ v0.4 (#106, #113): app React Native (Android, iOS) gửi kêu cứu bằng form + GPS hoặc chọn trên bản đồ, dán tin để AI điền sẵn, chuyển tin cho điều phối duyệt, gửi ảnh hiện trường và vị trí đội. **Mất mạng vẫn dùng được**: mọi thứ vào hàng đợi mã hóa trên máy, có mạng thì tự gửi; mỗi bản ghi một khóa idempotency nên gửi lại không tạo trùng. Đã rà UX một tay, mạng yếu, chữ lớn, tương phản ([`apps/cuu-tro/mobile/`](apps/cuu-tro/mobile/README.md)). Chưa build và thử trên máy thật |
| **Quét mã độc** ảnh tải lên | ✅ Từ v0.4 (#111): ClamAV quét ảnh hiện trường trước khi lưu (profile `sec`) |

Ngoài ra đã có: tải và xem ảnh hiện trường qua link ngắn hạn. Ánh xạ từng yêu cầu của đề vào mã nguồn: [`docs/de-thi-mapping.md`](docs/de-thi-mapping.md).

English:

| Feature | Status (v0.5.0) |
|---|---|
| **SOS reports** with mandatory coordinates and duplicate blocking | ✅ Since v0.1: role-based GraphQL API · since v0.2 (#66): `POST /workflow/keu-cuu` with per-field errors (422) and 409 for a duplicate within 200 m |
| **Rescue dispatch** to the nearest team, with confirmation | ✅ Since v0.1: Temporal workflow, `/workflow` API · since v0.2 (#67): starts automatically for each new report, ordered by urgency, re-assigned to the next team when the deadline passes |
| **Water-level alerts** from gauges | ✅ Since v0.1: simulated gauges → MQTT → threshold events · since v0.3 (#84, #85): 9 stations in Quang Nam and Da Nang with a 48-hour sample flood (simulated), each station is an NGSI-LD digital twin on Scorpio, readable through the gateway at `/ngsi-ld/v1/*` · since v0.3 (#87): each alert episode is a Temporal workflow that notifies exactly once when crossing the threshold, when reaching danger and when going back below, to an internal inbox + the web app, or to Telegram when a bot token is set |
| **Transparency ledger** for money and goods | ✅ Since v0.1 for goods (Tessera, public page, verify CLI) · since v0.3 (#89): money in/out on the ledger, a worker seals late entries, a verification API by receipt or entry code with proofs · public web page (#63): the browser verifies the ledger itself with WebCrypto |
| **Real-time map** for coordinators | ✅ Since v0.2: Nuxt 4 + Nuxt UI + MapLibre web app, GraphQL subscriptions through the gateway, assignment board for coordinators and rescue teams, Centrifugo notifications · water-level station layer (#62) |
| **Operations dashboard, historical data** | ✅ Since v0.3 (#91, #92): Grafana OSS (`make up-bi`, http://localhost:9080/grafana/) showing reports by status, response time, water levels, stock and funds; it reads through a read-only role that cannot see phone numbers or names; old data is exported to monthly Parquet files on SeaweedFS (`make luu-tru`) and queried with DuckDB (`make luu-tru-truy-van`) · after v0.4.0 (#126, on `develop`): Keycloak SSO, coordinators are Editors, rescue teams are Viewers |
| **AI extraction** of free-text SOS messages, reviewed by a human | ✅ Since v0.4 (#102): pasted SMS or Zalo messages, even without Vietnamese diacritics → a suggestion with address, coordinates (if present), phone, number of people, urgency and needs; it goes through the same Poka-yoke and duplicate checks as the SOS API; the AI never creates a report by itself. Pick the model with `LLM_PROVIDER`: Qwen2.5 7B on Ollama (`make up-ai`), any OpenAI-compatible API, or a rule-based extractor that needs no model (default) · **review queue** (#104): the suggestion is shown next to the original text, the reviewer edits it, picks the location on the map and approves; the audit trail records what the AI proposed, which fields were changed, who approved and when |
| **Field app** for volunteers and rescue teams | ✅ Since v0.4 (#106, #113): React Native app (Android, iOS) to send SOS reports with a form + GPS or a map pick, paste a message for the AI to pre-fill, forward a message to a coordinator, send field photos and team location. **Works offline**: everything goes into an encrypted on-device queue and is sent when the network is back; each record has an idempotency key so resending never creates duplicates. UX reviewed for one-handed use, weak networks, large text and contrast ([`apps/cuu-tro/mobile/`](apps/cuu-tro/mobile/README.md)). Not yet built and tested on a real device |
| **Malware scanning** of uploads | ✅ Since v0.4 (#111): ClamAV scans field photos before they are stored (profile `sec`) |

Also available: uploading field photos and viewing them through short-lived links. Mapping of every contest requirement to the code: [`docs/de-thi-mapping.md`](docs/de-thi-mapping.md) (Vietnamese).

## 📸 Sản phẩm · Product demo

Web điều phối chạy trên stack thật, dữ liệu trên màn hình là dữ liệu giả. Quy trình demo: đăng nhập (Keycloak, vai điều phối có MFA), xem bản đồ tin kêu cứu và trạm đo mực nước, phân công cứu hộ, rồi tra trang Minh bạch công khai để trình duyệt tự kiểm sổ cái.

The coordination web app running on the real stack with fake data: sign in (Keycloak, MFA for coordinators) → live map of SOS reports and water-level stations → rescue assignment → public transparency page where the browser verifies the ledger by itself.

![GIF demo: đăng nhập, bản đồ tin kêu cứu và trạm đo, phân công, trang Minh bạch tự kiểm sổ cái](docs/images/web-demo-dieu-phoi.gif)

| Sáng · Light | Tối · Dark |
|---|---|
| ![Bản đồ điều phối: tin kêu cứu, trạm đo mực nước, popup mực nước và biểu đồ 24 giờ](docs/images/web-ban-do-tram-do.webp) | ![Bản đồ điều phối ở chế độ tối](docs/images/web-ban-do-tram-do-toi.webp) |
| Bản đồ: tin kêu cứu theo mức khẩn, trạm đo theo cấp báo động, popup mực nước 24 giờ · *Map: SOS reports by urgency, stations by alert level, 24-hour water-level popup* | |
| ![Màn phân công cứu hộ: Cần xử lý, Chờ phân công, Đang phân công, Đang cứu](docs/images/web-phan-cong.webp) | ![Màn phân công ở chế độ tối](docs/images/web-phan-cong-toi.webp) |
| Phân công: đội gần nhất, đồng hồ hạn nhận · *Assignment board: nearest team, acceptance countdown* | |
| ![Trang Minh bạch cứu trợ: máy chủ xác minh, trình duyệt tự kiểm 5 bước](docs/images/web-minh-bach.webp) | ![Trang Minh bạch ở chế độ tối](docs/images/web-minh-bach-toi.webp) |
| Minh bạch: không cần đăng nhập, trình duyệt tự kiểm sổ cái · *Public transparency page: no login, in-browser ledger verification* | |

Chụp lại khi giao diện đổi: [`scripts/chup-anh/`](scripts/chup-anh/) (Playwright, xem [`docs/images/README.md`](docs/images/README.md)).
*To re-take the screenshots after a UI change, use the Playwright scripts in [`scripts/chup-anh/`](scripts/chup-anh/).*

## 🗺️ Kiến trúc · Architecture

![Kiến trúc tổng quan: người dùng đi qua APISIX và Keycloak vào Hasura, SeaweedFS, Temporal, sổ cái; dữ liệu trên PostgreSQL + PostGIS; OpenBao giữ bí mật; trạm đo gửi MQTT vào NATS](docs/images/kien-truc-tong-quan.webp)

Hệ thống có hai tầng theo mô hình Open-Core của đề. **Tầng 1** (`core/`) là lõi headless: chỉ có API, không có giao diện người dùng cuối và không chứa nghiệp vụ thiên tai. Lõi có đủ 4 dịch vụ bắt buộc: **SSO** (Keycloak, có OTP), **API Gateway** (APISIX + Coraza WAF), **dữ liệu** có cấu trúc (PostgreSQL + PostGIS, GraphQL tự sinh bằng Hasura CE) và phi cấu trúc (SeaweedFS S3), **workflow engine** (Temporal); thêm NATS cho sự kiện và IoT, sổ cái Tessera, OpenBao giữ mọi bí mật. **Tầng 2** (`apps/cuu-tro/`) là ứng dụng cứu trợ, chỉ gọi lõi qua APISIX; muốn dùng lõi cho bài toán khác thì thêm một thư mục trong `apps/`, không sửa `core/`. Repo có sẵn module mẫu thứ hai [`apps/muon-thiet-bi/`](apps/muon-thiet-bi/README.md) (mượn trả thiết bị dùng chung) chạy trên cùng lõi, và hướng dẫn viết module: [`docs/viet-module.md`](docs/viet-module.md).

The system has two tiers, following the contest's Open-Core model. **Tier 1** (`core/`) is a headless core: API only, no end-user interface, and no disaster-specific logic. It provides the 4 required services: **SSO** (Keycloak with OTP), **API Gateway** (APISIX + Coraza WAF), **structured data** (PostgreSQL + PostGIS with GraphQL generated by Hasura CE) and **unstructured data** (SeaweedFS S3), and a **workflow engine** (Temporal); plus NATS for events and IoT, a Tessera transparency log, and OpenBao holding every secret. **Tier 2** (`apps/cuu-tro/`) is the relief application and calls the core only through APISIX. To use the core for another problem, add a folder under `apps/` without touching `core/`. The repo ships a second sample module, [`apps/muon-thiet-bi/`](apps/muon-thiet-bi/README.md) (shared equipment lending), running on the same core, and a module guide: [`docs/viet-module.md`](docs/viet-module.md).

Sơ đồ chi tiết, luồng JWT, route gateway, quản lý bí mật: [`docs/architecture.md`](docs/architecture.md).
*Detailed diagrams, JWT flow, gateway routes and secret management: [`docs/architecture.md`](docs/architecture.md) (Vietnamese).*

## ⚙️ Công nghệ · Technology

| Lớp · *Layer* | Thành phần · *Component* | Giấy phép · *License* |
|---|---|---|
| SSO / MFA | Keycloak 26.8 | Apache-2.0 |
| API Gateway | Apache APISIX 3.19 + Coraza WAF (OWASP CRS 4.14) | Apache-2.0 |
| Dữ liệu có cấu trúc · *Structured data* | PostgreSQL 17 + PostGIS 3.5, Hasura GraphQL Engine CE v2.51 | PostgreSQL, GPL-2.0 (dịch vụ riêng · *separate service*), Apache-2.0 |
| Dữ liệu phi cấu trúc · *Unstructured data* | SeaweedFS 4.48 (S3) | Apache-2.0 |
| Workflow | Temporal 1.29 + Python SDK | MIT |
| Sự kiện, IoT · *Events, IoT* | NATS 2.15 JetStream + MQTT | Apache-2.0 |
| Sổ cái minh bạch · *Transparency log* | Tessera (Go, `core/ledger`) | Apache-2.0 |
| Bản sao số · *Digital twin* (NGSI-LD) | Scorpio Broker 6.0 (dùng PostgreSQL + PostGIS, không MongoDB · *on PostgreSQL + PostGIS, no MongoDB*) | BSD-3-Clause |
| Bí mật · *Secrets* | OpenBao 2.7 | MPL-2.0 |
| Thông báo realtime · *Real-time notifications* | Centrifugo OSS 6.9 | Apache-2.0 |
| Backend ứng dụng · *App backend* | Python 3.12, FastAPI | PSF-2.0, MIT |
| Web điều phối · *Coordination web* | Nuxt 4 (Vue 3) + Nuxt UI 4, Tailwind CSS 4, MapLibre GL JS 5 | MIT, BSD-3-Clause |
| App hiện trường · *Field app* (#106) | React Native 0.80 + TypeScript, React Navigation, TanStack Query, Zustand, i18next, MapLibre React Native, react-native-app-auth (PKCE) | MIT |
| Dữ liệu lịch sử, dashboard · *History, dashboard* | Parquet trên SeaweedFS + DuckDB (#91); Grafana OSS 13 dịch vụ riêng, profile `bi` (#92) | MIT; AGPL-3.0 (dịch vụ riêng, image gốc · *separate service, unmodified image*) |
| AI (Tầng [I] · *tier [I]*) | Ollama 0.40 dịch vụ riêng, profile `ai` + Qwen2.5 7B Instruct; hoặc API ngoài chuẩn OpenAI; mặc định bộ luật không cần mô hình (#102) · *or any OpenAI-compatible API; rule-based by default* | MIT; Apache-2.0 |
| Quét mã độc · *Malware scanning* (#111) | ClamAV 1.5 dịch vụ riêng, profile `sec` (`make up-sec`) | GPL-2.0 (dịch vụ riêng, image gốc · *separate service, unmodified image*) |
| Sắp có · *Planned* | Qdrant | Apache-2.0 |

Phiên bản và giấy phép từng image, thư viện: [`DEPENDENCIES.md`](DEPENDENCIES.md).
*Exact versions and licenses of every image and library: [`DEPENDENCIES.md`](DEPENDENCIES.md).*

## 🔄 Luồng nghiệp vụ · Business flows

**Kêu cứu → cứu hộ · SOS → rescue**

![Luồng kêu cứu 5 bước: báo tin, kiểm tra, điều phối, đội gần nhất, đã cứu](docs/images/luong-keu-cuu.webp)

1. **Báo tin:** người dân hoặc tình nguyện viên gửi tin kêu cứu kèm tọa độ (form, app hiện trường, hoặc tin nhắn tự do qua AI rồi người duyệt).
2. **Kiểm tra:** CSDL từ chối tin thiếu tọa độ và tin trùng số điện thoại trong 200 m / 6 giờ.
3. **Điều phối:** tin mới tự khởi chạy workflow Temporal (#67), tin khẩn được xếp trước; người điều phối chỉ can thiệp khi hệ thống báo (hết lần giao, không có đội).
4. **Đội gần nhất:** workflow tìm đội sẵn sàng gần nhất bằng PostGIS và giao đội; đội không nhận hoặc từ chối trong hạn (theo mức khẩn) thì giao đội kế tiếp.
5. **Đã cứu:** đội cứu hộ xác nhận, tin được đóng, đội trở lại trạng thái sẵn sàng.

English:

1. **Report:** a resident or volunteer sends an SOS report with coordinates (form, field app, or a free-text message extracted by AI and then approved by a human).
2. **Check:** the database rejects reports without coordinates and duplicates of the same phone number within 200 m / 6 hours.
3. **Dispatch:** each new report starts a Temporal workflow (#67), urgent reports first; the coordinator only steps in when the system asks (no team left, too many attempts).
4. **Nearest team:** the workflow finds the nearest available team with PostGIS and assigns it; if the team does not accept or refuses before the deadline (based on urgency), the next team is assigned.
5. **Rescued:** the team confirms, the report is closed and the team becomes available again.

**Hàng cứu trợ → kiểm chứng công khai · Relief goods → public verification**

![Luồng minh bạch 4 bước: phiếu cứu trợ, băm, sổ cái công khai, ai cũng kiểm chứng được](docs/images/luong-minh-bach.webp)

1. **Phiếu cứu trợ:** người điều phối lập phiếu nhập hoặc xuất kho (hoặc bút toán thu/chi tiền), tồn kho tự cập nhật.
2. **Băm:** bản ghi chuẩn hóa, không chứa thông tin cá nhân, được băm SHA-256.
3. **Sổ cái công khai:** dấu băm được ghi vào transparency log Tessera, chỉ thêm, không sửa, có chữ ký.
4. **Ai cũng kiểm chứng được:** trang công khai hoặc công cụ `ledger-verify` tự kiểm từ dữ liệu công khai, không cần tài khoản.

English:

1. **Relief record:** a coordinator creates a stock receipt or issue (or a money in/out entry); stock is updated automatically.
2. **Hash:** the record is canonicalised, contains no personal data, and is hashed with SHA-256.
3. **Public ledger:** the hash is appended to a Tessera transparency log: append-only, never edited, signed.
4. **Anyone can verify:** the public web page or the `ledger-verify` tool checks the record against public data, with no account.

API và lệnh mẫu của từng bước: [`apps/cuu-tro/README.md`](apps/cuu-tro/README.md).
*APIs and sample commands for each step: [`apps/cuu-tro/README.md`](apps/cuu-tro/README.md) (Vietnamese).*

## 🚀 Hướng phát triển · Roadmap

Theo [`docs/PLAN.md`](docs/PLAN.md). Đã xong đến v0.5.0 (tuần 1–7):

- **Tuần 1–2 (v0.0.1, v0.1.0):** lõi Tầng 1 đủ 4 dịch vụ, OpenBao, sổ cái Tessera, ứng dụng cứu trợ, phân công Temporal.
- **Tuần 3 (v0.2.0):** web điều phối Nuxt UI, bản đồ realtime, phân công tự động, API kêu cứu, thông báo Centrifugo.
- **Tuần 4 (v0.3.0):** bản sao số NGSI-LD trên Scorpio, trận lũ mẫu, cảnh báo vượt ngưỡng qua Temporal, tiền cứu trợ trên sổ cái, Parquet + DuckDB, Grafana.
- **Tuần 5–6 (v0.4.0):** AI bóc tách tin kêu cứu + hàng chờ duyệt, app hiện trường React Native offline, ClamAV, module mẫu thứ hai, bộ mô phỏng trạm đo cho cộng đồng.
- **Tuần 6–7 (v0.5.0):** Grafana đăng nhập SSO Keycloak, README song ngữ + Quick start tiếng Anh, kịch bản demo 15 phút, script dữ liệu demo và video dự phòng.

Còn lại (tuần 7, đến v1.0.0):

- Thử với người dùng thật và sửa theo phản hồi; build và thử app hiện trường trên máy thật.
- VPS + tên miền + HTTPS, CI tự triển khai từ `main` (chờ hạ tầng).
- Bot Telegram cho người dân, Qdrant cho tìm kiếm ngữ nghĩa.
- Rà 6 tiêu chí PoF, đóng băng tính năng, phát hành v1.0.0 trước hạn nộp 06/12/2026.

English. Following [`docs/PLAN.md`](docs/PLAN.md). Done up to v0.5.0 (weeks 1–7):

- **Weeks 1–2 (v0.0.1, v0.1.0):** Tier 1 core with the 4 required services, OpenBao, Tessera ledger, relief app, Temporal dispatch.
- **Week 3 (v0.2.0):** Nuxt UI coordination web, real-time map, automatic dispatch, SOS API, Centrifugo notifications.
- **Week 4 (v0.3.0):** NGSI-LD digital twins on Scorpio, sample flood, threshold alerts via Temporal, relief money on the ledger, Parquet + DuckDB, Grafana.
- **Weeks 5–6 (v0.4.0):** AI extraction of SOS messages + review queue, offline React Native field app, ClamAV, a second sample module, a flood-gauge simulator for the community.
- **Weeks 6–7 (v0.5.0):** Grafana sign-in through Keycloak SSO, a fully bilingual README with an English quick start, the 15-minute demo script, demo data scripts and a backup video.

Remaining (week 7, towards v1.0.0):

- Tests with real users and fixes from their feedback; build and test the field app on real devices.
- VPS + domain + HTTPS, CI auto-deploy from `main` (waiting for infrastructure).
- Telegram bot for residents, Qdrant for semantic search.
- Review the 6 proof-of-function criteria, feature freeze, release v1.0.0 before the 06/12/2026 deadline.

## 🛠️ Cài đặt từ máy sạch

> **English:** the same steps in English are in [Quick start (English)](#-quick-start-english) below.

### Yêu cầu máy

| Mục | Tối thiểu |
|---|---|
| Hệ điều hành | Linux, macOS (Intel hoặc Apple Silicon). Windows qua WSL 2 về lý thuyết chạy được, đội chưa kiểm thử. Apple Silicon (Docker Desktop, OrbStack hoặc Colima): `make` tự dùng Scorpio bản JVM, vì bản native cần AVX2 mà Rosetta không có (#99); chạy `docker compose up` trực tiếp thì đặt `SCORPIO_IMAGE` trong `.env` |
| Docker | Docker Engine 24+ hoặc Docker Desktop, **Docker Compose 2.20+** (cần `include`) |
| RAM cấp cho Docker | 6 GB trở lên. Đo thật (v0.3.0, 24/10/2026): cả hệ thống khoảng 2,3 GB sau khi khởi động, khoảng 3,0 GB sau `make smoke` (gồm Grafana, profile `bi`). Profile `sec` (ClamAV, `make smoke` tự bật rồi dừng) cần thêm khoảng 1 GB |
| Ổ trống | 15 GB trở lên. Đo thật (v0.3.0): image khoảng 8,5 GB (Grafana 1,4 GB, chỉ khi bật profile `bi`), build cache khoảng 0,8 GB; lúc chạy `make smoke` trên volume trống ổ giảm thêm tới khoảng 10 GB. Chạy xong: `make down` rồi `docker image prune -a` |
| AI bằng mô hình thật (tùy chọn, `make up-ai`) | Thêm ~12 GB ổ (image Ollama 7 GB + Qwen2.5 7B 4,7 GB) và ~5 GB RAM cho Docker. Đo trên MacBook Apple Silicon (CPU): ~11,5 giây mỗi tin. Không bật thì dùng bộ luật mặc định |
| Công cụ | `git`, `make`, `bash`, `curl`, `python3`, `openssl` |
| Cổng trống | `8080` (Keycloak), `9080` (APISIX); chỉ trên `127.0.0.1`: `8200`, `15432`, `8081`, `8333`, `7233`, `8088`, `4222`, `1883` |

Không bắt buộc: [`uv`](https://docs.astral.sh/uv/) để chạy pytest, Go 1.26 để chạy `go test`, `shellcheck` + `yamllint` cho `make lint`.

### Chạy

```bash
git clone https://github.com/disaster-dxos/disaster-dxos.git
cd disaster-dxos
cp .env.example .env
make up
make smoke
```

Sau `make up`, mở web điều phối qua gateway: **http://localhost:9080/** (đăng nhập bằng tài khoản mẫu bên dưới).

| Bước | Việc xảy ra |
|---|---|
| `cp .env.example .env` | Cấu hình cho máy dev. Không có bí mật nào trong file này; `KC_DEMO_USER_PASSWORD` chỉ là mật khẩu của tài khoản mẫu |
| `make up` | Chạy OpenBao, khởi tạo (Shamir 3 mảnh, ngưỡng 2), mở khóa, sinh ngẫu nhiên mọi bí mật lõi, rồi chạy profile `core` + `app`: kéo image, build 4 image từ mã nguồn (APISIX + Coraza, sổ cái Go, backend Python, web Nuxt), áp migration, áp metadata Hasura, tạo bucket |
| `make smoke` | Nạp dữ liệu giả rồi kiểm 1033 ca ở v0.5.0: OpenBao, JWT, route gateway + WAF, ràng buộc CSDL, phân quyền GraphQL, workflow phân công, cảm biến MQTT + trận lũ mẫu, bản sao số NGSI-LD, cảnh báo vượt ngưỡng, ảnh hiện trường, ClamAV, sổ cái (hàng + tiền), web điều phối, thông báo realtime, bản đồ, API kêu cứu, Parquet + DuckDB, Grafana, trang Minh bạch, hàng chờ duyệt AI, đường gọi của app hiện trường, AI bóc tách. Tự bật profile `bi` và `sec` khi cần |

Đo thật ngày 22/10/2026 trên bản clone sạch từ GitHub, chạy ở thư mục khác thư mục mã gốc (Mac Apple Silicon, Docker Desktop, Docker Engine 28.5, chưa có image nào trên máy): `make up` lần đầu 2 phút 36 giây (gồm kéo khoảng 6,9 GB image và build), lần sau 48 giây; `make smoke` 72 giây, đạt 339/339 (số đo v0.1.0). Ở v0.5.0, `make up` + `make seed` + `make smoke` trên volume trống (project tạm, MacBook Apple Silicon, OrbStack, image đã có sẵn) mất khoảng 9 phút (543 giây), đạt 1033/1033. Mạng chậm hơn thì lần đầu lâu hơn.

**Giữ kín `.data/openbao/`.** Lần đầu `make up` ghi unseal key và root token vào đây (đã nằm trong `.gitignore`); mất thư mục này thì không mở khóa được dữ liệu OpenBao. Sau khi khởi động lại máy, nếu OpenBao còn khóa: `make bao-unseal`.

Lệnh khác: `make ps`, `make logs`, `make down` (dừng, giữ dữ liệu), `make seed` (nạp lại dữ liệu giả), `make gia-lap`, `make gia-lap-vuot-nguong` và `make gia-lap-tran-lu` (giả lập trạm đo gửi MQTT; trận lũ mẫu 48 giờ, #84), `make up-bi` (Grafana, #92), `make up-sec` (ClamAV, #111), `make up-ai` (Ollama + Qwen2.5 7B, #102), `make luu-tru` và `make luu-tru-truy-van SQL="..."` (Parquet + DuckDB, #91), `make bao-status`, `make bao-init`. Danh sách đầy đủ, mỗi lệnh một dòng chú thích `##`: [`Makefile`](Makefile).

Cấu hình qua biến môi trường, lệnh OpenBao, cách thêm ứng dụng mới vào `apps/`, kiểm thử và lint: [`docs/cai-dat.md`](docs/cai-dat.md).

### Tài khoản mẫu và thử API

Tài khoản trong realm `disaster` là **dữ liệu giả** của `apps/cuu-tro`, chỉ dùng trên máy dev. Mật khẩu là giá trị `KC_DEMO_USER_PASSWORD` trong `.env`.

| Tên đăng nhập | Vai trò | Ghi chú |
|---|---|---|
| `dieuphoi01` | `dieu-phoi` (cán bộ xã) | Đăng nhập qua trình duyệt bị bắt cài OTP (dùng app OTP bất kỳ, vd FreeOTP, Aegis). Vào Grafana là Editor |
| `cuuho01` | `cuu-ho` | Thành viên "Đội ca nô Biên phòng" trong dữ liệu mẫu. Vào Grafana là Viewer |
| `tinhnguyen01` | `tinh-nguyen` | Chỉ thấy tin mình tạo, không thấy SĐT người báo. Không vào được Grafana |

Dữ liệu mẫu là xã An Lạc giả định (`make seed`, `make smoke` cũng tự nạp).

Web điều phối: http://localhost:9080/ chuyển sang trang đăng nhập Keycloak (client `dxos-web`, PKCE) rồi quay về bản đồ. Thử nhanh API qua gateway (client `dxos-dev-cli` chỉ dùng khi dev):

```bash
set -a; . ./.env; set +a
TOKEN=$(curl -s -X POST http://localhost:8080/realms/disaster/protocol/openid-connect/token \
  -d grant_type=password -d client_id=dxos-dev-cli -d username=dieuphoi01 \
  --data-urlencode password="$KC_DEMO_USER_PASSWORD" | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

# Tin kêu cứu qua GraphQL (Hasura lọc theo vai trò trong JWT)
curl -s -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"query":"{ incidents(limit: 3) { id description status } }"}' http://localhost:9080/graphql

# Không có token thì gateway trả 401
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:9080/graphql

# Khóa công khai của sổ cái, đọc không cần đăng nhập
curl -s http://localhost:9080/ledger/verifier

# AI bóc tách tin kêu cứu viết tự do → đề xuất + Poka-yoke (không tạo tin; mặc định bộ luật, không cần mô hình)
curl -s -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"van_ban": "Cuu voi, nha o thon 3 ngap toi mai, 5 nguoi, 15.8502, 108.1035, sdt 0905 123 456", "nguon": "sms"}' \
  http://localhost:9080/workflow/ai/boc-tach
```

Chạy AI bằng mô hình thật Qwen2.5 7B: `make up-ai` (tải image Ollama và mô hình ~4,7 GB lần đầu), đặt `LLM_PROVIDER=ollama` trong `.env`, rồi `make up`. Mô hình chạy CPU trong Docker; không đủ RAM thì giữ `LLM_PROVIDER=gia-lap`.

Duyệt tin AI trên web: đăng nhập `dieuphoi01`, mở http://localhost:9080/hang-cho, dán tin nhắn, bấm "Bóc tách bằng AI", sửa nếu cần rồi "Duyệt và tạo tin". Gọi API: thêm `"vao_hang_cho": true` vào lệnh trên rồi `POST /workflow/hang-cho/<mã>/duyet`.

Grafana: `make up-bi`, mở http://localhost:9080/grafana/, đăng nhập bằng tài khoản Keycloak ở trên (form mật khẩu của Grafana đã tắt; tài khoản `admin` khẩn cấp: [`apps/cuu-tro/README.md`](apps/cuu-tro/README.md)).

Phân công đội, xác nhận, tải ảnh, lập phiếu kho, trang minh bạch, tự kiểm sổ cái bằng `ledger-verify`: xem [`apps/cuu-tro/README.md`](apps/cuu-tro/README.md).

### Xử lý lỗi thường gặp

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `Bind for 0.0.0.0:8080 failed: port is already allocated` | Cổng đã có chương trình khác dùng | Đổi `KEYCLOAK_PORT` (kèm `KEYCLOAK_PUBLIC_URL`), `APISIX_PORT` (kèm `GATEWAY_PUBLIC_URL`) hoặc biến `*_PORT` tương ứng trong `.env`, rồi `make up`. Tìm chương trình đang chiếm: `lsof -i :8080` |
| Dịch vụ đứng ở `Waiting`, `openbao` unhealthy, `make bao-status` báo `Sealed true` | OpenBao luôn khởi động ở trạng thái khóa | `make bao-unseal`. Nếu báo thiếu key: kiểm tra `.data/openbao/` còn nguyên |
| `make smoke` lỗi `HTTPS required`, hoặc lấy token từ máy host trả 403 | Realm `external` chỉ cho HTTP với IP riêng; VPN, proxy hoặc mạng của Docker Desktop làm Keycloak thấy IP công khai (đã gặp khi kiểm chứng máy sạch) | Chỉ trên máy dev: đặt `KC_REALM_SSL_REQUIRED=none` trong `.env`. Realm chỉ import lần đầu nên tạo lại CSDL (giữ OpenBao): `make down && docker volume rm disaster-dxos_pgdata && make up` |
| Container thoát mã 137, `docker inspect` báo `OOMKilled` | Docker được cấp quá ít RAM | Tăng RAM cho Docker lên 6 GB trở lên; xem mức dùng bằng `docker stats` |
| `no space left on device` khi kéo image hoặc build | Thiếu ổ | Cần khoảng 15 GB trống. Dọn: `make down && docker image prune -a -f && docker builder prune -f` (giữ volume dữ liệu) |
| PostgreSQL khởi động và chạy chậm hơn trên Mac Apple Silicon | `postgis/postgis` chỉ có image amd64 (`POSTGIS_PLATFORM=linux/amd64`), Docker chạy giả lập | Bình thường, vẫn đạt `make smoke`. Bật "Use Rosetta for x86_64/amd64 emulation" trong Docker Desktop để nhanh hơn |
| `/workflow/*` trả 502 hoặc 503 | Backend ứng dụng chưa chạy | `make ps` xem `cuu-tro-api`; chạy lại `make up` (bật cả profile `app`) |
| Đăng nhập Grafana báo lỗi hoặc `/grafana/login/generic_oauth` trả 403 sau khi kéo mã mới | APISIX còn đọc `apisix.yaml` cũ, hoặc client `dxos-grafana` chưa có | Làm theo mục [Nâng cấp](#️-nâng-cấp--upgrading) bên dưới |
| Muốn làm lại từ đầu | | Xóa **mọi** dữ liệu dev: `docker compose --profile '*' down -v`, xóa thư mục `.data/openbao/`, rồi `make up`. Không chạy `down -v` mà giữ `.data/openbao/`: key cũ không mở được volume OpenBao mới |

## 🇬🇧 Quick start (English)

This section is enough to run Disaster DX-OS from a clean machine without reading Vietnamese. Commands, file names and API paths are the same in both languages; some identifiers are Vietnamese words (for example `cuu-tro` = relief, `dieu-phoi` = coordinator, `cuu-ho` = rescue, `tinh-nguyen` = volunteer, `keu-cuu` = SOS).

### 1. Requirements

| Item | Minimum |
|---|---|
| OS | Linux or macOS (Intel or Apple Silicon). Windows through WSL 2 should work but has not been tested by the team. On Apple Silicon (Docker Desktop, OrbStack or Colima), `make` automatically uses the JVM build of Scorpio because the native build needs AVX2, which Rosetta lacks (#99); if you call `docker compose up` directly, set `SCORPIO_IMAGE` in `.env` |
| Docker | Docker Engine 24+ or Docker Desktop, **Docker Compose 2.20+** (the compose file uses `include`) |
| RAM for Docker | 6 GB or more. Measured (v0.3.0, 24/10/2026): about 2.3 GB after start-up, about 3.0 GB after `make smoke` (including Grafana). ClamAV (profile `sec`, started and stopped by `make smoke`) needs about 1 GB more |
| Free disk | 15 GB or more. Measured (v0.3.0): images about 8.5 GB (Grafana 1.4 GB, only with profile `bi`), build cache about 0.8 GB; a `make smoke` run on empty volumes uses up to about 10 GB more while it runs. Clean up with `make down` and `docker image prune -a` |
| Real AI model (optional, `make up-ai`) | About 12 GB more disk (Ollama image 7 GB + Qwen2.5 7B 4.7 GB) and about 5 GB more RAM. Measured on an Apple Silicon MacBook (CPU only): about 11.5 s per message. Without it, the default rule-based extractor is used |
| Tools | `git`, `make`, `bash`, `curl`, `python3`, `openssl` |
| Free ports | `8080` (Keycloak), `9080` (APISIX); on `127.0.0.1` only: `8200`, `15432`, `8081`, `8333`, `7233`, `8088`, `4222`, `1883` |

Optional: [`uv`](https://docs.astral.sh/uv/) to run pytest, Go 1.26 for `go test`, `shellcheck` + `yamllint` for `make lint`.

### 2. Run

```bash
git clone https://github.com/disaster-dxos/disaster-dxos.git
cd disaster-dxos
cp .env.example .env
make up
make smoke
```

| Step | What happens |
|---|---|
| `cp .env.example .env` | Development configuration. It contains no secrets; `KC_DEMO_USER_PASSWORD` is only the password of the sample accounts |
| `make up` | Starts OpenBao, initialises it (Shamir, 3 shares, threshold 2), unseals it, generates every core secret at random, then starts profiles `core` + `app`: pulls images, builds 4 images from source (APISIX + Coraza, the Go ledger, the Python backend, the Nuxt web app), applies database migrations and Hasura metadata, creates S3 buckets |
| `make smoke` | Loads fake sample data and runs the end-to-end checks against the real stack: 1033 checks at v0.5.0. It starts profiles `bi` (Grafana) and `sec` (ClamAV) when needed |

Measured: on a clean clone (Apple Silicon Mac, Docker Desktop, no images cached) the first `make up` took 2 min 36 s including about 6.9 GB of image downloads (v0.1.0). At v0.5.0, `make up` + `make seed` + `make smoke` on empty volumes took about 9 minutes (543 s) with images already present, and passed 1033/1033.

**Keep `.data/openbao/` safe.** The first `make up` writes the unseal keys and root token there (the folder is in `.gitignore`). Without it you cannot unseal OpenBao's data. After a reboot, if OpenBao is sealed: `make bao-unseal`.

### 3. Open the apps

| What | URL | Notes |
|---|---|---|
| Coordination web app | http://localhost:9080/ | Redirects to Keycloak (client `dxos-web`, PKCE), then back to the map |
| AI review queue | http://localhost:9080/hang-cho | Paste a message, click "Bóc tách bằng AI" (extract with AI), edit, then "Duyệt và tạo tin" (approve and create) |
| Public transparency page | http://localhost:9080/minh-bach/ | No login; the browser verifies the ledger itself |
| Grafana dashboard | http://localhost:9080/grafana/ | Run `make up-bi` first; sign in with a Keycloak account below |
| Keycloak | http://localhost:8080/ | Admin password in OpenBao `secret/core/keycloak-admin` |

Sample accounts in realm `disaster` are **fake data**, for development only. The password is `KC_DEMO_USER_PASSWORD` from `.env`.

| Username | Role | Notes |
|---|---|---|
| `dieuphoi01` | `dieu-phoi` (commune coordinator) | Browser sign-in requires setting up OTP (any TOTP app, e.g. FreeOTP or Aegis). Grafana Editor |
| `cuuho01` | `cuu-ho` (rescue team) | Member of the sample boat team. Grafana Viewer |
| `tinhnguyen01` | `tinh-nguyen` (volunteer) | Sees only own reports, never the reporter's phone number. No Grafana access |

The sample data is a fictional commune, "An Lạc" (`make seed`; `make smoke` loads it too).

### 4. Try the API

```bash
set -a; . ./.env; set +a
# Token for development only (client dxos-dev-cli allows the password grant)
TOKEN=$(curl -s -X POST http://localhost:8080/realms/disaster/protocol/openid-connect/token \
  -d grant_type=password -d client_id=dxos-dev-cli -d username=dieuphoi01 \
  --data-urlencode password="$KC_DEMO_USER_PASSWORD" | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

# SOS reports through GraphQL (Hasura filters by the role in the JWT)
curl -s -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"query":"{ incidents(limit: 3) { id description status } }"}' http://localhost:9080/graphql

# Without a token the gateway answers 401
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:9080/graphql

# Public key of the transparency log, no login needed
curl -s http://localhost:9080/ledger/verifier

# AI extraction of a free-text SOS message (creates nothing; rule-based by default, no model needed)
curl -s -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"van_ban": "Cuu voi, nha o thon 3 ngap toi mai, 5 nguoi, 15.8502, 108.1035, sdt 0905 123 456", "nguon": "sms"}' \
  http://localhost:9080/workflow/ai/boc-tach
```

Real model: `make up-ai` (downloads Ollama and Qwen2.5 7B the first time), set `LLM_PROVIDER=ollama` in `.env`, then `make up`. Without enough RAM keep `LLM_PROVIDER=gia-lap` (rule-based).

More commands: every target has a `##` comment in the [`Makefile`](Makefile). Useful ones: `make ps`, `make logs`, `make down` (stop, keep data), `make seed`, `make gia-lap-tran-lu` (replay the 48-hour sample flood over MQTT), `make up-bi`, `make up-sec`, `make luu-tru` (export to Parquet).

### 5. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Bind for 0.0.0.0:8080 failed: port is already allocated` | Another program uses the port | Change `KEYCLOAK_PORT` (and `KEYCLOAK_PUBLIC_URL`), `APISIX_PORT` (and `GATEWAY_PUBLIC_URL`) or the matching `*_PORT` in `.env`, then `make up`. Find the program: `lsof -i :8080` |
| Services stuck in `Waiting`, `openbao` unhealthy, `make bao-status` shows `Sealed true` | OpenBao always starts sealed | `make bao-unseal`. If keys are missing, check that `.data/openbao/` is intact |
| `make smoke` fails with `HTTPS required`, or getting a token from the host returns 403 | The realm allows plain HTTP only from private IPs; a VPN, proxy or Docker Desktop networking makes Keycloak see a public IP | Development only: set `KC_REALM_SSL_REQUIRED=none` in `.env`. The realm is imported only once, so recreate the database (keeping OpenBao): `make down && docker volume rm disaster-dxos_pgdata && make up` |
| A container exits with code 137, `docker inspect` shows `OOMKilled` | Docker has too little RAM | Give Docker 6 GB or more; check usage with `docker stats` |
| `no space left on device` | Not enough disk | Free about 15 GB: `make down && docker image prune -a -f && docker builder prune -f` (keeps data volumes) |
| PostgreSQL is slower on Apple Silicon | `postgis/postgis` only ships amd64 images, so Docker emulates them | Expected; `make smoke` still passes. Enable Rosetta emulation in Docker Desktop to speed it up |
| `/workflow/*` returns 502 or 503 | The app backend is not running | `make ps` and look for `cuu-tro-api`; run `make up` again |
| Start over | | Delete **all** development data: `docker compose --profile '*' down -v`, delete `.data/openbao/`, then `make up`. Do not run `down -v` while keeping `.data/openbao/`: the old keys cannot unseal a new OpenBao volume |

Configuration variables, OpenBao commands, adding an app under `apps/`, tests and lint: [`docs/cai-dat.md`](docs/cai-dat.md) (Vietnamese; every variable is also commented in `.env.example`).

## ⬆️ Nâng cấp · Upgrading

**Từ v0.4.0 lên v0.5.0 (#126, Grafana SSO).** Realm Keycloak chỉ import khi CSDL còn trống, và APISIX không tự đọc lại `core/apisix/apisix.yaml` khi tệp được thay bằng `git pull`. Sau khi kéo mã:

```bash
make up                          # openbao-init thêm secret/core/grafana-oauth, cập nhật policy
docker compose restart apisix    # nạp lại apisix.yaml (route /grafana/ chấp nhận tham số iss của Keycloak)
make up-bi                       # tạo lại bao agent nếu còn cấu hình cũ, tạo client dxos-grafana, khởi động lại Grafana
```

Dữ liệu cũ giữ nguyên. Chi tiết và cách dùng tài khoản `admin` khẩn cấp của Grafana: [`apps/cuu-tro/README.md`](apps/cuu-tro/README.md) mục "Đăng nhập SSO".

**From v0.4.0 to v0.5.0 (#126, Grafana SSO).** The Keycloak realm is imported only into an empty database, and APISIX does not re-read `core/apisix/apisix.yaml` when `git pull` replaces the file. After pulling, run the three commands above: `make up` (adds the `secret/core/grafana-oauth` secret and updates policies), `docker compose restart apisix` (reloads the gateway routes), `make up-bi` (recreates outdated secret agents, creates the `dxos-grafana` client, restarts Grafana). Existing data is kept.

Bản phát hành khác: đọc mục của phiên bản trong [`CHANGELOG.md`](CHANGELOG.md) trước khi nâng cấp.
*Other releases: read the version's section in [`CHANGELOG.md`](CHANGELOG.md) before upgrading.*

## 🤝 Đóng góp · Contributing

Quy trình: issue → nhánh `feature/<số-issue>-<tên-ngắn>` tách từ `develop` → PR về `develop` theo mẫu → CI xanh + 1 người duyệt → merge squash. Commit theo Conventional Commits, mô tả tiếng Việt. Trước khi mở PR: `make check`, `make lint`, thêm dòng vào `CHANGELOG.md`, file mới có header `SPDX-License-Identifier: Apache-2.0` (`make license`).

Workflow: issue → branch `feature/<issue-number>-<short-name>` from `develop` → pull request to `develop` using the template → green CI + 1 review → squash merge. Commits follow Conventional Commits (descriptions in Vietnamese; English is welcome from outside contributors). Before opening a PR run `make check` and `make lint`, add a line to `CHANGELOG.md`, and give every new file the `SPDX-License-Identifier: Apache-2.0` header (`make license`).

Chi tiết · *Details*: [`CONTRIBUTING.md`](CONTRIBUTING.md). Quy tắc ứng xử · *Code of conduct*: [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

Dùng lại mà không cần cả hệ thống: [`cong-dong/tram-do-lu/`](cong-dong/tram-do-lu/README.md) là bộ mô phỏng trạm đo lũ (chỉ cần Python, gửi MQTT hoặc NGSI-LD) kèm mô hình dữ liệu NGSI-LD trạm đo, JSON Schema và ví dụ.
*Reuse without the whole system: [`cong-dong/tram-do-lu/`](cong-dong/tram-do-lu/README.md) is a standalone flood-gauge simulator (Python only, sends MQTT or NGSI-LD) with an NGSI-LD station data model, JSON Schemas and examples, documented in both languages.*

## 🐛 Báo lỗi · Reporting bugs

Mở issue tại [GitHub Issues](https://github.com/disaster-dxos/disaster-dxos/issues) theo mẫu "Báo lỗi": mô tả, cách tái hiện, môi trường (hệ điều hành, RAM, `docker compose version`).

Open an issue on [GitHub Issues](https://github.com/disaster-dxos/disaster-dxos/issues) with the "Báo lỗi" (bug report) template: description, steps to reproduce, environment (OS, RAM, `docker compose version`). English is fine.

## 📜 Giấy phép · License

Mã nguồn phát hành theo [Apache-2.0](LICENSE). Bản quyền và ghi nhận thành phần bên thứ ba: [`NOTICE`](NOTICE). Phiên bản và giấy phép từng image, thư viện: [`DEPENDENCIES.md`](DEPENDENCIES.md).

- Chỉ dùng thành phần có giấy phép được OSI công nhận.
- Thành phần copyleft (PostGIS GPL-2.0, Grafana AGPL-3.0, ClamAV GPL-2.0) chạy như dịch vụ riêng bằng image gốc, không sửa, không nhúng vào mã của dự án.
- Ảnh minh họa trong `docs/images/` do đội tạo bằng công cụ AI, sơ đồ SVG do đội vẽ; cấp phép cùng repo. Biểu tượng trong ảnh kiến trúc là hình minh họa, không phải logo chính thức ([`docs/images/README.md`](docs/images/README.md)).

The source code is released under [Apache-2.0](LICENSE). Copyright and third-party notices: [`NOTICE`](NOTICE). Versions and licenses of every image and library: [`DEPENDENCIES.md`](DEPENDENCIES.md).

- Only OSI-approved licenses are used.
- Copyleft components (PostGIS GPL-2.0, Grafana AGPL-3.0, ClamAV GPL-2.0) run as separate services from their unmodified upstream images; they are not modified or embedded in the project's code.
- Illustrations in `docs/images/` were made by the team with AI tools and the SVG diagrams were drawn by the team; they are licensed with the repository. Icons in the architecture picture are illustrations, not official logos.

## 📝 CHANGELOG

Theo [SemVer](https://semver.org/lang/vi/). Bản mới nhất: [v0.5.0](https://github.com/disaster-dxos/disaster-dxos/releases/tag/v0.5.0) (29/10/2026, hoàn thiện cho trình bày: Grafana đăng nhập SSO Keycloak, README song ngữ + Quick start tiếng Anh, kịch bản demo 15 phút và video dự phòng); bản trước: [v0.4.0](https://github.com/disaster-dxos/disaster-dxos/releases/tag/v0.4.0) (29/10/2026, Tầng [I] và tuần UX: AI bóc tách tin kêu cứu có người duyệt, app hiện trường React Native offline, ClamAV, module cắm–rút mẫu, bộ mô phỏng trạm đo cho cộng đồng); bản trước: [v0.3.0](https://github.com/disaster-dxos/disaster-dxos/releases/tag/v0.3.0) (24/10/2026, Tầng [D]: bản sao số trạm đo NGSI-LD, trận lũ mẫu, cảnh báo vượt ngưỡng qua Temporal, tiền cứu trợ trên sổ cái minh bạch, Parquet + DuckDB, Grafana), [v0.2.0](https://github.com/disaster-dxos/disaster-dxos/releases/tag/v0.2.0) (23/10/2026, web điều phối Nuxt UI: bản đồ realtime, phân công tự động, API kêu cứu, thông báo Centrifugo), [v0.1.0](https://github.com/disaster-dxos/disaster-dxos/releases/tag/v0.1.0) (22/10/2026, lõi Tầng 1 đầy đủ + ứng dụng cứu trợ, sổ cái minh bạch), [v0.0.1](https://github.com/disaster-dxos/disaster-dxos/releases/tag/v0.0.1) (19/10/2026, khung dự án + profile `core`). Thay đổi chưa phát hành và lịch sử: [`CHANGELOG.md`](CHANGELOG.md). Mỗi bản có gói mã nguồn `disaster-dxos-X.Y.Z.tar.gz` + `SHA256SUMS`; cách kiểm, build từ gói và quy trình phát hành: [`CONTRIBUTING.md`](CONTRIBUTING.md) mục 7.

Versioned with [SemVer](https://semver.org/). Latest release: [v0.5.0](https://github.com/disaster-dxos/disaster-dxos/releases/tag/v0.5.0) (29/10/2026: ready for the final presentation: Grafana sign-in through Keycloak SSO, a fully bilingual README with an English quick start, the 15-minute demo script and a backup video). Earlier: [v0.4.0](https://github.com/disaster-dxos/disaster-dxos/releases/tag/v0.4.0) (29/10/2026: tier [I] and the UX week: human-reviewed AI extraction of SOS messages, offline React Native field app, ClamAV, a sample plug-in module, a flood-gauge simulator for the community). Earlier: [v0.3.0](https://github.com/disaster-dxos/disaster-dxos/releases/tag/v0.3.0) (24/10/2026, tier [D]: NGSI-LD digital twins, sample flood, threshold alerts via Temporal, relief money on the ledger, Parquet + DuckDB, Grafana), [v0.2.0](https://github.com/disaster-dxos/disaster-dxos/releases/tag/v0.2.0) (23/10/2026, Nuxt UI coordination web: real-time map, automatic dispatch, SOS API, Centrifugo notifications), [v0.1.0](https://github.com/disaster-dxos/disaster-dxos/releases/tag/v0.1.0) (22/10/2026, complete Tier 1 core + relief app, transparency ledger), [v0.0.1](https://github.com/disaster-dxos/disaster-dxos/releases/tag/v0.0.1) (19/10/2026, project skeleton + profile `core`). Unreleased changes and history: [`CHANGELOG.md`](CHANGELOG.md) (Vietnamese). Each release ships a source tarball `disaster-dxos-X.Y.Z.tar.gz` with `SHA256SUMS`; how to verify it, build from it, and the release process: [`CONTRIBUTING.md`](CONTRIBUTING.md) §7.
