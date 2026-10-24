<!-- SPDX-License-Identifier: Apache-2.0 -->
# Cài đặt nâng cao: cấu hình, thêm ứng dụng, kiểm thử

Các bước chạy từ máy sạch, tài khoản mẫu và xử lý lỗi thường gặp nằm trong [`README.md`](../README.md) (mục "Cài đặt từ máy sạch"). Tài liệu này bổ sung phần cấu hình, cách cắm ứng dụng mới vào lõi và cách kiểm thử.

## Cấu hình

Mọi cấu hình qua biến môi trường trong `.env`, có giải thích trong [`.env.example`](../.env.example). Bí mật của dịch vụ lõi **không** nằm trong `.env` mà nằm trong OpenBao (đường dẫn `secret/core/*` và `secret/app/<DXOS_APP>/*`, xem [`architecture.md`](architecture.md) mục 8).

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `DXOS_APP` | `cuu-tro` | Ứng dụng Tầng 2 cắm vào lõi: tên thư mục trong `apps/` |
| `COMPOSE_PROJECT_NAME` | `disaster-dxos` | Tiền tố tên container, volume, mạng |
| `KEYCLOAK_PORT`, `KEYCLOAK_PUBLIC_URL` | `8080`, `http://localhost:8080` | Đổi cổng thì đổi cả URL (giá trị `iss` của token) |
| `APISIX_PORT`, `GATEWAY_PUBLIC_URL` | `9080`, `http://localhost:9080` | Cổng gateway và URL công khai: địa chỉ mở web điều phối (#64), link ảnh trỏ tới, `redirect_uri` của client `dxos-web` (Keycloak đọc lúc import realm lần đầu) |
| `KEYCLOAK_REALM` | `disaster` | Tên realm |
| `KC_REALM_SSL_REQUIRED` | `external` | Realm đòi HTTPS khi nào; xem lỗi "HTTPS required" trong README |
| `OPENBAO_DEV_AUTO_UNSEAL` | `true` | Tự mở khóa OpenBao khi khởi động lại. **Chỉ cho máy dev**; triển khai thật đặt `false` |
| `POSTGIS_PLATFORM` | `linux/amd64` | Image PostGIS chỉ có amd64 |
| `GW_RATE_LIMIT_COUNT`, `GW_RATE_LIMIT_WINDOW` | `300`, `60` | Giới hạn request theo IP |
| `GW_CORS_ALLOW_ORIGINS` | `http://localhost:3000` | Origin web được gọi API. Web chạy trong compose mở qua chính gateway nên cùng origin, không cần; `localhost:3000` dành cho `npm run dev` |
| `GW_WEB_RATE_LIMIT_COUNT` | `600` | Rate limit route web `/*` (request / `GW_RATE_LIMIT_WINDOW` giây / IP) |
| `PHAN_CONG_*` | 20 km, 6 giờ, 10 lần, 60 s | Bán kính tìm đội, hạn xác nhận, số lần và khoảng chờ tìm lại |
| `REALTIME_TOKEN_HAN_GIAY` | `300` | Hạn token kết nối Centrifugo do `cuu-tro-api` cấp (30–3600 giây, #68) |
| `CENTRIFUGO_ALLOWED_ORIGINS` | `GATEWAY_PUBLIC_URL` | Origin được mở WebSocket tới Centrifugo, cách nhau bởi dấu cách (#68) |
| `GW_REALTIME_RATE_LIMIT_COUNT` | `60` | Số lần mở WebSocket `/realtime/websocket` mỗi IP trong `GW_RATE_LIMIT_WINDOW` giây (#68) |
| `SCORPIO_DB`, `SCORPIO_DB_USER` | `scorpio`, `scorpio` | CSDL và role của Scorpio NGSI-LD trên PostgreSQL của lõi; mật khẩu trong OpenBao `secret/core/scorpio-db` (#85) |
| `SCORPIO_PLATFORM` | `linux/amd64` | Image Scorpio chỉ có amd64 (như PostGIS) |
| `SCORPIO_DB_POOL` | `8` | Số kết nối PostgreSQL tối đa của Scorpio (role `scorpio` có `CONNECTION LIMIT 20`); hết thì request xếp hàng |
| `CANH_BAO_KENH` | `gia-lap` | Kênh thông báo cảnh báo vượt ngưỡng (#87): `gia-lap` (hộp thư nội bộ + web) hoặc `telegram` (token + chat id trong OpenBao `secret/app/cuu-tro/telegram`, cách bật: `apps/cuu-tro/README.md`) |
| `APP_BI_DB_USER` | `cuu_tro_bi` | Role chỉ đọc của ứng dụng cho Grafana và bộ xuất Parquet (#91, #92); đổi khi `DXOS_APP` khác `cuu-tro` |
| `SO_CAI_QUET_GIAY`, `SO_CAI_CHO_GIAY` | `10`, `5` | Worker quét mỗi ngần ấy giây các phiếu kho / bút toán tiền chưa niêm phong cũ hơn ngần ấy giây và ghi bù lên sổ cái (#89) |
| `CANH_BAO_HAN_DOT_GIAY` | `604800` | Đợt vượt ngưỡng không có sự kiện về dưới ngưỡng thì workflow tự kết thúc sau ngần này giây |
| `TELEGRAM_API_URL` | `https://api.telegram.org` | Địa chỉ Telegram Bot API (đổi khi dùng máy chủ Bot API riêng) |
| `GW_NGSI_LD_CONTEXT_URL` | `http://<DXOS_APP>-api:8000/ngsi-ld/context.jsonld` | `@context` NGSI-LD mà gateway đặt vào header `Link` của route `/ngsi-ld/v1/*`; Scorpio tải trong mạng nội bộ (#85) |

Thêm biến mới thì thêm vào `.env.example` kèm chú thích.

**Lệnh OpenBao.** Lần đầu `make up` ghi unseal key và root token vào `.data/openbao/` (đã nằm trong `.gitignore`). Giữ kín thư mục này: mất nó thì không mở khóa được dữ liệu OpenBao.

| Lệnh | Khi nào dùng |
|---|---|
| `make bao-status` | Xem OpenBao đã mở khóa chưa |
| `make bao-unseal` | Sau khi khởi động lại máy, nếu đặt `OPENBAO_DEV_AUTO_UNSEAL=false` (mặc định `true` trên máy dev: container `openbao-unseal` tự mở) |
| `make bao-init` | Nạp lại bí mật, policy, AppRole còn thiếu; chạy lại bao nhiêu lần cũng được, không ghi đè |

Mật khẩu quản trị Keycloak không nằm trong `.env`, lấy từ OpenBao khi cần: `BAO_TOKEN=$(cat .data/openbao/root.token) docker compose exec -e BAO_TOKEN openbao bao kv get secret/core/keycloak-admin`.

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
├── openbao/secrets.conf       # bí mật riêng của ứng dụng (tạo trống/ngẫu nhiên nếu chưa có, #87)
├── s3/buckets.conf            # bucket, bắt buộc tiền tố <tên>-
├── nats/streams.json          # stream JetStream, subject <tên>.>
└── ngsi-ld/context.jsonld     # @context NGSI-LD nếu ứng dụng ghi thực thể lên Scorpio (#85); <tên>-api phục vụ ở /ngsi-ld/context.jsonld
```

Các bước:

1. Tạo `apps/<tên>/` theo cấu trúc trên, lấy `apps/cuu-tro/` làm mẫu. Cần ít nhất `keycloak/realm.json` và `compose.yaml`.
2. Đặt `DXOS_APP=<tên>` (và `KEYCLOAK_REALM` nếu realm tên khác) trong `.env`.
3. `make up`. Lõi tạo role CSDL `<tên>_app`, bí mật, AppRole, bucket theo quy ước tên; gateway chuyển `/workflow/*` vào `<tên>-api:8000`.

Không sửa gì trong `core/`. Chi tiết và lý do: [`architecture.md`](architecture.md) mục 7, [`apps/README.md`](../apps/README.md).

## Kiểm thử và lint

| Lệnh | Kiểm gì | Cần |
|---|---|---|
| `make check` | Header SPDX của mọi file mã, `docker-compose.yml` hợp lệ ở mọi profile | Docker |
| `make lint` | `shellcheck` mọi `*.sh`, `yamllint --strict` mọi YAML | `shellcheck`, `yamllint` |
| `make smoke` | 448 ca chạy thật qua gateway và CSDL (đo 22/10/2026 trên volume trống), gồm 31 ca web điều phối (`scripts/smoke-web.sh`, #64) và 26 ca thông báo realtime (`scripts/smoke-realtime.sh`, #68) | `make up` trước; `python3` trên máy host |
| `make test-db` | Ràng buộc CSDL của ứng dụng (ROLLBACK sau khi chạy) | `make up` trước |
| `make test-py` | pytest backend `apps/<DXOS_APP>/workflow` | [`uv`](https://docs.astral.sh/uv/) |
| `cd core/ledger && go test ./...` | Sổ cái: lá, ghi/proof trên log POSIX thật, CLI kiểm chứng | Go 1.26 |

CI ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)) chạy 7 job bắt buộc trên mỗi PR: `license`, `build-from-source`, `shellcheck`, `yamllint`, `pytest`, `go-test`, `go-licenses`.

## Web điều phối (#64)

`make up` build và chạy `cuu-tro-web` (profile `app`). Web không mở cổng ra host, chỉ đi qua APISIX:

| URL | Ghi chú |
|---|---|
| http://localhost:9080/ | Trang điều phối; chưa đăng nhập thì chuyển sang Keycloak (`http://localhost:8080`, client `dxos-web`, `redirect_uri` `http://localhost:9080/auth/callback`) |
| http://localhost:9080/_nuxt/…, /logo/… | Tệp tĩnh, cache `immutable` |

Route `/*` của APISIX có ưu tiên thấp nhất và chỉ nhận GET/HEAD, nên `/graphql`, `/files/*`, `/workflow/*`, `/ledger/*`, `/api/v1/me`, `/healthz` không đổi. Header bảo mật (CSP có hash script, `X-Frame-Options: DENY`, `nosniff`) do web đặt, xem `apps/cuu-tro/web/server/plugins/bao-mat.ts`.

Đổi địa chỉ công khai (vd máy chủ thật): đặt `GATEWAY_PUBLIC_URL` (và `KEYCLOAK_PUBLIC_URL`) trong `.env` rồi `make up`; image web không cần build lại vì Nitro chèn URL vào trang lúc chạy. Realm chỉ import lần đầu: nếu CSDL Keycloak đã có (vd nâng cấp từ v0.1.0), thêm `<GATEWAY_PUBLIC_URL>/*` vào "Valid redirect URIs" và "Valid post logout redirect URIs", `<GATEWAY_PUBLIC_URL>` vào "Web origins" của client `dxos-web` trong trang quản trị Keycloak (realm `disaster` → Clients), hoặc tạo lại CSDL như mục lỗi "HTTPS required" trong README.

### Thông báo realtime (#68)

Người dùng vai `dieu-phoi` mở web là tự kết nối Centrifugo (nút **Thông báo** trên thanh đầu trang: chấm xanh = đang nhận). Ba loại thông báo: tin kêu cứu mới, tin cần điều phối xử lý (phân công tự động đã dừng), trạm đo vượt ngưỡng. Thử nhanh khi đang mở web:

```
make gia-lap-vuot-nguong
```

Web nhận cảnh báo của từng trạm trong khoảng 1 giây. Luồng chạy:

1. Web xin token qua `GET /workflow/realtime/token` (kèm JWT Keycloak; vai khác `dieu-phoi` bị 403).
2. Web mở WebSocket `ws://localhost:9080/realtime/websocket` qua APISIX. Centrifugo không mở cổng ra host.
3. Dịch vụ `cuu-tro-thong-bao` đọc sự kiện từ NATS JetStream và đẩy lên kênh `dieu-phoi`.

Nếu nút có chấm đỏ ("Không có quyền nhận thông báo"), tài khoản không có vai `dieu-phoi` hoặc phiên đã hết hạn. Nếu chấm vàng kéo dài, kiểm tra Centrifugo:

```
docker compose logs centrifugo cuu-tro-thong-bao
```

Khóa ký token và API key nằm trong OpenBao `secret/app/<DXOS_APP>/realtime`; `make bao-init` tạo nếu còn thiếu (máy đã chạy bản trước #68: chạy `make up` như thường, script tự thêm). Thiết kế và lý do chọn token riêng thay vì JWT Keycloak: [`architecture.md`](architecture.md) mục 3.5.

Build riêng image web: `docker compose --profile '*' build cuu-tro-web`, hoặc `docker build --build-context logo=docs/images/logo -t disaster-dxos/cuu-tro-web:0.2.0 apps/cuu-tro/web`.
