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
| Apache APISIX | `apache/apisix:3.19.0-debian` | Apache-2.0 | github.com/apache/apisix | Dịch vụ riêng | core | ✔ |
| Hasura GraphQL Engine **CE** | `hasura/graphql-engine:v2.51.0-ce` | Apache-2.0 | github.com/hasura/graphql-engine | Dịch vụ riêng | core-next | ◐ |
| SeaweedFS | `chrislusf/seaweedfs:4.48` | Apache-2.0 | github.com/seaweedfs/seaweedfs | Dịch vụ riêng | core-next | ◐ |
| Temporal (server, auto-setup) | `temporalio/auto-setup:1.29.7` | MIT | github.com/temporalio/temporal | Dịch vụ riêng | core-next | ◐ |
| Temporal UI (quản trị) | `temporalio/ui:2.56.0` | MIT | github.com/temporalio/ui | Dịch vụ riêng, chỉ mở 127.0.0.1 | core-next | ◐ |
| NATS Server (JetStream + MQTT) | `nats:2.15.1-alpine` | Apache-2.0 | github.com/nats-io/nats-server | Dịch vụ riêng | core-next | ◐ |
| OpenBao (server + bao agent) | `openbao/openbao:2.7.1` | MPL-2.0 | github.com/openbao/openbao | Dịch vụ riêng, image gốc, không sửa (cùng image chạy server, `bao agent` và mở khóa dev) | core | ✔ |
| Coraza WAF (coraza-proxy-wasm) | ghim ở tuần 2 | Apache-2.0 | github.com/corazawaf/coraza-proxy-wasm | Plugin WASM nạp vào APISIX lúc chạy | core | ☐ |
| Scorpio Broker (NGSI-LD) | ghim ở tuần 4 | BSD-3-Clause | github.com/ScorpioBroker/ScorpioBroker | Dịch vụ riêng, dùng chung postgis | gis | ☐ |
| Sổ cái `core/ledger` (nhúng Tessera, xem mục 2) | build từ nguồn trong repo, tuần 4 | Apache-2.0 | mã của đội | Dịch vụ của đội | sec | ☐ |
| ClamAV | ghim ở tuần 2+ | GPL-2.0 | github.com/Cisco-Talos/clamav | Dịch vụ riêng | sec | ☐ |
| Centrifugo **OSS** | ghim ở tuần 3 | Apache-2.0 | github.com/centrifugal/centrifugo | Dịch vụ riêng | core | ☐ |
| Grafana | ghim ở tuần 4 | AGPL-3.0 | github.com/grafana/grafana | Dịch vụ riêng | bi | ☐ |
| Ollama | ghim ở tuần 5 | MIT | github.com/ollama/ollama | Dịch vụ riêng (hoặc chạy trên máy host) | ai | ☐ |
| Qwen2.5 7B / 14B Instruct | tải qua Ollama, tuần 5 | Apache-2.0 | huggingface.co/Qwen | Trọng số model, không đưa vào repo | ai | ☐ |
| Qdrant | ghim ở tuần 5 | Apache-2.0 | github.com/qdrant/qdrant | Dịch vụ riêng | ai | ☐ |

## 2. Thư viện

| Thư viện | Phiên bản | Giấy phép | Nguồn gốc | Dùng ở | Trạng thái |
|---|---|---|---|---|---|
| Temporal Python SDK (`temporalio`) | ghim khi tạo worker, tuần 2 | MIT | github.com/temporalio/sdk-python | Worker workflow (PyPI) | ☐ |
| FastAPI | tuần 2–5 | MIT | github.com/fastapi/fastapi | API dịch vụ Python (PyPI) | ☐ |
| nats-py | tuần 4 | Apache-2.0 | github.com/nats-io/nats.py | Worker nhận sự kiện (PyPI) | ☐ |
| DuckDB | tuần 4 | MIT | github.com/duckdb/duckdb | Truy vấn Parquet lịch sử (PyPI) | ☐ |
| LangGraph | tuần 5 | MIT | github.com/langchain-ai/langgraph | Agent AI bóc tách tin kêu cứu (PyPI) | ☐ |
| Vue 3 | tuần 3 | MIT | github.com/vuejs/core | Web điều phối (npm) | ☐ |
| Nuxt 3 | tuần 3 | MIT | github.com/nuxt/nuxt | Web điều phối (npm) | ☐ |
| Tailwind CSS | tuần 3 | MIT | github.com/tailwindlabs/tailwindcss | Web điều phối (npm) | ☐ |
| MapLibre GL JS | tuần 3 | BSD-3-Clause | github.com/maplibre/maplibre-gl-js | Bản đồ thời gian thực (npm) | ☐ |
| Flutter SDK | tuần 5 | BSD-3-Clause | github.com/flutter/flutter | App hiện trường (pub) | ☐ |
| Tessera (đã chốt – D-007, driver POSIX) | ghim trong `core/ledger/go.mod`, tuần 2–4 | Apache-2.0 | github.com/transparency-dev/tessera | Sổ cái minh bạch `core/ledger` (Go modules) | ☐ |

Phiên bản thư viện được ghim trong file khai báo của từng ứng dụng (`requirements.txt`/`pyproject.toml`, `package-lock.json`, `pubspec.lock`, `go.mod`/`go.sum`) khi tạo. Bảng này cập nhật cùng lúc.

**Phụ thuộc Go của `core/ledger`:** Tessera kéo theo nhiều thư viện gián tiếp (AWS SDK, GCP, BadgerDB…). Khi dựng `core/ledger` phải liệt kê các phụ thuộc gián tiếp vào bảng này và chạy công cụ kiểm giấy phép Go (ví dụ `go-licenses`) trong CI, chặn giấy phép không phải OSI.

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
