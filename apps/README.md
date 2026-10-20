<!-- SPDX-License-Identifier: Apache-2.0 -->
# apps/ — Ứng dụng Tầng 2

Mỗi thư mục con là một ứng dụng cắm vào lõi `core/`. Chọn ứng dụng bằng biến `DXOS_APP` trong `.env`.

| Ứng dụng | Mô tả |
|---|---|
| `cuu-tro/` | Ứng phó thiên tai & cứu trợ cộng đồng (mặc định) |

Cấu trúc một ứng dụng (điểm cắm vào lõi):

```
apps/<tên>/
├── keycloak/realm.json     # realm: vai trò, client, người dùng mẫu (bắt buộc)
├── db/migrations/          # schema nghiệp vụ, SQL đánh số NNNN_<tên>.sql (container migrate)
├── db/seed/                # dữ liệu mẫu (dữ liệu giả), make seed
├── db/tests/               # kiểm thử ràng buộc, make test-db
├── hasura/metadata/        # quyền GraphQL theo vai trò (tuần 2)
├── gateway/routes.yaml     # route APISIX riêng của ứng dụng (tuần 2)
├── workflows/              # worker Temporal (Python)
└── web/, mobile/           # giao diện người dùng cuối
```

Ứng dụng chỉ gọi lõi qua API Gateway. Xem `docs/architecture.md` mục 7.
