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
- Cần **1 người khác duyệt** và CI xanh: 7 job bắt buộc `license`, `build-from-source`, `shellcheck`, `yamllint`, `pytest`, `go-test`, `go-licenses`; job `web` và `mobile` chạy trên mọi PR (chưa bắt buộc nhưng phải xanh).
- Nhánh phải cập nhật theo `develop` trước khi merge (`git pull --rebase origin develop` hoặc nút *Update branch*).
- Merge kiểu **squash**, xóa nhánh sau khi merge.
- Người duyệt kiểm: đúng phạm vi issue, có SPDX, có CHANGELOG, chạy được theo hướng dẫn trong PR.

## 6. Thành phần bên thứ ba
- Chỉ dùng thành phần có giấy phép OSI. Thành phần GPL/AGPL chỉ chạy như dịch vụ riêng bằng image gốc.
- Không vendor hay sửa mã thư viện. Ghim phiên bản cụ thể, không dùng tag `latest`.
- Thêm thành phần → cập nhật `NOTICE` và `DEPENDENCIES.md` trong cùng PR.

## 7. Phát hành phiên bản
Phiên bản theo [SemVer](https://semver.org/lang/vi/). Mỗi bản phát hành là một tag `vX.Y.Z` trên `main`, kèm gói mã nguồn `.tar.gz` và `SHA256SUMS` trên GitHub Releases.

1. **Issue + nhánh** `release/vX.Y.Z` tách từ `develop`. Chạy `make smoke` đầy đủ trên volume trống, ghi số ca vào CHANGELOG.
2. **Chốt CHANGELOG:** đổi `[Unreleased]` thành `[X.Y.Z] - YYYY-MM-DD`, thêm một đoạn tóm tắt, thêm mục `[Unreleased]` trống ở trên, cập nhật đường so sánh `vX.Y.Z...` ở cuối tệp.
3. **Nâng phiên bản** ở mọi nơi khai báo:
   - `apps/cuu-tro/web/package.json` (+ `package-lock.json`), `apps/cuu-tro/mobile/package.json` (+ `versionName` trong `android/app/build.gradle`, `MARKETING_VERSION` trong Xcode);
   - `apps/cuu-tro/workflow/pyproject.toml` (+ `uv.lock`), `version` của FastAPI trong `cuu_tro_workflow/api.py`;
   - tag image `disaster-dxos/cuu-tro-web`, `disaster-dxos/cuu-tro-workflow` trong compose (image `disaster-dxos/ledger` chỉ nâng khi `core/ledger` đổi);
   - README (mục CHANGELOG).
4. **PR về `develop`**, CI xanh, merge. Sau đó **PR `develop` → `main`** (merge commit, không squash).
5. **Tag và đóng gói** trên `main`:
   ```bash
   git switch main && git pull
   git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z
   git archive --format=tar.gz --prefix=disaster-dxos-X.Y.Z/ -o disaster-dxos-X.Y.Z.tar.gz vX.Y.Z
   shasum -a 256 disaster-dxos-X.Y.Z.tar.gz > SHA256SUMS     # Linux: sha256sum
   ```
   `git archive` chỉ lấy tệp trong git: không có `.env`, `.data/`, `node_modules/`, trọng số mô hình.
6. **GitHub Release** từ tag, nội dung lấy từ mục CHANGELOG của bản, đính kèm `disaster-dxos-X.Y.Z.tar.gz` và `SHA256SUMS`. Tệp `.zip` GitHub tự sinh không cần xử lý.

**Người dùng kiểm và build từ gói phát hành:**
```bash
shasum -a 256 -c SHA256SUMS                 # → disaster-dxos-X.Y.Z.tar.gz: OK
tar -xzf disaster-dxos-X.Y.Z.tar.gz && cd disaster-dxos-X.Y.Z
cp .env.example .env && make up && make seed && make smoke   # chi tiết: docs/cai-dat.md
```

