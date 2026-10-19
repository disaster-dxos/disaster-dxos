# Đóng góp

## Nhánh (GitFlow)
- `main` — chỉ chứa bản phát hành (`v1.0.0`…), merge từ `develop` qua PR.
- `develop` — nhánh tích hợp hằng ngày.
- `feature/<issue>-<ten-ngan>` — mỗi việc một nhánh, tách từ `develop`, mở PR về `develop`.

## Commit
Mỗi commit một việc, viết rõ làm gì: `feat(rag): nạp PDF vào pgvector (#12)`.
Loại: `feat`, `fix`, `docs`, `chore`, `test`, `refactor`. Gắn số issue nếu có.

**Ai làm thì người đó commit** — log commit là bằng chứng đóng góp của từng thành viên.

## Trước khi mở PR
- [ ] `bash scripts/add-license-header.sh` — mọi file mới có header SPDX
- [ ] `make up` chạy được từ máy sạch
- [ ] Không commit `.env`, model, dữ liệu thật
