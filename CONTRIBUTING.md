# Đóng góp

Cảm ơn bạn quan tâm tới Disaster DX-OS. Mọi thay đổi đi theo một quy trình: **issue → nhánh → PR → duyệt → merge**.
Không đẩy thẳng lên `main` hay `develop`: hai nhánh này được bảo vệ, chỉ nhận PR đã qua CI và có người duyệt.

## 1. Mở issue
- Mỗi việc là một issue. Dùng mẫu **Việc cần làm** hoặc **Báo lỗi**.
- Ghi rõ "Xong khi" (tiêu chí hoàn thành) và gắn nhãn: tuần (`tuan-2`…`tuan-7`), vai phụ trách (`vai-1-core`, `vai-2`, `vai-3`), loại (`pof`, `documentation`, `bug`…).
- Tự giao issue cho mình (assign) trước khi làm để tránh hai người làm trùng.
- Người mới: chọn issue có nhãn `good first issue` hoặc `help wanted`.

## 2. Tạo nhánh
Tách từ `develop` mới nhất:

```bash
git checkout develop && git pull
git checkout -b feature/<số-issue>-<tên-ngắn>
```

| Nhánh | Dùng cho |
|---|---|
| `main` | Chỉ bản phát hành (`v0.1.0`, `v1.0.0`…), merge từ `develop` khi release |
| `develop` | Nhánh tích hợp, đích của mọi PR |
| `feature/<số-issue>-<tên-ngắn>` | Một issue một nhánh, ví dụ `feature/12-hasura-jwt` |

Tên ngắn viết thường, không dấu, nối bằng gạch ngang.

## 3. Commit
Theo [Conventional Commits](https://www.conventionalcommits.org/vi/v1.0.0/), mô tả bằng tiếng Việt, kèm số issue:

```
<loại>(<phạm vi>): <mô tả ngắn> (#<số-issue>)
```

Ví dụ: `feat(gateway): thêm route /graphql kiểm JWT (#12)`, `fix(keycloak): sửa redirect URI của dxos-web (#15)`.

| Loại | Khi nào |
|---|---|
| `feat` | Tính năng mới |
| `fix` | Sửa lỗi |
| `docs` | Chỉ tài liệu |
| `chore` | Cấu hình, CI, công cụ, giấy phép |
| `refactor` | Sắp xếp lại mã, không đổi hành vi |
| `test` | Thêm/sửa kiểm thử |

Mỗi commit một việc. **Ai làm thì người đó commit bằng tài khoản của mình**: lịch sử commit là bằng chứng đóng góp của từng thành viên.

## 4. Mở PR
- PR về `develop`, điền mẫu PR, ghi `Closes #<số-issue>` để issue tự đóng khi merge.
- Trước khi mở PR:
  - [ ] `make check` đạt (header SPDX + compose hợp lệ)
  - [ ] File mới có header `SPDX-License-Identifier: Apache-2.0` (`make license`)
  - [ ] Thêm dòng vào `CHANGELOG.md` mục `[Unreleased]`
  - [ ] Cập nhật tài liệu, `.env.example`, `NOTICE`/`DEPENDENCIES.md` nếu thêm thành phần
  - [ ] Không commit `.env`, model, dữ liệu thật

## 5. Duyệt và merge
- Cần **1 người khác duyệt** và CI (`license`, `build-from-source`) xanh.
- Nhánh phải cập nhật theo `develop` trước khi merge (`git pull --rebase origin develop` hoặc nút *Update branch*).
- Merge kiểu **squash**, xóa nhánh sau khi merge.
- Người duyệt kiểm: đúng phạm vi issue, có SPDX, có CHANGELOG, chạy được theo hướng dẫn trong PR.

## 6. Thành phần bên thứ ba
- Chỉ dùng thành phần có giấy phép OSI. Thành phần GPL/AGPL chỉ chạy như dịch vụ riêng bằng image gốc.
- Không vendor hay sửa mã thư viện. Ghim phiên bản cụ thể, không dùng tag `latest`.
- Thêm thành phần → cập nhật `NOTICE` và `DEPENDENCIES.md` trong cùng PR.
