<!-- SPDX-License-Identifier: Apache-2.0 -->
# apps/muon-thiet-bi: module mẫu "Mượn trả thiết bị dùng chung"

Module thứ hai, nhỏ, **khác đề tài cứu trợ** (D-008 mục 3). Mục đích: chứng minh lõi `core/` dùng lại được cho nghiệp vụ khác mà không sửa lõi. Nghiệp vụ: tổ dân phố hoặc trường học có kho thiết bị dùng chung (máy phát điện, máy bơm, loa kéo, máy chiếu); người dân mượn, người quản lý ghi nhận trả.

Cách viết một module như thế này: [`docs/viet-module.md`](../../docs/viet-module.md).

| Tệp | Nội dung |
|---|---|
| `compose.yaml` | `services: {}`: module **không có backend**, chỉ dùng lõi qua GraphQL `/graphql` |
| `keycloak/realm.json` | Realm `thiet-bi`, 2 vai `quan-ly`, `nguoi-muon`; client `dxos-gateway` (APISIX), `dxos-dev-cli` (chỉ dev), mapper claim Hasura; user mẫu `quanly01`, `nguoimuon01`, `nguoimuon02` (mật khẩu `KC_DEMO_USER_PASSWORD`) |
| `db/migrations/0001_thiet_bi.sql` | Schema `muon_thiet_bi`: bảng `devices`, `loans` + Poka-yoke |
| `db/seed/0001_kho_mau.sql` | 4 thiết bị giả (một máy chiếu đang hỏng) |
| `db/tests/0001_rang_buoc.sql` | 11 ca kiểm ràng buộc (`make test-db`) |
| `hasura/metadata/` | Quyền GraphQL theo vai, lọc theo hàng |
| `tests/smoke.sh` | Smoke qua gateway (`make smoke-app`) |
| `module.env` | Biến cần đặt trong `.env` khi chạy module |

## Dữ liệu và Poka-yoke

| Bảng | Cột chính |
|---|---|
| `devices` | `code` (mã in trên thiết bị), `name`, `kind` (`may_phat_dien`, `may_bom`, `loa`, `may_chieu`, `dung_cu`, `khac`), `condition` (`tot`, `can_sua`, `hong`, `ngung_dung`), `location`, `note` |
| `loans` | `device_id`, `borrower_sub` (sub Keycloak), `borrower_name`, `purpose`, `borrowed_at`, `due_at`, `returned_at`, `return_note` |

Ràng buộc nằm trong CSDL, nên mọi đường ghi đều phải qua:

| Ràng buộc | Cách làm |
|---|---|
| Một thiết bị chỉ có một lượt mượn đang mở | Chỉ mục duy nhất có điều kiện `loans_one_open_per_device (device_id) WHERE returned_at IS NULL`; hai người mượn cùng lúc cũng chỉ một người được |
| Không mượn thiết bị hỏng hoặc ngừng dùng | Trigger `loans_guard` |
| Hạn trả sau lúc mượn, tối đa 30 ngày; trả không trước lúc mượn | CHECK `loans_due_after_borrow`, `loans_max_30_days`, `loans_return_after_borrow` |
| Lượt đã trả không sửa; không đổi thiết bị, người mượn, lúc mượn | Trigger `loans_guard` (`23001`) |

## Quyền theo vai (Hasura)

| Bảng | `quan-ly` | `nguoi-muon` |
|---|---|---|
| `devices` | Đọc mọi cột, thêm, sửa (tình trạng, chỗ để, ghi chú). Không xóa (ngừng dùng = `ngung_dung`) | Đọc, không thấy `note` |
| `loans` | Đọc mọi lượt; ghi nhận trả (`returned_at`, `return_note`) | Mượn cho **chính mình** (`borrower_sub` gán từ JWT, không tự khai được); chỉ thấy lượt của mình; không sửa |

Không vai trò nào xóa được lượt mượn.

## Chạy

```bash
cp .env.example .env
sed -i.bak '/^DXOS_APP=/d; /^KEYCLOAK_REALM=/d' .env && grep -v '^#' apps/muon-thiet-bi/module.env >> .env
make up && make seed
make smoke-app      # smoke lõi dùng chung + test DB + tests/smoke.sh
```

```graphql
# nguoimuon01: mượn máy phát điện 3 ngày
mutation { insert_loans_one(object: {device_id: "d0000000-0000-4000-8000-000000000001",
  due_at: "2026-11-01T00:00:00Z", purpose: "Chiếu sáng sân chung khi mất điện"}) { id due_at } }
# quanly01: lượt mượn gần nhất của từng thiết bị (returned_at null = đang mượn)
query { devices { code name condition loans(order_by: {borrowed_at: desc}, limit: 1) { borrower_name due_at returned_at } } }
```

Smoke (`tests/smoke.sh`, 22 ca) kiểm:
- lõi chạy với module: schema và role theo quy ước tên của lõi, không có gì của `apps/cuu-tro`, `/` và `/workflow/*` trả 503 vì không có backend;
- quyền theo vai, kể cả giả mạo người mượn;
- Poka-yoke qua GraphQL, kể cả hai người mượn cùng lúc;
- trả rồi mượn lại.

Dữ liệu là dữ liệu giả.
