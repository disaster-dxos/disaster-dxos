<!-- SPDX-License-Identifier: Apache-2.0 -->
# Phụ thuộc của Disaster DX-OS

Danh sách mọi thành phần bên thứ ba: phiên bản, giấy phép, nguồn gốc và cách dùng.
Cập nhật trong cùng PR khi thêm, bỏ hoặc nâng phiên bản một thành phần (xem `CONTRIBUTING.md` mục 6). Tóm tắt giấy phép cũng có trong `NOTICE`.

Quy ước cột **Cách dùng**:
- **Dịch vụ riêng**: chạy bằng image Docker gốc của nhà phát hành, không sửa mã, giao tiếp qua mạng (HTTP, gRPC, SQL, MQTT). Mã của thành phần không nằm trong kho này.
- **Thư viện**: cài qua trình quản lý gói (pip, npm, pub, Go modules) theo file khai báo phụ thuộc, không chép mã vào repo.

Giấy phép kiểm tra ngày 17/10/2026 trên file LICENSE ở repo chính thức. Trạng thái: ✔ đang dùng trong `docker-compose.yml` · ◐ đã khai báo, chưa dùng trong luồng chính · ☐ dự kiến.

## 1. Dịch vụ (image Docker)

| Thành phần | Image / phiên bản ghim | Giấy phép | Nguồn gốc | Cách dùng | Profile | Trạng thái |
|---|---|---|---|---|---|---|
| PostgreSQL + PostGIS | `postgis/postgis:17-3.5` | PostgreSQL License / GPL-2.0-or-later | github.com/postgis/docker-postgis | Dịch vụ riêng | core | ✔ |
| Keycloak | `quay.io/keycloak/keycloak:26.8.1` | Apache-2.0 | github.com/keycloak/keycloak | Dịch vụ riêng | core | ✔ |
| Apache APISIX | `apache/apisix:3.19.0-debian` (nền của image `disaster-dxos/apisix:3.19.0-coraza0.6.0`, `core/apisix/Dockerfile`) | Apache-2.0 | github.com/apache/apisix | Dịch vụ riêng, image gốc chỉ thêm file wasm | core | ✔ |
| Hasura GraphQL Engine **CE** (bản kèm `hasura-cli` áp metadata lúc khởi động, #26) | `hasura/graphql-engine:v2.51.0-ce.cli-migrations-v3` | Apache-2.0 | github.com/hasura/graphql-engine | Dịch vụ riêng | core | ✔ |
| SeaweedFS | `chrislusf/seaweedfs:4.48` | Apache-2.0 | github.com/seaweedfs/seaweedfs | Dịch vụ riêng; cùng image chạy container một lần `s3-buckets` (`weed shell`) tạo bucket của ứng dụng (#27) | core | ✔ |
| Temporal (server, auto-setup) | `temporalio/auto-setup:1.29.7` | MIT | github.com/temporalio/temporal | Dịch vụ riêng | core | ✔ |
| Temporal UI (quản trị) | `temporalio/ui:2.56.0` | MIT | github.com/temporalio/ui | Dịch vụ riêng, chỉ mở 127.0.0.1 | core | ✔ |
| NATS Server (JetStream + MQTT) | `nats:2.15.1-alpine` | Apache-2.0 | github.com/nats-io/nats-server | Dịch vụ riêng; bắt buộc xác thực, cấu hình `auth.conf` do bao agent render (#30) | core | ✔ |
| OpenBao (server + bao agent) | `openbao/openbao:2.7.1` | MPL-2.0 | github.com/openbao/openbao | Dịch vụ riêng, image gốc, không sửa (cùng image chạy server, `bao agent` và mở khóa dev) | core | ✔ |
| Coraza WAF (coraza-proxy-wasm) + OWASP CRS | `coraza-proxy-wasm-0.6.0.zip`, SHA-256 `cca4e3c75cf6b2e615907f936a1b6dcd0955250e0fb7d3b1c2ecef807d84603c` (file `.wasm` bên trong: `f36e710529167482df820b790981230092da098d26d21aebb16f1d9c8c4e26d5`); nhúng OWASP CRS 4.14.0 | Apache-2.0 (Coraza, coraza-proxy-wasm, OWASP CRS); thư viện Go nhúng trong wasm: libinjection-go BSD-3-Clause, proxy-wasm-go-sdk / coraza-wasilibs Apache-2.0, gjson / nottinygc / aho-corasick MIT | github.com/corazawaf/coraza-proxy-wasm (GitHub Release 0.6.0), github.com/coreruleset/coreruleset | Plugin WASM nạp vào APISIX (`core/apisix/config.yaml` mục `wasm`); tải bản phát hành lúc build image, kiểm SHA-256, không chép mã vào repo (#12) | core | ✔ |
| Scorpio Broker (NGSI-LD) | `scorpiobroker/all-in-one-runner:linux-amd64-6.0.2` (bản native GraalVM "all-in-one", không kèm Kafka/MQTT; chỉ có amd64); trên arm64 (Apple Silicon) Makefile chọn `scorpiobroker/all-in-one-runner:java-6.0.2` (cùng phiên bản, bản JVM, cũng amd64 chạy qua Rosetta; bản native cần AVX2, #99) | BSD-3-Clause (LICENSE của repo, © NEC) | github.com/ScorpioBroker/ScorpioBroker, hub.docker.com/r/scorpiobroker/all-in-one-runner | Dịch vụ riêng, image gốc không sửa. CSDL riêng `scorpio` trên PostgreSQL + PostGIS của lõi (role `scorpio`, không superuser; Scorpio tự tạo bảng bằng Flyway), không MongoDB. Không mở cổng ra host; ghi chỉ từ `cuu-tro-ban-sao-so` trong mạng nội bộ, đọc qua APISIX `/ngsi-ld/v1/*` (JWT, chỉ GET) (#85) | core | ✔ |
| Sổ cái `core/ledger` (nhúng Tessera, xem mục 2) | `disaster-dxos/ledger:0.1.0` build từ nguồn trong repo (`core/ledger/Dockerfile`): bước build `golang:1.26.10-alpine3.24` (BSD-3-Clause, không vào image chạy), image chạy `scratch` | Apache-2.0 | mã của đội | Dịch vụ của đội, ghi chỉ trong mạng nội bộ, đọc công khai qua APISIX `/ledger/*` (#28) | core | ✔ |
| ClamAV | ghim ở tuần 2+ | GPL-2.0 | github.com/Cisco-Talos/clamav | Dịch vụ riêng | sec | ☐ |
| Centrifugo **OSS** | `centrifugo/centrifugo:v6.9.7` | Apache-2.0 (LICENSE tại tag v6.9.7) | github.com/centrifugal/centrifugo | Dịch vụ riêng, image gốc không sửa, không dùng bản PRO. Chỉ đường WebSocket đi qua APISIX `/realtime/websocket`; HTTP API chỉ trong mạng nội bộ; khóa ký token + API key do bao agent render (#68) | core | ✔ |
| Grafana OSS | `grafana/grafana-oss:13.0.2` | AGPL-3.0 (LICENSE của repo) | github.com/grafana/grafana, hub.docker.com/r/grafana/grafana-oss | Dịch vụ riêng, image gốc không sửa mã (AGPL-3.0: không nhúng, không liên kết vào mã dự án). Cấu hình qua biến môi trường + tệp provisioning của dự án (`core/grafana/provisioning`, `apps/cuu-tro/grafana/dashboards`). Datasource PostgreSQL bằng role chỉ đọc `<schema>_bi`; mật khẩu admin và datasource qua OpenBao; không tải plugin/tin tức từ Internet; không mở cổng ra host, mở qua APISIX `/grafana/` (#92) | bi | ✔ |
| Ollama | ghim ở tuần 5 | MIT | github.com/ollama/ollama | Dịch vụ riêng (hoặc chạy trên máy host) | ai | ☐ |
| Qwen2.5 7B / 14B Instruct | tải qua Ollama, tuần 5 | Apache-2.0 | huggingface.co/Qwen | Trọng số model, không đưa vào repo | ai | ☐ |
| Qdrant | ghim ở tuần 5 | Apache-2.0 | github.com/qdrant/qdrant | Dịch vụ riêng | ai | ☐ |

## 2. Thư viện

| Thư viện | Phiên bản | Giấy phép | Nguồn gốc | Dùng ở | Trạng thái |
|---|---|---|---|---|---|
| Temporal Python SDK (`temporalio`) | 1.34.0 | MIT | github.com/temporalio/sdk-python | Worker + client workflow `apps/cuu-tro/workflow` (PyPI, #29) | ✔ |
| FastAPI | 0.150.0 | MIT | github.com/fastapi/fastapi | API workflow `cuu-tro-api` (PyPI, #29) | ✔ |
| Uvicorn | 0.54.0 | BSD-3-Clause | github.com/encode/uvicorn | Máy chủ ASGI của `cuu-tro-api` (PyPI, #29) | ✔ |
| asyncpg | 0.32.0 | Apache-2.0 | github.com/MagicStack/asyncpg | Worker kết nối PostgreSQL (PyPI, #29). Chọn thay psycopg (LGPL-3.0) để giữ toàn bộ phụ thuộc giấy phép dễ dãi | ✔ |
| PyJWT (`pyjwt[crypto]`) | 2.15.1 | MIT | github.com/jpadilla/pyjwt | API kiểm lại JWT bằng JWKS Keycloak (PyPI, #29) | ✔ |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause | github.com/pyca/cryptography | Chữ ký RS256 cho PyJWT; kiểm chữ ký Ed25519 của checkpoint sổ cái trên trang minh bạch (PyPI, khai báo trực tiếp từ #28) | ✔ |
| HTTPX | 0.28.1 | BSD-3-Clause | github.com/encode/httpx | API hỏi Hasura qua gateway `/graphql` (PyPI, #29) | ✔ |
| pytest | 8.3.4 | MIT | github.com/pytest-dev/pytest | Kiểm thử (nhóm `dev`, không có trong image) | ✔ |
| nats-py | 2.16.0 | Apache-2.0 | github.com/nats-io/nats.py | Consumer JetStream `cuu-tro-cam-bien`: khai báo stream, kéo bản tin, phát cảnh báo (PyPI, #30) | ✔ |
| Eclipse Paho MQTT Python (`paho-mqtt`) | 2.1.0 | EPL-2.0 OR BSD-3-Clause (dùng theo EDL-1.0 = BSD-3-Clause) | github.com/eclipse-paho/paho.mqtt.python | Bộ giả lập trạm cảm biến gửi MQTT (PyPI, #30) | ✔ |
| DuckDB | 2.0.0 | MIT | github.com/duckdb/duckdb | Ghi Parquet và truy vấn dữ liệu lịch sử trong `cuu-tro-luu-tru` (`cuu_tro_workflow/luu_tru.py`, PyPI, wheel có sẵn Parquet, không tải extension lúc chạy) (#91) | ✔ |
| LangGraph | tuần 5 | MIT | github.com/langchain-ai/langgraph | Agent AI bóc tách tin kêu cứu (PyPI) | ☐ |
| Vue 3 (qua Nuxt) | 3.5.44 | MIT | github.com/vuejs/core | Web điều phối `apps/cuu-tro/web` (npm, #59) | ✔ |
| Nuxt 4 | 4.6.2 | MIT | github.com/nuxt/nuxt | Web điều phối, chạy chế độ SPA (`ssr: false`) (npm, #59; nâng từ 3.21.11 ở #77 vì Nuxt UI 4 cần Nuxt ≥ 4.1) | ✔ |
| Nuxt UI (`@nuxt/ui`) | 4.12.0 | MIT | github.com/nuxt/ui | Bộ thành phần giao diện web điều phối: khung trang có thanh bên, nút, nhãn, ngăn bên, chế độ sáng/tối (npm, #77). Kéo theo reka-ui 2.11.0, `@nuxt/icon` 2.5.1, `@nuxtjs/color-mode` 4.0.1, tailwind-variants 3.3.1, `@vueuse/core` 14.4.0, `@tailwindcss/vite` 4.3.3 (đều MIT) và `@nuxt/fonts` 0.14.0 (MIT, **tắt** bằng `ui.fonts: false` để không tải Google Fonts) | ✔ |
| Tailwind CSS | 4.3.3 | MIT | github.com/tailwindlabs/tailwindcss | Giao diện web điều phối, màu theo bộ nhận diện (npm, chỉ lúc build, #59; nạp qua Nuxt UI từ #77) | ✔ |
| Lucide icons (`@iconify-json/lucide`) | 1.2.147 | ISC | github.com/lucide-icons/lucide | Biểu tượng web điều phối, đóng gói sẵn vào bundle (`icon.provider: 'none'`), không gọi API Iconify (npm, #77) | ✔ |
| Be Vietnam Pro (font) | commit `804e62d` | OFL-1.1 | github.com/bettergui/BeVietnamPro | Font chữ web điều phối, 4 độ đậm woff2 tự host trong `apps/cuu-tro/web/public/fonts/be-vietnam-pro/` (kèm `OFL.txt`, SHA-256 trong README cùng thư mục), không sửa tệp font (#77) | ✔ |
| MapLibre GL JS | 5.24.0 | BSD-3-Clause | github.com/maplibre/maplibre-gl-js | Bản đồ web điều phối (npm, #59). Chưa dùng 6.x: bản chỉ ESM, worker tách tệp, kiểu bản đồ không nạp được khi Vite đóng gói | ✔ |
| graphql-ws | 6.3.0 | MIT | github.com/enisdenjo/graphql-ws | Client GraphQL subscription qua WebSocket (giao thức `graphql-transport-ws`) của bản đồ tin kêu cứu realtime: tự kết nối lại, ping giữ kết nối (npm, #60). Kéo theo peer `graphql` 17.0.2 (MIT, chỉ dùng kiểu); `ws`, `crossws`, `@fastify/websocket` là peer tùy chọn cho phía máy chủ, không cài | ✔ |
| centrifuge-js (`centrifuge`) | 5.7.4 | MIT | github.com/centrifugal/centrifuge-js | Client WebSocket của web điều phối nhận thông báo realtime từ Centrifugo, tự kết nối lại và lấy bù tin (npm, #68). Kéo theo protobufjs 7.6.6 + `@protobufjs/*` (BSD-3-Clause), long 5.3.2 (Apache-2.0), events 3.3.0 (MIT); web chỉ dùng giao thức JSON | ✔ |
| Flutter SDK | tuần 5 | BSD-3-Clause | github.com/flutter/flutter | App hiện trường (pub) | ☐ |
| Tessera (đã chốt – D-007, driver POSIX + antispam BadgerDB) | v1.0.4 (`core/ledger/go.mod`) | Apache-2.0 | github.com/transparency-dev/tessera | Sổ cái minh bạch `core/ledger`: appender, tile/checkpoint tlog-tiles, gói `client` dựng inclusion proof (Go modules, #28) | ✔ |
| transparency-dev/formats | v0.0.0-20251017110053-404c0d5b696c | Apache-2.0 | github.com/transparency-dev/formats | Đọc/kiểm checkpoint (`log.ParseCheckpoint`) trong `core/ledger` (#28) | ✔ |
| transparency-dev/merkle | v0.0.2 | Apache-2.0 | github.com/transparency-dev/merkle | Leaf hash RFC 6962, kiểm inclusion proof (`ledger-verify`, #28) | ✔ |
| golang.org/x/mod (`sumdb/note`) | v0.33.0 | BSD-3-Clause | cs.opensource.google/go/x/mod | Khóa ký / chữ ký checkpoint Ed25519 dạng note (#28) | ✔ |

**Phụ thuộc Python gián tiếp của `apps/cuu-tro/workflow`** (khóa trong `uv.lock`, có hash trong `requirements.txt`; giấy phép đọc từ metadata gói ngày 20/10/2026): starlette 1.9.0, click 8.5.0, httpcore 1.0.9, idna 3.20, protobuf 7.36.2, pycparser 3.11 (BSD-3-Clause); pydantic 2.14.1, pydantic-core 2.50.1, anyio 4.15.1, h11 0.16.0, annotated-types 0.8.0, annotated-doc 0.0.5, typing-inspection 0.4.4, nexus-rpc 1.4.0 (MIT); cffi 2.1.1 (MIT-0); opentelemetry-api 1.45.1, types-protobuf 7.35.1.20260906 (Apache-2.0); typing-extensions 4.16.0 (PSF-2.0); certifi 2026.10.19 (MPL-2.0, chỉ dùng như gói, không sửa). Tất cả là giấy phép OSI. Image nền `python:3.12.13-slim-bookworm` (PSF-2.0 + gói Debian) chỉ dùng để chạy, không chép mã vào repo.

Phiên bản thư viện được ghim trong file khai báo của từng ứng dụng (`requirements.txt`/`pyproject.toml`, `package-lock.json`, `pubspec.lock`, `go.mod`/`go.sum`) khi tạo. Bảng này cập nhật cùng lúc.

**Phụ thuộc Go của `core/ledger`** (#28). `go.mod` của Tessera khai báo cả driver AWS, GCP, Spanner…, nhưng Go chỉ biên dịch gói được import (driver POSIX), nên binary chỉ chứa các gói dưới đây. Danh sách lấy từ `go-licenses report ./...` ngày 20/10/2026; job CI `go-licenses` chạy `go-licenses check` mỗi PR và chặn giấy phép ngoài danh sách Apache-2.0, BSD-2-Clause, BSD-3-Clause, MIT, ISC, MPL-2.0. Cập nhật bảng này khi nâng Tessera (`go get github.com/transparency-dev/tessera@<bản> && go mod tidy`).

| Gói Go (gián tiếp) | Phiên bản | Giấy phép |
|---|---|---|
| github.com/dgraph-io/badger/v4 (antispam bền vững) | v4.9.1 | Apache-2.0 |
| github.com/dgraph-io/ristretto/v2 (cache của Badger; gói con `z` MIT) | v2.2.0 | Apache-2.0, MIT |
| github.com/google/flatbuffers/go | v25.2.10 | Apache-2.0 |
| github.com/klauspost/compress (zstd, s2, snappy) | v1.18.0 | Apache-2.0, BSD-3-Clause, MIT |
| github.com/cespare/xxhash/v2 | v2.3.0 | MIT |
| github.com/dustin/go-humanize | v1.0.1 | MIT |
| github.com/cenkalti/backoff/v5 | v5.0.3 | MIT |
| github.com/hashicorp/golang-lru/v2 (gói con `simplelru` BSD-3-Clause) | v2.0.7 | MPL-2.0 (thư viện dùng nguyên dạng, không sửa) |
| github.com/go-logr/logr, github.com/go-logr/stdr | v1.4.3, v1.2.2 | Apache-2.0 |
| go.opentelemetry.io/otel, /otel/metric, /otel/trace, /auto/sdk | v1.40.0, v1.2.1 | Apache-2.0 (kèm đoạn BSD-3-Clause) |
| google.golang.org/protobuf | v1.36.11 | BSD-3-Clause |
| golang.org/x/crypto, x/exp, x/net, x/sync, x/sys | v0.48.0, 2024-03-25, v0.50.0, v0.19.0, v0.41.0 | BSD-3-Clause |
| k8s.io/klog/v2 | v2.130.1 | Apache-2.0 |

Công cụ chỉ dùng trong CI, không vào image: `github.com/google/go-licenses/v2` v2.0.1 (Apache-2.0).

**Web điều phối `apps/cuu-tro/web`** (#59). Phiên bản ghim chính xác trong `package.json`, cây phụ thuộc khóa trong `package-lock.json` (`npm ci`). Image `disaster-dxos/cuu-tro-web:0.1.0` build từ nguồn (`apps/cuu-tro/web/Dockerfile`, #64): bước build `node:22.22.3-bookworm-slim`, image chạy `node:22.22.3-alpine3.22` (Node.js MIT + gói Alpine; Nuxt 4.6 cần Node ≥ 22.22.3, #77), chỉ dùng để chạy, không chép mã vào repo. Phụ thuộc trực tiếp ngoài bảng trên, chỉ dùng lúc phát triển/kiểm thử, không vào bản build: Vitest 5.0.5 (MIT), TypeScript 5.9.3 (Apache-2.0), vue-tsc 3.3.13 (MIT), `@types/node` 22.20.5 và `@types/geojson` 7946.0.16 (MIT).

Giấy phép mọi gói (kể cả gián tiếp) kiểm bằng `npm run licenses` (`apps/cuu-tro/web/scripts/check-licenses.mjs`, đọc `package-lock.json`, không cần mạng); thoát mã 1 nếu gặp giấy phép ngoài danh sách OSI MIT, ISC, Apache-2.0, BSD-2/3-Clause, 0BSD, MPL-2.0, BlueOak-1.0.0, Python-2.0. Kết quả ngày 23/10/2026 sau #77 (Nuxt 4 + Nuxt UI), 913 gói: MIT 768, ISC 46, MPL-2.0 24 (lightningcss, chỉ lúc build, dùng nguyên dạng), Apache-2.0 23, BSD-3-Clause 23 (gồm protobufjs của centrifuge-js), BlueOak-1.0.0 13, BSD-2-Clause 7, `MIT OR Apache-2.0` 2, CC0-1.0 2 và CC-BY-4.0 1 (ngoại lệ dưới đây), 0BSD 1, `MIT OR CC0-1.0` 1 (type-fest, dùng theo MIT), `BSD-3-Clause OR GPL-2.0` 1 (node-forge của máy chủ dev `nuxt dev`, dùng theo BSD-3-Clause), không ghi giấy phép 1 (vaul-vue, ngoại lệ dưới đây). Không có gói GPL/AGPL/LGPL bắt buộc.

**Công cụ chụp ảnh README `scripts/chup-anh`** (#65), chỉ chạy trên máy của đội, không vào image hay bản build: Playwright 1.64.0 (Apache-2.0, kèm `playwright-core` cùng phiên bản) điều khiển Chromium headless do Playwright tải về (BSD-3-Clause, không lưu trong repo). Ghép GIF và đổi WebP bằng ffmpeg và ImageMagick cài sẵn trên máy (không phân phối).

Ngoại lệ đã duyệt (không phải giấy phép OSI nhưng tương thích Apache-2.0, chỉ là dữ liệu/công cụ lúc build hoặc dev, không nằm trong `.output`):

| Gói | Giấy phép | Kéo vào bởi | Lý do chấp nhận |
|---|---|---|---|
| caniuse-lite | CC-BY-4.0 | autoprefixer ← `@nuxt/vite-builder` | Bảng dữ liệu trình duyệt dùng khi build CSS; không vào bản build |
| mdn-data (2 bản) | CC0-1.0 | css-tree ← csso/cssnano ← Nuxt | Dữ liệu thuộc tính CSS dùng khi nén CSS; không vào bản build |
| @speed-highlight/core | CC0-1.0 | youch ← `@nuxt/cli` | Tô màu mã trong trang lỗi của `nuxt dev`; không vào bản build |
| vaul-vue 0.4.1 | MIT (không ghi trong `package.json`) | `@nuxt/ui` (thành phần Drawer) | Gói thiếu trường `license`; repo gốc `github.com/unovue/vaul-vue` có tệp LICENSE MIT. Web chưa dùng Drawer nên tree-shaking loại khỏi bản build (#77) |

**Nguồn bản đồ nền của web điều phối:**

| Nguồn | Giấy phép / điều khoản | Dùng |
|---|---|---|
| OpenFreeMap, kiểu `liberty` (`https://tiles.openfreemap.org/styles/liberty`, ô vector OpenMapTiles) | Mã OpenFreeMap MIT; dữ liệu © những người đóng góp OpenStreetMap, ODbL-1.0; lược đồ OpenMapTiles BSD-3-Clause / CC-BY-4.0. Không cần khóa API, bắt buộc ghi công (MapLibre tự hiện từ kiểu bản đồ) | Mặc định (`NUXT_PUBLIC_MAP_STYLE_URL`). Web đổi nhãn sang tên tiếng Việt (`name:vi`) và thêm nhãn "Quần đảo Hoàng Sa (Việt Nam)", "Quần đảo Trường Sa (Việt Nam)" |
| OpenFreeMap, kiểu `dark` (`https://tiles.openfreemap.org/styles/dark`) | Như kiểu `liberty` | Kiểu nền khi giao diện ở chế độ tối (`NUXT_PUBLIC_MAP_STYLE_URL_TOI`, #77; bản đồ dùng từ #78) |
| Ô ảnh OpenStreetMap (`tile.openstreetmap.org`) | Dữ liệu ODbL-1.0, theo Chính sách dùng ô bản đồ của OSMF (lượng truy cập nhỏ, ghi công) | Dự phòng khi không tải được kiểu vector |

Không dùng ô bản đồ Google hay Mapbox (điều khoản đóng). Khi triển khai thật (tuần 4) có thể tự host ô OpenFreeMap/OpenMapTiles và đổi `NUXT_PUBLIC_MAP_STYLE_URL`.

## 3. Danh sách không dùng

Đội chủ động chỉ dùng thành phần có giấy phép OSI, kể cả khi chúng chỉ chạy như dịch vụ riêng. Không dùng:

| Thành phần | Lý do | Thay bằng |
|---|---|---|
| immudb | BSL 1.1 từ 12/2023, không phải giấy phép OSI | Tessera (Apache-2.0, D-007) |
| MongoDB | SSPL, không phải giấy phép OSI | PostgreSQL |
| Orion-LD | Cần MongoDB | Scorpio Broker |
| Stellio | Image CSDL kèm TimescaleDB (thư mục `tsl` dùng Timescale License) | Scorpio Broker |
| HashiCorp Vault | BSL 1.1 | OpenBao |
| n8n | Sustainable Use License, không phải giấy phép OSI | Temporal |
| Redpanda | BSL 1.1 | NATS JetStream |
| Directus | BSL 1.1 | Hasura CE |
| bpmn-js | Giấy phép bpmn.io có điều khoản hạn chế | Workflow viết bằng mã (Temporal) |
| Hasura image không có hậu tố `-ce` | Kèm thành phần Enterprise độc quyền | Tag `-ce` |
| Centrifugo PRO | Giấy phép thương mại | Centrifugo OSS |
| Qwen2.5 3B | Giấy phép Qwen Research, không phải Apache-2.0 | Qwen2.5 7B / 14B |
| Model Llama, Gemma | Giấy phép riêng của Meta/Google, có điều khoản hạn chế sử dụng | Qwen2.5 7B / 14B |
| Image có tag `latest` | Không tái lập được bản build | Tag phiên bản cụ thể |
