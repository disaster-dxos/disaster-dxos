# Disaster DX-OS — Hệ điều hành Ứng phó Thiên tai & Cứu trợ Cộng đồng

> OLP PMNM 2026 · Đề tài DX-OS Open-Core · Giấy phép [Apache-2.0](LICENSE)

**VI:** Nền tảng nguồn mở giúp chính quyền địa phương, đội cứu hộ và tình nguyện viên tiếp nhận tin kêu cứu, điều phối cứu hộ trên bản đồ thời gian thực và quản lý hàng cứu trợ minh bạch.

**EN:** An open-source platform for local authorities, rescue teams and volunteers to triage distress calls, coordinate rescue on a real-time map, and manage relief supplies transparently.

## Trạng thái
Đang xây dựng. Xem [`docs/de-thi-mapping.md`](docs/de-thi-mapping.md) và [`CHANGELOG.md`](CHANGELOG.md).

## Chạy nhanh / Quick start
```bash
cp .env.example .env
make up      # lần đầu: tự khởi tạo + mở khóa OpenBao, sinh bí mật lõi
make smoke   # kiểm OpenBao + JWT qua APISIX
```

**Bí mật / Secrets (OpenBao):** bí mật của dịch vụ lõi nằm trong OpenBao, không nằm trong `.env`. Unseal key và root token được ghi vào `.data/openbao/` (ngoài git) — giữ kín, mất là không mở khóa được dữ liệu. / Core service secrets live in OpenBao, not in `.env`; unseal keys and the root token are written to `.data/openbao/` (git-ignored).

| Lệnh | Việc |
|---|---|
| `make bao-init` | Khởi tạo / nạp bí mật, policy, AppRole (chạy lại an toàn) · Init and seed (idempotent) |
| `make bao-unseal` | Mở khóa sau khi khởi động lại nếu `OPENBAO_DEV_AUTO_UNSEAL=false` · Unseal after restart |
| `make bao-status` | Trạng thái seal · Seal status |

Chi tiết: [`docs/architecture.md`](docs/architecture.md) mục 8.

## Đóng góp
Xem [`CONTRIBUTING.md`](CONTRIBUTING.md) và [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).
