<!-- SPDX-License-Identifier: Apache-2.0 -->
# apps/cuu-tro — Ứng phó thiên tai & cứu trợ cộng đồng

Ứng dụng Tầng 2 cho chính quyền xã (điều phối), đội cứu hộ, tình nguyện viên và người dân cần cứu.

| Thư mục | Nội dung | Trạng thái |
|---|---|---|
| `keycloak/realm.json` | Realm `disaster`: vai trò `dieu-phoi`, `cuu-ho`, `tinh-nguyen`; client `dxos-gateway`, `dxos-web`, `dxos-dev-cli` (chỉ dev); 3 người dùng mẫu, mật khẩu lấy từ `.env` | Có |
| `db/migrations/` | Schema `cuu_tro`: `incidents`, `rescue_teams`, `shelters`, `supplies`, `supply_movements`, `sensors` (PostGIS); `team_members` (#26); `sensor_readings` chuỗi đo cảm biến (#30); `incident_media` ảnh hiện trường (#27); quyền lập phiếu + ghi sổ cái cho `cuu_tro_app` (#28) | Có (#25, #26, #30, #27, #28) |
| `db/seed/` | Dữ liệu giả xã An Lạc (giả định) | Có (#25) |
| `db/tests/` | Kiểm thử ràng buộc (Poka-yoke, CHECK, quyền theo search_path, quyền role `cuu_tro_app`, chuỗi đo cảm biến, ảnh hiện trường, phiếu kho + sổ cái) | Có (#25, #26, #29, #30, #27, #28) |
| `hasura/metadata/` | Metadata Hasura: bảng track, quan hệ, quyền theo vai trò JWT | Có (#26) |
| `workflow/` | Backend Python: Temporal worker (`PhanCongCuuHo`, `Hello`) + API FastAPI khởi chạy workflow qua gateway `/workflow/*` (#29); consumer cảm biến NATS JetStream + bộ giả lập trạm đo MQTT (#30); API ảnh hiện trường (#27); phiếu nhập/xuất → sổ cái minh bạch + trang công khai (#28); pytest | Có (#29, #30, #27, #28) |
| `compose.yaml` | Dịch vụ `cuu-tro-worker`, `cuu-tro-api`, `cuu-tro-cam-bien`, `cuu-tro-thong-bao` (#68), `bao-agent-cuu-tro` (profile `app`), `cuu-tro-gia-lap` (profile `gia-lap`), lõi nạp bằng `include` | Có (#29, #30, #27) |
| `openbao/` | Policy + template bao agent cho backend (mật khẩu role `cuu_tro_app`, NATS/MQTT, khóa S3 của ứng dụng, token ghi sổ cái) | Có (#29, #30, #27, #28) |
| `s3/buckets.conf` | Bucket S3 của ứng dụng (`cuu-tro-media`), lõi tạo khi `make up` | Có (#27) |
| `nats/streams.json` | Khai báo stream/consumer JetStream của ứng dụng (`cuu-tro-cam-bien` tạo consumer `ghi-csdl`, `cuu-tro-thong-bao` tạo consumer `realtime-*`) | Có (#30, #68) |
| `web/` | Web điều phối Nuxt 3 + Tailwind + MapLibre: đăng nhập Keycloak OIDC + PKCE (client `dxos-web`), bản đồ + danh sách tin kêu cứu (dữ liệu giả); dịch vụ `cuu-tro-web`, mở qua gateway http://localhost:9080/; xem `web/README.md` | Khung (#59), trong stack (#64) |
| `mobile/` | App hiện trường Flutter | Tuần 5 |

## Dữ liệu (`db/`, #25)

Schema `cuu_tro`, chủ sở hữu role `cuu_tro_owner` (`NOLOGIN`). Role `hasura` chỉ có quyền DML. Cơ chế migration là của lõi (`core/postgres/migrate.sh`, `docs/architecture.md` mục 7.1); thư mục này chỉ chứa SQL.

```mermaid
erDiagram
  rescue_teams ||--o{ incidents : "được phân công"
  shelters ||--o{ supplies : "điểm lưu"
  supplies ||--o{ supply_movements : "phiếu nhập/xuất"
  shelters ||--o{ supply_movements : "nơi nhận"
  rescue_teams ||--o{ team_members : "thành viên"
  sensors ||--o{ sensor_readings : "chuỗi đo"
  incidents ||--o| assignment_queue : "outbox phân công (#67)"
  incidents ||--o{ incident_assignments : "lịch sử giao (#67)"
  rescue_teams ||--o{ incident_assignments : "được giao"

  incidents {
    uuid id PK
    text description
    geography location "Point 4326, NOT NULL"
    int people_count "1..10000"
    text urgency "khan_cap|cao|trung_binh|thap"
    text status "tiep_nhan|phan_cong|dang_cuu|da_cuu|dong"
    phone_vn reporter_phone "0 + 9 số"
    text source
    uuid assigned_team_id FK
  }
  rescue_teams {
    uuid id PK
    text name UK
    int member_count
    geography location "vị trí hiện tại"
    text status "san_sang|dang_lam_nhiem_vu|nghi"
    phone_vn contact_phone
  }
  shelters {
    uuid id PK
    text name UK
    geography location
    int capacity "> 0"
    int current_occupancy "<= capacity"
  }
  supplies {
    uuid id PK
    text item_name
    text unit
    numeric quantity ">= 0"
    text storage_name
    uuid shelter_id FK
  }
  supply_movements {
    uuid id PK
    uuid supply_id FK
    text direction "nhap|xuat"
    numeric quantity "> 0"
    bigint ledger_index "Tessera (#28)"
    bytea ledger_leaf_hash "SHA-256"
  }
  sensors {
    uuid id PK
    text code UK
    text kind "muc_nuoc|luong_mua|gio"
    geography location
    numeric warning_threshold
    numeric danger_threshold ">= warning"
    numeric last_value
    text ngsi_ld_id "Scorpio (tuần 4)"
  }
  sensor_readings {
    bigint id PK
    uuid sensor_id FK
    timestamptz observed_at "UK cùng sensor_id"
    numeric value
    text level "binh_thuong|canh_bao|nguy_hiem"
    timestamptz received_at
  }
```

Mọi bảng có `created_at`, `updated_at` (trigger tự cập nhật), khóa chính UUID, chỉ mục GiST trên cột vị trí.

### Poka-yoke ở tầng dữ liệu
| Ràng buộc | Cách làm | Lỗi trả về |
|---|---|---|
| Tin kêu cứu phải có tọa độ | `location ... NOT NULL` | `23502` not_null_violation |
| Chặn tin trùng: cùng SĐT, cách tin còn mở (chưa `da_cuu`/`dong`) ≤ 200 m, trong 6 giờ | Trigger `incidents_no_duplicate` (INSERT và UPDATE vị trí/SĐT), khóa advisory theo SĐT để hai yêu cầu đồng thời không cùng lọt. Tham số trong bảng một dòng `incident_dedup_config` | `23505` unique_violation, constraint `incidents_no_duplicate`, DETAIL `incident_id=… distance_m=…`, HINT cập nhật tin cũ |
| Đã phân công / đang cứu phải có đội | CHECK `incidents_team_required` | `23514` |
| Điểm trú ẩn không quá sức chứa | CHECK `shelters_not_over_capacity` | `23514` |
| Xuất kho không quá tồn | Phiếu `supply_movements` cộng/trừ `supplies.quantity` trong cùng transaction, CHECK `quantity >= 0` | `23514` |
| Phiếu nhập/xuất không sửa/xóa (chỉ điền `ledger_*` một lần) | Trigger `supply_movements_immutable` | `23001` restrict_violation |

Vì sao trigger mà không phải exclusion constraint: điều kiện "trong 6 giờ" và "tin cũ còn mở" phụ thuộc thời điểm và trạng thái, exclusion constraint (GiST) chỉ so được giá trị cố định của hai dòng.

Phiếu nhập/xuất và leaf sổ cái (#28) không chứa dữ liệu cá nhân (D-007). Chuỗi đo cảm biến: bảng `sensor_readings` (#30, mục "Cảm biến" bên dưới).

### Chạy
```bash
make up        # tự chạy migration (container migrate) trước Hasura
make seed      # nạp dữ liệu giả, chạy lại được
make test-db   # 29 ca kiểm thử ràng buộc, ROLLBACK sau khi chạy (cũng nằm trong make smoke)
make migrate   # chạy lại migration bằng tay (không có file mới thì không làm gì)
```

Thêm thay đổi schema: tạo file mới `db/migrations/0003_<tên>.sql` (số tiếp theo), không sửa file đã chạy (migrate báo lỗi checksum). Cả file chạy trong một transaction nên không dùng `CREATE INDEX CONCURRENTLY`. Reset từ volume trống: `docs/architecture.md` mục 7.1.

## API GraphQL và phân quyền (`hasura/metadata/`, #26)

Tầng 2 gọi `POST http://<gateway>:9080/graphql` với `Authorization: Bearer <access token Keycloak>`. Vai trò lấy từ claim `x-hasura-default-role` của token (client có thể xin vai trò khác bằng header `X-Hasura-Role` nếu nằm trong `x-hasura-allowed-roles`). Luồng JWT → Hasura → lọc theo hàng: `docs/architecture.md` mục 3.4; cách metadata được áp khi khởi động: mục 7.2.

Tên field gốc trùng tên bảng (không tiền tố schema): `incidents`, `insert_incidents_one`, `update_incidents`, `incidents_aggregate`… Cột vị trí là kiểu `geography`, nhập/xuất bằng GeoJSON `{"type":"Point","coordinates":[kinh độ, vĩ độ]}`.

### Bảng quyền theo vai trò

R = đọc, C = tạo, U = sửa, D = xóa, – = không có (bảng không xuất hiện trong schema GraphQL của vai trò). Không vai trò nào được xóa tin kêu cứu, đội, điểm trú ẩn, hàng, phiếu (đóng/ngừng bằng trạng thái). `anonymous` (không có JWT) không có quyền gì, và APISIX đã chặn 401 trước đó.

| Bảng | `dieu-phoi` (cán bộ xã) | `cuu-ho` (thành viên đội) | `tinh-nguyen` |
|---|---|---|---|
| `incidents` | R mọi tin, mọi cột · C · U nội dung, `status`, `assigned_team_id` | R chỉ tin của **đội mình**, có SĐT để liên lạc · U chỉ cột `status`: từ `phan_cong`/`dang_cuu` sang `dang_cuu`/`da_cuu` | C (luôn `tiep_nhan`, chưa có đội) · R chỉ tin **mình tạo**, **không có** `reporter_phone`, `reporter_name`, `created_by` |
| `rescue_teams` | R · C · U | R đội mình · U vị trí, trạng thái đội mình | – |
| `team_members` | R · C (gán) · U (chuyển đội) · D (gỡ khỏi đội) | R dòng của mình | – |
| `shelters` | R · C · U | R | R |
| `supplies` | R · C · U thông tin mặt hàng (**không** sửa `quantity`) | – | R |
| `supply_movements` | R (lập phiếu qua API `POST /workflow/kho/phieu`, #28; phiếu bất biến, không U/D) | – | – |
| `sensors` | R · U tên, ngưỡng, bật/tắt | R | R thông tin công khai của trạm (#30) |
| `sensor_readings` | R (quan hệ `sensor`, `sensors.readings`) | R | R (tối đa 500 dòng/truy vấn) |
| `incident_media` (#27) | R mọi ảnh (quan hệ `incident`, `incidents.media`) | R ảnh của tin **đội mình** | R chỉ ảnh **mình tải lên**, không có `uploaded_by`, `uploader_role` |
| `incident_assignments` (#67) | R mọi lần giao (quan hệ `incident`, `team`, `incidents.assignments`) | R lần giao cho **đội mình** | – |
| `incident_dedup_config`, `assignment_queue` (#67) | không track: không vai trò nào thấy | | |

Cột hệ thống gán từ token, client không tự đặt được: `incidents.created_by` = `X-Hasura-User-Id` (sub Keycloak); `supply_movements.created_by` = tên đăng nhập trong JWT, API gán (#28). Tồn kho chỉ đổi qua phiếu nhập/xuất (trigger, sổ cái #28); cột `ledger_*` và giá trị đo cảm biến do dịch vụ nội bộ ghi (#28, #30), không qua vai trò người dùng.

**Thành viên đội:** `cuu-ho` thấy tin nhờ bảng `team_members (user_id = sub Keycloak, team_id)`: filter `assigned_team.members.user_id = X-Hasura-User-Id`. Điều phối gán/chuyển đội trong ứng dụng, có hiệu lực ngay ở truy vấn sau (không chờ token mới):

```graphql
mutation GanDoi($u: String!, $t: uuid!) {
  insert_team_members_one(object: {user_id: $u, team_id: $t},
    on_conflict: {constraint: team_members_pkey, update_columns: [team_id]}) { user_id team_id }
}
```

User mẫu có `id` cố định trong `keycloak/realm.json` nên seed gán sẵn `cuuho01` vào "Đội ca nô Biên phòng" trên volume trống. Realm import từ trước #26 có `sub` ngẫu nhiên: gán lại bằng mutation trên (`scripts/smoke-hasura.sh` làm vậy).

Truy vấn mẫu: tin kêu cứu trong bán kính 500 m (PostGIS qua Hasura, vẫn áp quyền của vai trò):

```graphql
query GanToi($p: geography!) {
  incidents(where: {location: {_st_d_within: {from: $p, distance: 500}}}) { id description status }
}
# biến: {"p": {"type": "Point", "coordinates": [108.1035, 15.8502]}}
```

Sửa quyền: sửa file bảng trong `hasura/metadata/databases/default/tables/`, `docker compose restart hasura`, chạy `bash scripts/smoke-hasura.sh`. Lệch DB (bảng/cột không có) thì Hasura dừng khởi động, xem `docker compose logs hasura`.

Truy vấn SQL mẫu: đội sẵn sàng gần mỗi tin kêu cứu mới nhất (KNN trên chỉ mục GiST):

```sql
SELECT i.description, t.name, round(ST_Distance(t.location, i.location)) AS met
  FROM cuu_tro.incidents i
  CROSS JOIN LATERAL (SELECT name, location FROM cuu_tro.rescue_teams
                       WHERE status = 'san_sang' AND location IS NOT NULL
                       ORDER BY location <-> i.location LIMIT 1) t
 WHERE i.status = 'tiep_nhan';
```

## Workflow (`workflow/`, #29)

Backend nghiệp vụ của ứng dụng (D-008), không thuộc lõi. Hai dịch vụ dùng chung một image (`python:3.12-slim`, phụ thuộc cài từ `requirements.txt` có hash, sinh từ `uv.lock`):

| Dịch vụ | Lệnh | Gọi tới |
|---|---|---|
| `cuu-tro-worker` | `python -m cuu_tro_workflow.worker` | Temporal (task queue `cuu-tro`), PostgreSQL bằng role `cuu_tro_app` (`APP_DB_URL` từ OpenBao qua `bao-agent-cuu-tro`), NATS (báo điều phối, #67). Cùng tiến trình: bộ khởi chạy tự động `khoi_chay.py` (#67) |
| `cuu-tro-api` | `uvicorn cuu_tro_workflow.api:app --root-path /workflow` | Temporal (start/signal/query), Hasura qua gateway `/graphql` bằng JWT người dùng. Không mở cổng ra host. Cấp token kết nối Centrifugo (#68) |
| `cuu-tro-thong-bao` | `python -m cuu_tro_workflow.thong_bao_cau_noi` | Cầu nối thông báo realtime (#68): consumer JetStream `realtime-dieu-phoi`, `realtime-canh-bao` → HTTP API Centrifugo (mạng nội bộ) → kênh `dieu-phoi`. Không đọc CSDL |

Cách backend gọi lõi và vì sao: `docs/architecture.md` mục 7.3.

### `PhanCongCuuHo`: tiếp nhận → phân công → nhận → xác nhận → đóng (#29, #67)

**Tự khởi chạy (#67).** Không ai phải bấm "phân công": mỗi tin `tiep_nhan` mới (từ Hasura, API kêu cứu #66 hay SQL) được trigger `incidents_enqueue_assignment` ghi vào outbox `assignment_queue` **cùng transaction** rồi `pg_notify('cuu_tro_tin_moi')`. Bộ khởi chạy `khoi_chay.py` chạy trong tiến trình worker, `LISTEN` kênh đó và quét lại mỗi `PHAN_CONG_QUET_GIAY` giây (phòng lỡ NOTIFY), lấy tin khẩn trước (`urgency_rank`, rồi thời điểm tạo), `FOR UPDATE SKIP LOCKED`, khởi chạy workflow id **`phan-cong-<incident_id>`** rồi đánh dấu `started_at`. Gọi lại an toàn: đang chạy → dùng lại (`USE_EXISTING`), đã chạy xong → Temporal từ chối (`REJECT_DUPLICATE`). Seed dữ liệu mẫu đặt `SET LOCAL cuu_tro.tu_phan_cong = off` nên tin mẫu không tự chạy. Tắt cả cơ chế: `PHAN_CONG_TU_DONG=0` (vẫn khởi chạy tay qua API).

```mermaid
stateDiagram-v2
  [*] --> doc_tin: tin mới (outbox, tự động)<br/>hoặc POST /workflow/phan-cong/{id} (dieu-phoi)
  doc_tin --> xong_bo_qua: tin không có / không ở tiep_nhan
  doc_tin --> tim_doi
  tim_doi --> tim_doi: chưa có đội sẵn sàng / mọi đội phải nhường<br/>timer PHAN_CONG_CHO_TIM_LAI_GIAY
  tim_doi --> xong_bao_dieu_phoi: hết PHAN_CONG_SO_LAN_TIM_DOI vòng (khong_co_doi)
  tim_doi --> cho_nhan: gan_doi: đội san_sang gần nhất, không bị giữ cho tin khẩn hơn
  cho_nhan --> tim_doi: signal tu_choi / quá hạn nhận theo urgency<br/>gỡ đội, ghi lịch sử, giao đội kế tiếp
  cho_nhan --> xong_bao_dieu_phoi: hết PHAN_CONG_SO_LAN_GIAO_TOI_DA lần giao (het_lan_giao)
  cho_nhan --> xong_huy: signal huy (dieu-phoi), gỡ đội
  cho_nhan --> cho_xac_nhan: signal nhan_nhiem_vu<br/>tin dang_cuu
  cho_xac_nhan --> ket_thuc: signal xac_nhan_da_cuu
  cho_xac_nhan --> xong_bao_dieu_phoi: quá PHAN_CONG_HAN_XAC_NHAN_GIAY (qua_han_xac_nhan)
  ket_thuc --> [*]: tin da_cuu → dong, đội san_sang
  xong_bo_qua --> [*]
  xong_huy --> [*]: tin tiep_nhan, đội san_sang
  xong_bao_dieu_phoi --> [*]: sự kiện NATS cuu-tro.dieu-phoi.can-xu-ly.{id}
```

| Bước | Activity (I/O) | Ghi chú |
|---|---|---|
| `doc_tin` | `SELECT` tin (kèm `urgency`) | Chỉ phân công tin `tiep_nhan`; hạn nhận lấy theo `urgency` của tin |
| `tim_doi` | `tim_doi_ung_vien`: đánh dấu tin đang tìm đội (`assignment_queue.seeking_at`), tối đa 10 đội `san_sang` có vị trí trong `PHAN_CONG_BAN_KINH_M` (mặc định 20 km), xếp theo `location <-> incident.location` | Chọn đội: `logic.chon_doi_gan_nhat` (gần nhất; hòa thì đội đông người hơn, rồi theo id), bỏ các đội đã từ chối/quá hạn với tin này |
| `gan_doi` | Một transaction: khóa tin, **luật ưu tiên** `team_reserved_for_more_urgent`, `UPDATE` đội chỉ khi còn `san_sang`, ghi `incident_assignments` (`cho_nhan`, `deadline_at`) | Trả `da_gan` · `bi_gianh` (đội vừa bị tin khác lấy) · `nhuong` (đội đang được giữ cho tin khẩn hơn) · `tin_da_doi` |
| `cho_nhan` | – | Timer bền của Temporal (`wait_condition` có hạn), không vòng lặp sleep. Signal `nhan_nhiem_vu` / `tu_choi` mang `doi_id`: phản hồi muộn của đội đã bị thay bị bỏ qua |
| (từ chối/quá hạn/hủy) | `go_doi`: tin `phan_cong → tiep_nhan`, đội về `san_sang`, lịch sử `tu_choi`/`qua_han`/`huy` | Đội đã thử không được giao lại cho cùng tin |
| (nhận) | `nhan_nhiem_vu`: tin `phan_cong → dang_cuu`, lịch sử `da_nhan` | Sau khi đội nhận, signal `huy` không còn tác dụng (đội đang ở hiện trường) |
| `cho_xac_nhan` | – | Signal `xac_nhan_da_cuu`; quá hạn (mặc định 6 giờ) → báo điều phối, tin giữ `dang_cuu` |
| `ket_thuc` | Tin `da_cuu` → `dong`, đội về `san_sang` | Mọi activity chạy lại được (Temporal thử lại 5 lần); lỗi nghiệp vụ không thử lại |
| báo điều phối | `bao_dieu_phoi`: JetStream `cuu-tro.dieu-phoi.can-xu-ly.<incident_id>` (stream `CUU_TRO_DIEU_PHOI`), `Nats-Msg-Id` = run + lý do | Chỉ id tin, urgency, lý do, số lần giao: không có SĐT/tên. NATS lỗi kéo dài không làm hỏng kết quả workflow |

**Ưu tiên theo `urgency`** (`khan_cap` > `cao` > `trung_binh` > `thap`, hàm SQL `urgency_rank`):
1. Bộ khởi chạy lấy tin khẩn trước khi có nhiều tin cùng lúc.
2. Workflow và activity mang `priority_key` của Temporal (1 = khẩn nhất): máy chủ Temporal đưa việc của tin khẩn cho worker trước khi worker bận.
3. Quan trọng nhất là **giành đội**: khi đội khan hiếm, `gan_doi` của một tin không lấy đội nếu có tin **khẩn hơn hẳn**, còn `tiep_nhan`, đang tìm đội (`seeking_at` trong 2 chu kỳ tìm lại + 30 giây) và đội đó nằm trong bán kính của tin khẩn hơn. Tin kém khẩn đi tìm đội kế tiếp hoặc chờ vòng sau. Không giành lại đội đã giao (không ngắt nhiệm vụ đang làm); workflow chết thì `seeking_at` tự hết hạn, không ai bị chặn mãi.

**Hạn nhận nhiệm vụ** theo urgency: `PHAN_CONG_HAN_NHAN_GIAY_KHAN_CAP` (mặc định 300), `_CAO` (600), `_TRUNG_BINH` (900), `_THAP` (1800). Tối đa `PHAN_CONG_SO_LAN_GIAO_TOI_DA` (mặc định 3) lần giao, mỗi lần một đội, rồi báo điều phối.

Lịch sử giao (`incident_assignments`): mỗi lần giao một dòng (đội, lần, urgency, khoảng cách, `assigned_at`, `deadline_at`, kết quả, người phản hồi). GraphQL chỉ đọc: `dieu-phoi` mọi dòng, `cuu-ho` dòng của đội mình, `tinh-nguyen` không; quan hệ `incidents.assignments`.

Luồng trạng thái tin hợp lệ (`logic.CHUYEN_TRANG_THAI`): `tiep_nhan → phan_cong | dong`, `phan_cong → dang_cuu | da_cuu | tiep_nhan` (gỡ đội, #67), `dang_cuu → da_cuu`, `da_cuu → dong`. `cuu-ho` vẫn tự chuyển `phan_cong → dang_cuu` qua GraphQL (#26) khi bắt đầu cứu, workflow chấp nhận cả hai.

`Hello`: workflow một activity, kiểm đường đi gateway → API → Temporal → worker.

### API (qua gateway, `Authorization: Bearer <access token Keycloak>`)

| Phương thức, đường dẫn | Vai trò | Kết quả |
|---|---|---|
| `POST /workflow/hello` body `{"ten": "…"}` (tùy chọn) | mọi vai trò | `200 {"workflow_id", "ket_qua", "nguoi_goi"}` |
| `POST /workflow/phan-cong/{incident_id}` | `dieu-phoi` | Khởi chạy tay (tin mới đã tự chạy; dùng khi luồng tự động đã dừng và báo điều phối). `202 {"workflow_id": "phan-cong-<incident_id>", "run_id", "incident_id"}` · `404` tin không có · `409` tin không ở `tiep_nhan` hoặc luồng đang chạy |
| `GET /workflow/{workflow_id}` | `dieu-phoi`; `cuu-ho` của đội được giao | `200 {"workflow_id", "trang_thai": "RUNNING\|COMPLETED\|…", "chi_tiet": {buoc, urgency, han_nhan_giay, doi_id, doi_ten, khoang_cach_m, so_lan_tim, giao: [{lan, doi_id, doi_ten, ket_qua, …}], da_bao_dieu_phoi, xac_nhan, ket_qua, lich_su}}` |
| `POST /workflow/{workflow_id}/nhan` body `{"ghi_chu": "…"}` (tùy chọn) | `dieu-phoi`; `cuu-ho` của đội được giao | `202` · `409` không ở bước `cho_nhan` hoặc nhiệm vụ đã giao cho đội khác |
| `POST /workflow/{workflow_id}/tu-choi` body `{"ghi_chu": "…"}` (tùy chọn) | `dieu-phoi`; `cuu-ho` của đội được giao | `202` (workflow giao đội kế tiếp) · `409` như trên |
| `POST /workflow/{workflow_id}/huy` body `{"ly_do": "…"}` (tùy chọn) | `dieu-phoi` | `202` (gỡ đội nếu đang giao, tin về `tiep_nhan`) · `409` đội đã nhận hoặc workflow đã xong |
| `POST /workflow/{workflow_id}/xac-nhan` body `{"ghi_chu": "…"}` (tùy chọn) | `dieu-phoi`; `cuu-ho` của đội được giao | `202` (ở `cho_nhan` thì coi như đã nhận) · `409` workflow không chờ nhận/xác nhận |
| `GET /workflow/realtime/token` (#68) | `dieu-phoi` (`quan-tri` khi realm có) | `200 {"token", "han_giay", "kenh": ["dieu-phoi"]}`, `Cache-Control: no-store`: token HS256 kết nối Centrifugo qua `ws://<gateway>/realtime/websocket` (chỉ `sub` + kênh server-side, `REALTIME_TOKEN_HAN_GIAY` giây) · `403` vai khác · `503` chưa có khóa ký |

Không token → `401` ở APISIX; vai trò không đủ → `403` ở API; `cuu-ho` đội khác → `403` (API hỏi `incidents_by_pk` qua `/graphql` bằng JWT người dùng, luật lọc theo đội của Hasura trả `null`).

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/realms/disaster/protocol/openid-connect/token \
  -d grant_type=password -d client_id=dxos-dev-cli -d username=dieuphoi01 \
  --data-urlencode password="$KC_DEMO_USER_PASSWORD" | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
curl -s -X POST -H "Authorization: Bearer $TOKEN" http://localhost:9080/workflow/phan-cong/b0000000-0000-4000-8000-000000000004
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:9080/workflow/phan-cong-b0000000-0000-4000-8000-000000000004
```

Theo dõi trong Temporal không cần UI: `docker compose exec temporal temporal workflow list --address temporal:7233`.

### Phát triển

```bash
cd apps/cuu-tro/workflow
uv sync                 # tạo .venv theo uv.lock
uv run pytest -q        # hoặc từ gốc repo: make test-py
# Đổi phụ thuộc: sửa pyproject.toml rồi
uv lock && uv export --frozen --no-dev --no-emit-project -o requirements.txt
```

Test: logic thuần (chọn đội, chuyển trạng thái), workflow trên máy chủ test của `temporalio` (tự tua thời gian: quá hạn nhận → phân công lại, hạn theo urgency, hết lần giao → báo điều phối, tin khẩn cấp được đội trước, từ chối, hủy, tự khởi chạy không trùng; activity thay bằng bản giả trong bộ nhớ), API nhận/từ chối/hủy với Hasura và Temporal giả, kiểm JWT/vai trò của API bằng khóa RSA sinh tại chỗ. Luật SQL (outbox, `urgency_rank`, nhường đội, lịch sử giao, quyền `cuu_tro_app`): `db/tests/0007_phan_cong_tu_dong.sql` (`make test-db`). Lần chạy đầu `temporalio` tải máy chủ test về thư mục tạm. Kiểm thử thật qua gateway: `scripts/smoke-workflow.sh` (trong `make smoke`).

## Ảnh hiện trường (`workflow/cuu_tro_workflow/anh.py`, `s3.py`, #27)

Ảnh chụp tại hiện trường gắn với tin kêu cứu. Nội dung ảnh nằm trên SeaweedFS (bucket riêng tư `cuu-tro-media`), siêu dữ liệu ở bảng `incident_media` (migration `0005`). **Client Tầng 2 không bao giờ cầm khóa S3.**

**Thiết kế: tải lên qua API (cách a), xem bằng link presigned ngắn hạn (cách b).**

| Việc | Cách làm | Vì sao |
|---|---|---|
| Tải lên | Client gửi nội dung ảnh trong body `POST /workflow/tai-len/su-co/{incident_id}/anh`; `cuu-tro-api` kiểm quyền, kích thước, magic bytes, tính SHA-256 rồi tự ghi S3 bằng khóa của ứng dụng (từ OpenBao) | Phải **đọc nội dung** mới kiểm được magic bytes và kích thước thật; URL presigned PUT để client ghi thẳng S3 thì S3 nhận mọi thứ client gửi (HTML, tệp thực thi đổi đuôi .jpg). Một chỗ ghi duy nhất cũng là chỗ gắn quét ClamAV sau này |
| Xem | API kiểm quyền theo hàng rồi ký URL GET presigned cho **đúng một object**, hạn mặc định 5 phút (`ANH_LINK_HAN_GIAY`, client xin ngắn hơn bằng `?han_giay=`). Client mở `<gateway>/files/<bucket>/<key>?X-Amz-...` **kèm JWT** | Ảnh đi thẳng từ S3 qua gateway, API không phải chuyển tiếp byte. Link lộ ra ngoài vẫn cần JWT hợp lệ (APISIX) và hết hạn nhanh; đổi key/phương thức → S3 trả 403 |
| Route `/files/*` | Chỉ `GET`/`HEAD`. Gateway kiểm JWT (biết "đã đăng nhập"), S3 kiểm chữ ký (biết "được xem đúng object này đến lúc nào") | Kiểm quyền theo object nằm ở chữ ký: chỉ API giữ khóa, chỉ ký sau khi Hasura xác nhận người dùng thấy dòng `incident_media` đó. Không có đường ghi/xóa S3 từ ngoài |
| Khóa S3 | Định danh `cuu-tro-app` (`secret/app/cuu-tro/s3`) chỉ `Read`/`Write`/`List` bucket `cuu-tro-*`, không `Admin`; chỉ `cuu-tro-api` có (volume tmpfs riêng) | Lộ khóa ứng dụng không đụng được bucket khác, không tạo/xóa bucket. Khóa quản trị `secret/core/s3` không cấp cho ứng dụng |
| Thứ tự ghi | Kiểm quyền → đọc body (dừng ngay khi vượt giới hạn) → magic bytes → PUT S3 (ký kèm SHA-256 nội dung) → `INSERT incident_media`. CSDL lỗi → xóa object vừa ghi | Không có dòng trỏ tới object không có, không để object mồ côi |
| Tên object | `su-co/<incident_id>/<media_id>.<jpg\|png\|webp>`, đuôi theo loại thật | Không dùng tên tệp của người dùng (chặn path traversal, lộ thông tin) |
| Quét mã độc | Cột `scan_status` (mặc định `chua_quet`) chừa chỗ; ClamAV ở biên (profile `sec`) là việc sau | |

### Quyền theo vai trò

Quyền theo hàng không viết lại trong API: API hỏi Hasura qua gateway `/graphql` bằng JWT + vai trò của chính người dùng (`incidents_by_pk`, `incident_media_by_pk`), Hasura trả `null` nghĩa là không thấy. Người dùng có nhiều vai trò thì dùng vai trò rộng nhất (`dieu-phoi` > `cuu-ho` > `tinh-nguyen`).

| Vai trò | Tải ảnh lên | Liệt kê ảnh của tin | Lấy link xem một ảnh |
|---|---|---|---|
| `dieu-phoi` | Mọi tin (tin `dong` → 409, tin không có → 404) | Mọi tin | Mọi ảnh |
| `cuu-ho` | Tin phân công cho **đội mình**; đội khác → 403 | Tin của đội mình; đội khác → 403 | Ảnh của tin đội mình; khác → 403 |
| `tinh-nguyen` | Chỉ tin **mình vừa tạo**, khi tin còn `tiep_nhan` (lúc kêu cứu); tin khác hoặc đã phân công → 403 | Không được (403) | Chỉ ảnh **chính mình tải lên**; ảnh người khác → 403 |

### API (qua gateway, `Authorization: Bearer <access token Keycloak>`)

| Phương thức, đường dẫn | Kết quả |
|---|---|
| `POST /workflow/tai-len/su-co/{incident_id}/anh`, body = nội dung ảnh | `201 {id, incident_id, object_key, content_type, size_bytes, sha256, uploaded_by, uploader_role, uploaded_at, scan_status, link}` · `400` body rỗng · `413` quá `ANH_MAX_BYTES` (mặc định 10 MiB; gateway chặn trước ở `GW_UPLOAD_MAX_BODY_BYTES`, 20 MiB) · `415` không phải JPEG/PNG/WebP theo magic bytes |
| `GET /workflow/su-co/{incident_id}/anh` | `200 {incident_id, anh: [{id, content_type, size_bytes, sha256, uploaded_by, uploaded_at, scan_status, link}]}` |
| `GET /workflow/anh/{media_id}/link?han_giay=N` | `200 {…, link: {url, han_giay, het_han_luc}}` · `422` `han_giay` ngoài 1..`ANH_LINK_HAN_GIAY` |

`link.url` mở bằng `GET` kèm header `Authorization` (trình duyệt: `fetch` có header rồi `URL.createObjectURL`, không dùng thẳng trong `<img src>`). Mọi phản hồi có `Cache-Control: no-store`. Loại ảnh lấy từ magic bytes: `Content-Type` và đuôi tên tệp của client bị bỏ qua.

```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" --data-binary @anh.jpg \
  http://localhost:9080/workflow/tai-len/su-co/b0000000-0000-4000-8000-000000000002/anh
URL=$(curl -s -H "Authorization: Bearer $TOKEN" http://localhost:9080/workflow/su-co/b0000000-0000-4000-8000-000000000002/anh \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["anh"][0]["link"]["url"])')
curl -s -H "Authorization: Bearer $TOKEN" "$URL" -o anh-tai-ve.jpg
```

Kiểm thử: `tests/test_cuu_tro_anh.py` (ký SigV4 khớp ví dụ chính thức của AWS, magic bytes, luật quyền, endpoint với Hasura/S3/CSDL giả); `scripts/smoke-anh.sh` (trong `make smoke`) gọi thật qua APISIX. Luồng dữ liệu: `docs/architecture.md` mục 7.5.

## Sổ cái minh bạch: phiếu nhập/xuất → sổ cái → trang công khai (`workflow/cuu_tro_workflow/so_cai.py`, #28)

Mỗi phiếu nhập/xuất hàng cứu trợ được ghi thành một lá của sổ cái minh bạch của lõi (`core/ledger`, Tessera, D-007). Người dân, nhà tài trợ tra mã phiếu trên trang công khai, hoặc tự tải checkpoint + tile để kiểm, không cần tin hệ thống. Kiến trúc lõi: `docs/architecture.md` mục 5.1.

**Luồng ghi** (`POST /workflow/kho/phieu`, chỉ `dieu-phoi`):

1. `cuu-tro-api` kiểm JWT + vai trò, chặn ghi chú có dãy số dạng SĐT/CCCD (ghi chú hiện công khai) → 422.
2. `INSERT supply_movements` bằng role `cuu_tro_app` (migration `0006`); trigger cộng/trừ tồn kho (chạy với quyền chủ bảng), xuất quá tồn → 409. `created_by` = tên đăng nhập, chỉ nằm trong CSDL.
3. **Bản ghi chuẩn hóa**: `{loai: "cuu-tro.phieu-kho/v1", id, supply_id, direction, quantity ("10.00"), note, shelter_id, created_at (UTC, 6 chữ số micro giây)}`, mọi giá trị là chuỗi/null, **không có người lập phiếu**. JSON chuẩn tắc (khóa sắp xếp, không khoảng trắng, UTF-8; trùng RFC 8785 cho object chỉ gồm chuỗi) → SHA-256.
4. Gửi lá `{type: "cuu-tro.phieu-kho", ref: <mã phiếu>, sha256, attrs: {direction, quantity, at}}` tới `core/ledger` trong mạng nội bộ, kèm token ghi của ứng dụng (OpenBao `secret/app/cuu-tro/ledger`). Ledger trả `index` sau khi checkpoint đã ký chứa lá.
5. Điền `ledger_index`, `ledger_leaf_hash` (RFC 6962), `ledger_logged_at` đúng một lần (trigger chặn sửa lại).

Sổ cái lỗi ở bước 4 → phiếu vẫn được lập (202, `so_cai.trang_thai = chua_ghi_so`); gọi `POST /workflow/kho/phieu/{mã}/ghi-so` để ghi lại. Gửi lại an toàn: cùng phiếu → cùng lá → sổ cái chống trùng trả index cũ. Phiếu không còn lập được qua Hasura (bỏ quyền insert): mọi phiếu đều đi qua luồng ghi sổ.

**Trang công khai** `GET /workflow/minh-bach/phieu/{mã}` (không đăng nhập, route gateway `/workflow/minh-bach/*`): API đọc phiếu trong CSDL, dựng lại bản ghi chuẩn hóa, băm lại, lấy lá + inclusion proof + checkpoint từ sổ cái rồi tự kiểm: chữ ký checkpoint (Ed25519, khóa công khai của sổ cái), lá đúng loại/mã phiếu, SHA-256 trong lá = SHA-256 vừa tính, leaf hash = giá trị lưu trong CSDL, proof dẫn tới root của checkpoint (RFC 9162).

| `trang_thai` | Nghĩa |
|---|---|
| `da_xac_minh` | Bản ghi trong CSDL khớp lá trên sổ cái, lá nằm trong checkpoint đã ký |
| `khong_khop` | Lệch ở một bước (`chi_tiet` nói rõ): bản ghi bị sửa sau khi ghi sổ, leaf hash trong CSDL bị đổi, hoặc sổ cái/chữ ký không hợp lệ |
| `chua_ghi_so` | Phiếu chưa lên sổ cái (gọi lại `ghi-so`) |
| `khong_kiem_duoc` | Không gọi được sổ cái lúc này |

Phản hồi: `ma`, `trang_thai`, `chi_tiet`, `ban_ghi_chuan_hoa` (đúng object đã băm), `sha256`, `hien_thi` (tên hàng, đơn vị, kho, điểm nhận: chỉ để hiển thị, không nằm trong bản ghi đã băm), `so_cai` (`index`, `leaf_hash`, `logged_at`, `checkpoint`, `la`). Không có người lập phiếu, `Cache-Control: no-store`.

**Tự kiểm chứng** (không tin API): lưu phản hồi trang công khai rồi chạy CLI của lõi, CLI chỉ dùng checkpoint + tile công khai, tự dựng proof:

```bash
curl -s http://localhost:9080/workflow/minh-bach/phieu/<mã> -o phieu.json
VK=$(curl -s http://localhost:9080/ledger/verifier)   # nên lấy khóa công khai từ nguồn độc lập
INDEX=$(python3 -c 'import json; print(json.load(open("phieu.json"))["so_cai"]["index"])')
# Có Go: (cd core/ledger && go run ./cmd/ledger-verify -log http://localhost:9080/ledger/ -verifier "$VK" -index "$INDEX" -record ../../phieu.json)
# Không có Go: dùng image ledger (đã build khi make up), chỉ thấy gateway
docker run --rm -i --network disaster-dxos_default --entrypoint /ledger-verify disaster-dxos/ledger:0.1.0 \
  -log http://apisix:9080/ledger/ -verifier "$VK" -index "$INDEX" -record - < phieu.json
```

Kết quả `ĐÃ XÁC MINH` (mã 0) hoặc `KHÔNG KHỚP` kèm lý do (mã 1).

| Phương thức, đường dẫn | Quyền | Kết quả |
|---|---|---|
| `POST /workflow/kho/phieu` body `{supply_id, direction: nhap\|xuat, quantity (> 0, 2 chữ số thập phân), note?, shelter_id?}` | `dieu-phoi` | `201 {ban_ghi_chuan_hoa, sha256, so_cai: {trang_thai: da_ghi, index, leaf_hash, tree_size, logged_at}}` · `202` sổ cái lỗi (`chua_ghi_so`) · `401/403` · `404` không có hàng/điểm nhận · `409` xuất quá tồn · `422` dữ liệu sai, ghi chú có SĐT/CCCD |
| `POST /workflow/kho/phieu/{mã}/ghi-so` | `dieu-phoi` | `200` (đã ghi, hoặc ghi lại thành công) · `503` sổ cái vẫn lỗi · `404` |
| `GET /workflow/minh-bach/phieu/{mã}` | Công khai | `200` như trên · `404` mã không có/sai dạng |

Kiểm thử: `tests/test_cuu_tro_so_cai.py` (14 test: vector JSON chuẩn tắc chung với Go, inclusion proof mọi kích thước cây 1–17, chữ ký checkpoint, endpoint với CSDL + sổ cái giả, sửa CSDL → không khớp, sổ cái tắt → ghi lại); `db/tests/0006_so_cai_phieu_kho.sql` (16 ca quyền); `scripts/smoke-ledger.sh` (47 ca qua APISIX, trong `make smoke`).

## Cảm biến mực nước (`workflow/cuu_tro_workflow/cam_bien*.py`, `gia_lap.py`, #30)

Luồng IT/OT của ứng dụng: thiết bị (ở đây là bộ giả lập) gửi MQTT vào NATS của lõi, consumer của ứng dụng ghi chuỗi đo vào PostgreSQL và phát cảnh báo khi nước vượt ngưỡng. Lõi chỉ cung cấp NATS có xác thực (user `cuu-tro-thiet-bi` chỉ gửi được vào `cuu-tro.>`, chỉ qua MQTT), không biết topic nào. Vì sao làm vậy và ánh xạ nguyên lý B2: `docs/architecture.md` mục 7.4.

```mermaid
flowchart LR
  gl["cuu-tro-gia-lap<br/>(hoặc trạm đo thật)"] -->|"MQTT QoS 1, user cuu-tro-thiet-bi<br/>cuu-tro/cam-bien/AL-MN-02/muc-nuoc"| nats["NATS :1883 (lõi)<br/>topic → subject<br/>cuu-tro.cam-bien.AL-MN-02.muc-nuoc"]
  nats --> st[("Stream CUU_TRO_CAM_BIEN<br/>file, 7 ngày, 256 MiB")]
  st -->|"consumer bền ghi-csdl<br/>pull, ack thủ công"| cs["cuu-tro-cam-bien<br/>kiểm payload, so ngưỡng"]
  cs -->|"role cuu_tro_app, 1 transaction"| db[("sensor_readings<br/>sensors.last_*")]
  cs -->|"mức tăng lên canh_bao / nguy_hiem<br/>Nats-Msg-Id chống trùng"| cb[("Stream CUU_TRO_CANH_BAO<br/>cuu-tro.canh-bao.cam-bien.&lt;ma_tram&gt;")]
  cb -.->|"tuần 4–5"| ag["agent cảnh báo<br/>Temporal → Telegram / Centrifugo"]
  db -->|"/graphql qua APISIX"| ui["dieu-phoi · cuu-ho · tinh-nguyen"]
```

### Topic và payload

| | Giá trị |
|---|---|
| Topic MQTT | `cuu-tro/cam-bien/<ma_tram>/<dai_luong>`, `<dai_luong>` ∈ `muc-nuoc` (cm), `luong-mua` (mm), `gio` (m/s); `<ma_tram>` theo `sensors.code` (`^[A-Z0-9][A-Z0-9_-]{1,31}$`) |
| Subject NATS | như topic, `/` thành `.`: `cuu-tro.cam-bien.AL-MN-02.muc-nuoc` |
| Payload | `{"ma_tram": "AL-MN-02", "gia_tri": 215.3, "don_vi": "cm", "thoi_diem": "2026-10-20T08:00:00.000+07:00"}` |
| Sự kiện cảnh báo | subject `cuu-tro.canh-bao.cam-bien.<ma_tram>`, payload `{"loai": "vuot_nguong", "ma_tram", "ten_tram", "dai_luong", "muc", "muc_truoc", "gia_tri", "nguong", "don_vi", "thoi_diem"}` |

Kiểm tra bản tin (`cam_bien.phan_tich`, có pytest): `ma_tram` trùng topic; `don_vi` đúng đại lượng; `gia_tri` là số hữu hạn trong [-1000, 100000], làm tròn 2 chữ số; `thoi_diem` ISO 8601 **có múi giờ**, không sớm hơn 7 ngày, không muộn hơn 5 phút so với lõi; tối đa 4 KiB; trạm phải có trong `sensors`, đang bật, đúng loại/đơn vị. Sai thì consumer bỏ bản tin (`term`, không giao lại) và ghi log cảnh báo; lỗi CSDL thì `nak` để JetStream giao lại sau 5 giây (tối đa 5 lần).

Mức: `nguy_hiem` khi `gia_tri >= danger_threshold`, `canh_bao` khi `>= warning_threshold`, ngược lại `binh_thuong` (ngưỡng NULL thì bỏ qua mức đó). Chỉ phát cảnh báo khi mức **tăng** so với lần đo liền trước và bản tin là lần đo mới nhất: nước vẫn trên ngưỡng hay rút xuống không phát lại, bản tin gửi bù cũ không phát. Bản tin giao lại (chưa kịp ack) không tạo dòng trùng (`UNIQUE (sensor_id, observed_at)`) và không phát cảnh báo trùng (`Nats-Msg-Id` trong cửa sổ 2 phút).

Stream và consumer khai báo ở `nats/streams.json`; `cuu-tro-cam-bien` tạo hoặc cập nhật khi khởi động.

### Chạy bộ giả lập

```bash
make up                     # lõi + app: NATS có xác thực, consumer cuu-tro-cam-bien
make gia-lap                # một bản tin bình thường cho mỗi trạm mẫu (AL-MN-01, AL-MN-02, AL-LM-01)
make gia-lap-vuot-nguong    # một bản tin trên ngưỡng nguy hiểm cho mỗi trạm → sự kiện cảnh báo
# Chạy liên tục (mỗi 10 giây; kịch bản vuot-nguong: nước lên dần trong 6 chu kỳ rồi giữ)
GIA_LAP_KICH_BAN=vuot-nguong docker compose --profile core --profile app --profile gia-lap up -d cuu-tro-gia-lap
docker compose --profile core --profile app run --rm --no-deps cuu-tro-gia-lap python -m cuu_tro_workflow.gia_lap --help
```

Bộ giả lập chạy trong container chỉ có mật khẩu thiết bị (`bao-agent-cuu-tro` render vào volume tmpfs riêng `secrets-cuu-tro-thiet-bi`). Chạy từ máy host thì dùng cổng `127.0.0.1:${NATS_MQTT_PORT}` (thiết bị trong LAN: `NATS_MQTT_BIND=0.0.0.0`, chưa TLS):

```bash
export MQTT_PASSWORD=$(curl -s -H "X-Vault-Token: $(cat .data/openbao/root.token)" \
  http://127.0.0.1:8200/v1/secret/data/app/cuu-tro/nats | python3 -c 'import sys,json; print(json.load(sys.stdin)["data"]["data"]["device_password"])')
cd apps/cuu-tro/workflow && MQTT_HOST=127.0.0.1 MQTT_USERNAME=cuu-tro-thiet-bi uv run python -m cuu_tro_workflow.gia_lap --mot-lan
```

Xem kết quả:

```bash
docker compose logs -f cuu-tro-cam-bien     # "cảnh báo AL-MN-02: binh_thuong → nguy_hiem (420.0 cm)"
docker compose exec cuu-tro-cam-bien bash /opt/dxos/env-from-files.sh /run/secrets/dxos \
  python -m cuu_tro_workflow.cam_bien_consumer canh-bao-cuoi AL-MN-02
```

```graphql
query ChuoiDo { sensors { code last_value last_observed_at
  readings(order_by: {observed_at: desc}, limit: 10) { observed_at value level } } }
```

Kiểm thử thật: `scripts/smoke-cam-bien.sh` (trong `make smoke`). NGSI-LD (Scorpio, bản sao số trạm đo) nối vào luồng này ở tuần 4: consumer thứ hai trên cùng stream cập nhật thực thể `sensors.ngsi_ld_id`, không đổi thiết bị hay topic.
