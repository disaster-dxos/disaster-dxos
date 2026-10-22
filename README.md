English: [README.en.md](README.en.md)

![Disaster DX-OS: đội cứu hộ, trạm đo mực nước và điểm điều phối trong vùng lũ](docs/images/banner.webp)

# Disaster DX-OS

**Hệ điều hành Ứng phó Thiên tai & Cứu trợ Cộng đồng**, nền tảng nguồn mở giúp chính quyền xã, đội cứu hộ và tình nguyện viên tiếp nhận tin kêu cứu, điều phối cứu hộ theo vị trí thật và công khai hàng cứu trợ để ai cũng kiểm chứng được.

[![Giấy phép Apache-2.0](https://img.shields.io/badge/gi%E1%BA%A5y%20ph%C3%A9p-Apache--2.0-blue)](LICENSE)
[![Phiên bản](https://img.shields.io/github/v/release/disaster-dxos/disaster-dxos?label=phi%C3%AAn%20b%E1%BA%A3n)](https://github.com/disaster-dxos/disaster-dxos/releases)
[![CI](https://github.com/disaster-dxos/disaster-dxos/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/disaster-dxos/disaster-dxos/actions/workflows/ci.yml)

Bài dự thi OLP Phần mềm Nguồn mở 2026, đề tài DX-OS Open-Core, đội DTU_DZ_1.

## Mục lục

- [Bài toán](#bài-toán)
- [Kiến trúc](#kiến-trúc)
- [Hai luồng nghiệp vụ chính](#hai-luồng-nghiệp-vụ-chính)
- [Trạng thái](#trạng-thái)
- [Yêu cầu máy](#yêu-cầu-máy)
- [Chạy từ máy sạch](#chạy-từ-máy-sạch)
- [Tài khoản mẫu và thử API](#tài-khoản-mẫu-và-thử-api)
- [Cấu hình](#cấu-hình)
- [Thêm ứng dụng mới vào `apps/`](#thêm-ứng-dụng-mới-vào-apps)
- [Kiểm thử và lint](#kiểm-thử-và-lint)
- [Xử lý lỗi thường gặp](#xử-lý-lỗi-thường-gặp)
- [Đóng góp](#đóng-góp)
- [Giấy phép](#giấy-phép)
- [Phiên bản](#phiên-bản)

## Bài toán

Mỗi mùa bão lũ, tin kêu cứu đến rải rác qua điện thoại, mạng xã hội, người quen báo hộ. Cùng một nhà được báo nhiều lần trong khi nhà khác bị bỏ sót. Người điều phối không có bức tranh thời gian thực về mực nước, đội nào đang rảnh, đội nào đang ở gần. Tiền và hàng cứu trợ đi qua nhiều tay, người dân và nhà tài trợ khó biết hàng đã đến đâu.

Disaster DX-OS giải quyết bốn việc:

| Vấn đề | Cách làm |
|---|---|
| Tin kêu cứu trùng, thiếu vị trí | Poka-yoke ngay trong CSDL: bắt buộc tọa độ, chặn tin trùng cùng số điện thoại trong 200 m / 6 giờ |
| Phân công chậm, cảm tính | Workflow Temporal tìm đội sẵn sàng gần nhất (PostGIS), gán đội, chờ đội xác nhận có hạn |
| Thiếu số liệu hiện trường | Trạm đo mực nước gửi MQTT vào NATS JetStream, vượt ngưỡng thì phát sự kiện cảnh báo |
| Cứu trợ thiếu minh bạch | Mỗi phiếu nhập/xuất kho được ghi vào sổ cái chỉ-thêm (Tessera); ai cũng tự kiểm chứng được, không cần tài khoản |

![Hàng cứu trợ được ghi thành chuỗi khối kiểm chứng được, người dân đứng xem](docs/images/minh-bach-cuu-tro.webp)

Người dùng: cán bộ xã (vai trò `dieu-phoi`), thành viên đội cứu hộ (`cuu-ho`), tình nguyện viên (`tinh-nguyen`), người dân và nhà tài trợ (xem công khai). Ánh xạ từng yêu cầu của đề vào mã nguồn: [`docs/de-thi-mapping.md`](docs/de-thi-mapping.md).

## Kiến trúc

![Sơ đồ kiến trúc Disaster DX-OS: Tầng 2 apps/cuu-tro gọi lõi Tầng 1 core/ qua APISIX](docs/images/kien-truc.svg)

Hai tầng theo mô hình Open-Core của đề:

- **Tầng 1, lõi headless** (`core/`): chỉ có API, không có giao diện người dùng cuối, không chứa nghiệp vụ thiên tai. Bốn dịch vụ bắt buộc:
  1. **SSO / MFA**: Keycloak 26.8 (OIDC, OTP bắt buộc với vai trò `dieu-phoi`).
  2. **API Gateway**: Apache APISIX 3.19 + Coraza WAF (OWASP CRS 4.14), kiểm JWT, rate limit, CORS. Là điểm vào duy nhất của Tầng 2.
  3. **Dữ liệu**: có cấu trúc trên PostgreSQL 17 + PostGIS 3.5 với GraphQL tự sinh bằng Hasura CE v2.51; phi cấu trúc trên SeaweedFS (S3).
  4. **Workflow engine**: Temporal 1.29.

  Thêm: NATS JetStream + MQTT (sự kiện, IoT), sổ cái minh bạch `core/ledger` (Tessera, Go), OpenBao (bí mật, không có bí mật nào trong `.env`).
- **Tầng 2, ứng dụng** (`apps/cuu-tro/`): realm và vai trò, schema, quyền GraphQL, backend Python (`cuu-tro-api`, `cuu-tro-worker`, `cuu-tro-cam-bien`), bộ giả lập trạm đo. Web điều phối (Nuxt 3 + MapLibre) và app hiện trường (Flutter) đang làm. Tầng 2 chỉ gọi lõi qua APISIX.

Chi tiết từng thành phần, luồng JWT, route gateway, quản lý bí mật, RAM đo thật: [`docs/architecture.md`](docs/architecture.md). Phiên bản và giấy phép từng thành phần: [`DEPENDENCIES.md`](DEPENDENCIES.md).

## Hai luồng nghiệp vụ chính

![Luồng kêu cứu → phân công → xác nhận và luồng phiếu kho → sổ cái → kiểm chứng công khai](docs/images/luong-cuu-tro.svg)

API, quyền theo vai trò và lệnh mẫu của từng luồng: [`apps/cuu-tro/README.md`](apps/cuu-tro/README.md).

## Trạng thái

Đang phát triển, hướng tới v0.1.0 (cuối tuần 2). Đã chạy được trong `make up`:

| Nhóm | Đã có |
|---|---|
| Lõi | Keycloak, APISIX + Coraza WAF, OpenBao (chế độ server), PostgreSQL + PostGIS, Hasura CE, SeaweedFS, Temporal, NATS JetStream + MQTT, sổ cái Tessera |
| `apps/cuu-tro` | Schema `cuu_tro` + Poka-yoke, phân quyền GraphQL 3 vai trò, workflow phân công, luồng cảm biến, ảnh hiện trường, phiếu kho → sổ cái → trang minh bạch |
| Kiểm thử | `make smoke` 339 ca qua gateway và CSDL; pytest; `go test`; CI 7 job |

Sắp có (tuần 3–5): web điều phối + bản đồ, app hiện trường, Scorpio NGSI-LD, ClamAV, Centrifugo + bot Telegram, AI bóc tách tin kêu cứu có người duyệt (Ollama + Qwen2.5 7B/14B, Qdrant), Grafana. Kế hoạch: [`docs/PLAN.md`](docs/PLAN.md).

## Yêu cầu máy

| Mục | Tối thiểu |
|---|---|
| Hệ điều hành | Linux, macOS (Intel hoặc Apple Silicon). Windows qua WSL 2 về lý thuyết chạy được, đội chưa kiểm thử |
| Docker | Docker Engine 24+ hoặc Docker Desktop, **Docker Compose 2.20+** (cần `include`) |
| RAM cấp cho Docker | 4 GB trở lên. Đo thật: cả hệ thống dùng khoảng 2,0 GB sau `make smoke` |
| Ổ trống | 10 GB trở lên. Đo thật: image khoảng 6,9 GB, build cache khoảng 0,8 GB, cộng volume dữ liệu |
| Công cụ | `git`, `make`, `bash`, `curl`, `python3`, `openssl` |
| Cổng trống | `8080` (Keycloak), `9080` (APISIX); chỉ trên `127.0.0.1`: `8200`, `15432`, `8081`, `8333`, `7233`, `8088`, `4222`, `1883` |

Không bắt buộc: [`uv`](https://docs.astral.sh/uv/) để chạy pytest, Go 1.26 để chạy `go test`, `shellcheck` + `yamllint` cho `make lint`.

## Chạy từ máy sạch

```bash
git clone https://github.com/disaster-dxos/disaster-dxos.git
cd disaster-dxos
cp .env.example .env
make up
make smoke
```

| Bước | Việc xảy ra |
|---|---|
| `cp .env.example .env` | Cấu hình cho máy dev. Không có bí mật nào trong file này; `KC_DEMO_USER_PASSWORD` chỉ là mật khẩu của tài khoản mẫu |
| `make up` | Chạy OpenBao, khởi tạo (Shamir 3 mảnh, ngưỡng 2), mở khóa, sinh ngẫu nhiên mọi bí mật lõi, rồi chạy profile `core` + `app`: kéo image, build 3 image từ mã nguồn (APISIX + Coraza, sổ cái Go, backend Python), áp migration, áp metadata Hasura, tạo bucket |
| `make smoke` | Nạp dữ liệu giả rồi kiểm 339 ca: OpenBao, JWT, route gateway + WAF, ràng buộc CSDL, phân quyền GraphQL, workflow phân công, cảm biến MQTT, ảnh hiện trường, sổ cái |

Đo thật ngày 22/10/2026 trên bản clone sạch từ GitHub, chạy ở thư mục khác thư mục mã gốc (Mac Apple Silicon, Docker Desktop, Docker Engine 28.5, chưa có image nào trên máy): `make up` lần đầu 2 phút 36 giây (gồm kéo khoảng 6,9 GB image và build), lần sau 48 giây; `make smoke` 72 giây, đạt 339/339. Mạng chậm hơn thì lần đầu lâu hơn.

**OpenBao và thư mục `.data/openbao/`.** Lần đầu `make up` ghi unseal key và root token vào `.data/openbao/` (đã nằm trong `.gitignore`). Giữ kín thư mục này: mất nó thì không mở khóa được dữ liệu OpenBao.

| Lệnh | Khi nào dùng |
|---|---|
| `make bao-status` | Xem OpenBao đã mở khóa chưa |
| `make bao-unseal` | Sau khi khởi động lại máy, nếu đặt `OPENBAO_DEV_AUTO_UNSEAL=false` (mặc định `true` trên máy dev: container `openbao-unseal` tự mở) |
| `make bao-init` | Nạp lại bí mật, policy, AppRole còn thiếu; chạy lại bao nhiêu lần cũng được, không ghi đè |

Lệnh khác: `make ps`, `make logs`, `make down` (dừng, giữ dữ liệu), `make seed` (nạp lại dữ liệu giả), `make gia-lap` và `make gia-lap-vuot-nguong` (giả lập trạm đo gửi MQTT). Danh sách đầy đủ trong [`Makefile`](Makefile).

## Tài khoản mẫu và thử API

Tài khoản trong realm `disaster` là **dữ liệu giả** của `apps/cuu-tro`, chỉ dùng trên máy dev. Mật khẩu là giá trị `KC_DEMO_USER_PASSWORD` trong `.env`.

| Tên đăng nhập | Vai trò | Ghi chú |
|---|---|---|
| `dieuphoi01` | `dieu-phoi` (cán bộ xã) | Đăng nhập qua trình duyệt bị bắt cài OTP |
| `cuuho01` | `cuu-ho` | Thành viên "Đội ca nô Biên phòng" trong dữ liệu mẫu |
| `tinhnguyen01` | `tinh-nguyen` | Chỉ thấy tin mình tạo, không thấy SĐT người báo |

Dữ liệu mẫu là xã An Lạc giả định (`make seed`, `make smoke` cũng tự nạp). Mật khẩu quản trị Keycloak không nằm trong `.env`, lấy từ OpenBao khi cần: `BAO_TOKEN=$(cat .data/openbao/root.token) docker compose exec -e BAO_TOKEN openbao bao kv get secret/core/keycloak-admin`.

Thử nhanh qua gateway (client `dxos-dev-cli` chỉ dùng khi dev):

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
```

Phân công đội, xác nhận, tải ảnh, lập phiếu kho, trang minh bạch, tự kiểm sổ cái bằng `ledger-verify`: xem [`apps/cuu-tro/README.md`](apps/cuu-tro/README.md).

## Cấu hình

Mọi cấu hình qua biến môi trường trong `.env`, có giải thích trong [`.env.example`](.env.example). Bí mật của dịch vụ lõi **không** nằm trong `.env` mà nằm trong OpenBao (đường dẫn `secret/core/*` và `secret/app/<DXOS_APP>/*`, xem [`docs/architecture.md`](docs/architecture.md) mục 8).

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `DXOS_APP` | `cuu-tro` | Ứng dụng Tầng 2 cắm vào lõi: tên thư mục trong `apps/` |
| `COMPOSE_PROJECT_NAME` | `disaster-dxos` | Tiền tố tên container, volume, mạng |
| `KEYCLOAK_PORT`, `KEYCLOAK_PUBLIC_URL` | `8080`, `http://localhost:8080` | Đổi cổng thì đổi cả URL (giá trị `iss` của token) |
| `APISIX_PORT`, `GATEWAY_PUBLIC_URL` | `9080`, `http://localhost:9080` | Cổng gateway và URL công khai mà link ảnh trỏ tới |
| `KEYCLOAK_REALM` | `disaster` | Tên realm |
| `KC_REALM_SSL_REQUIRED` | `external` | Realm đòi HTTPS khi nào; xem mục lỗi "HTTPS required" |
| `OPENBAO_DEV_AUTO_UNSEAL` | `true` | Tự mở khóa OpenBao khi khởi động lại. **Chỉ cho máy dev**; triển khai thật đặt `false` |
| `POSTGIS_PLATFORM` | `linux/amd64` | Image PostGIS chỉ có amd64 |
| `GW_RATE_LIMIT_COUNT`, `GW_RATE_LIMIT_WINDOW` | `300`, `60` | Giới hạn request theo IP |
| `GW_CORS_ALLOW_ORIGINS` | `http://localhost:3000` | Origin web được gọi API |
| `PHAN_CONG_*` | 20 km, 6 giờ, 10 lần, 60 s | Bán kính tìm đội, hạn xác nhận, số lần và khoảng chờ tìm lại |

Thêm biến mới thì thêm vào `.env.example` kèm chú thích.

## Thêm ứng dụng mới vào `apps/`

Dành cho lập trình viên muốn dùng lại lõi cho bài toán khác. Mỗi ứng dụng có backend riêng (quyết định D-008), lõi dùng chung. Lõi không biết tên bảng hay quy trình nào; nó chỉ nạp các **điểm cắm** theo quy ước thư mục:

```
apps/<tên>/
├── keycloak/realm.json        # realm, vai trò, client, người dùng mẫu (bắt buộc)
├── db/migrations/NNNN_*.sql   # schema riêng <tên> (dấu - thành _), container migrate áp mỗi lần make up
├── db/seed/, db/tests/        # dữ liệu giả (make seed), kiểm thử ràng buộc (make test-db)
├── hasura/metadata/           # bảng lộ ra GraphQL, quyền theo vai trò
├── compose.yaml               # backend của ứng dụng, profile app; API tên <tên>-api cổng 8000
├── openbao/policies/*.hcl     # quyền đọc bí mật secret/app/<tên>/*
├── s3/buckets.conf            # bucket, bắt buộc tiền tố <tên>-
└── nats/streams.json          # stream JetStream, subject <tên>.>
```

Các bước:

1. Tạo `apps/<tên>/` theo cấu trúc trên, lấy `apps/cuu-tro/` làm mẫu. Cần ít nhất `keycloak/realm.json` và `compose.yaml`.
2. Đặt `DXOS_APP=<tên>` (và `KEYCLOAK_REALM` nếu realm tên khác) trong `.env`.
3. `make up`. Lõi tạo role CSDL `<tên>_app`, bí mật, AppRole, bucket theo quy ước tên; gateway chuyển `/workflow/*` vào `<tên>-api:8000`.

Không sửa gì trong `core/`. Chi tiết và lý do: [`docs/architecture.md`](docs/architecture.md) mục 7, [`apps/README.md`](apps/README.md).

## Kiểm thử và lint

| Lệnh | Kiểm gì | Cần |
|---|---|---|
| `make check` | Header SPDX của mọi file mã, `docker-compose.yml` hợp lệ ở mọi profile | Docker |
| `make lint` | `shellcheck` mọi `*.sh`, `yamllint --strict` mọi YAML | `shellcheck`, `yamllint` |
| `make smoke` | 339 ca chạy thật qua gateway và CSDL | `make up` trước |
| `make test-db` | Ràng buộc CSDL của ứng dụng (ROLLBACK sau khi chạy) | `make up` trước |
| `make test-py` | pytest backend `apps/<DXOS_APP>/workflow` | `uv` |
| `cd core/ledger && go test ./...` | Sổ cái: lá, ghi/proof trên log POSIX thật, CLI kiểm chứng | Go 1.26 |

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) chạy 7 job bắt buộc trên mỗi PR: `license`, `build-from-source`, `shellcheck`, `yamllint`, `pytest`, `go-test`, `go-licenses`.

## Xử lý lỗi thường gặp

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `Bind for 0.0.0.0:8080 failed: port is already allocated` | Cổng đã có chương trình khác dùng | Đổi `KEYCLOAK_PORT` (kèm `KEYCLOAK_PUBLIC_URL`), `APISIX_PORT` (kèm `GATEWAY_PUBLIC_URL`) hoặc biến `*_PORT` tương ứng trong `.env`, rồi `make up`. Tìm chương trình đang chiếm: `lsof -i :8080` |
| Dịch vụ đứng ở `Waiting`, `openbao` unhealthy, `make bao-status` báo `Sealed true` | OpenBao luôn khởi động ở trạng thái khóa | `make bao-unseal`. Nếu báo thiếu key: kiểm tra `.data/openbao/` còn nguyên |
| `make smoke` lỗi `HTTPS required`, hoặc lấy token từ máy host trả 403 | Realm `external` chỉ cho HTTP với IP riêng; VPN, proxy hoặc mạng của Docker Desktop làm Keycloak thấy IP công khai (đã gặp khi kiểm chứng máy sạch) | Chỉ trên máy dev: đặt `KC_REALM_SSL_REQUIRED=none` trong `.env`. Realm chỉ import lần đầu nên tạo lại CSDL (giữ OpenBao): `make down && docker volume rm disaster-dxos_pgdata && make up` |
| Container thoát mã 137, `docker inspect` báo `OOMKilled` | Docker được cấp quá ít RAM | Tăng RAM cho Docker Desktop lên 4 GB trở lên; xem mức dùng bằng `docker stats` |
| `no space left on device` khi kéo image hoặc build | Thiếu ổ | Cần khoảng 10 GB trống. Dọn: `make down && docker image prune -a -f && docker builder prune -f` (giữ volume dữ liệu) |
| PostgreSQL khởi động và chạy chậm hơn trên Mac Apple Silicon | `postgis/postgis` chỉ có image amd64 (`POSTGIS_PLATFORM=linux/amd64`), Docker chạy giả lập | Bình thường, vẫn đạt `make smoke`. Bật "Use Rosetta for x86_64/amd64 emulation" trong Docker Desktop để nhanh hơn |
| `/workflow/*` trả 502 hoặc 503 | Backend ứng dụng chưa chạy | `make ps` xem `cuu-tro-api`; chạy lại `make up` (bật cả profile `app`) |
| Muốn làm lại từ đầu | | Xóa **mọi** dữ liệu dev: `docker compose --profile '*' down -v`, xóa thư mục `.data/openbao/`, rồi `make up`. Không chạy `down -v` mà giữ `.data/openbao/`: key cũ không mở được volume OpenBao mới |

## Đóng góp

Quy trình: issue → nhánh `feature/<số-issue>-<tên-ngắn>` tách từ `develop` → PR về `develop` theo mẫu → CI xanh + 1 người duyệt → merge squash. Commit theo Conventional Commits, mô tả tiếng Việt. Trước khi mở PR: `make check`, `make lint`, thêm dòng vào `CHANGELOG.md`, file mới có header `SPDX-License-Identifier: Apache-2.0` (`make license`).

Chi tiết: [`CONTRIBUTING.md`](CONTRIBUTING.md). Quy tắc ứng xử: [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## Giấy phép

Mã nguồn phát hành theo [Apache-2.0](LICENSE). Bản quyền và ghi nhận thành phần bên thứ ba: [`NOTICE`](NOTICE). Phiên bản và giấy phép từng image, thư viện: [`DEPENDENCIES.md`](DEPENDENCIES.md).

- Chỉ dùng thành phần có giấy phép được OSI công nhận.
- Thành phần copyleft (PostGIS GPL-2.0; sắp có ClamAV GPL-2.0, Grafana AGPL-3.0) chạy như dịch vụ riêng bằng image gốc, không sửa, không nhúng vào mã của dự án.
- Ảnh minh họa trong `docs/images/` do đội tạo bằng công cụ AI, sơ đồ SVG do đội vẽ; cấp phép cùng repo ([`docs/images/README.md`](docs/images/README.md)).

## Phiên bản

Theo [SemVer](https://semver.org/lang/vi/). Bản đã phát hành: [v0.0.1](https://github.com/disaster-dxos/disaster-dxos/releases/tag/v0.0.1) (19/10/2026, khung dự án + profile `core`). Thay đổi chưa phát hành và lịch sử: [`CHANGELOG.md`](CHANGELOG.md).
