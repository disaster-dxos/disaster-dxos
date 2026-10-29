<!-- SPDX-License-Identifier: Apache-2.0 -->
# scripts/demo: dữ liệu demo, 7 luồng, video dự phòng · *demo data, the 7 flows, backup video*

Công cụ cho buổi trình bày 15 phút (#130). Kịch bản theo phút, lời thoại, câu hỏi giám khảo, phương án khi hỏng, dàn ý slide: [`docs/trinh-bay/kich-ban-demo.md`](../../docs/trinh-bay/kich-ban-demo.md). Mọi dữ liệu là **dữ liệu giả**.

*Tools for the 15-minute final presentation: a script that seeds demo data and replays each of the 7 demo flows through the real API gateway, and a Playwright script that records a 3–5 minute backup video of the same flows on the real stack. All data is fake.*

| Tệp · *File* | Việc · *Purpose* |
|---|---|
| `luong.sh` | Dựng dữ liệu demo (`chuan-bi`) và chạy từng luồng qua APISIX, in đúng điều cần nói · *seed demo data and replay each flow* |
| `quay-video.mjs` | Quay video dự phòng bằng Playwright, ghép MP4 bằng ffmpeg · *record the backup video* |
| `package.json`, `package-lock.json` | Playwright 1.64.0 (Apache-2.0), chỉ dùng cho việc quay · *Playwright, recording only* |

## Dựng dữ liệu và chạy luồng · *Seed data and run the flows*

```bash
make up                                  # nên dựng trên volume trống
bash scripts/demo/luong.sh chuan-bi      # seed, 10 đội giả, 8 tin nền, trận lũ mẫu tới giờ 30, nhập kho, thu quỹ, Grafana
bash scripts/demo/luong.sh 1 --duyet     # dán tin → AI bóc tách → hàng chờ (--duyet: điều phối duyệt qua API)
bash scripts/demo/luong.sh 2             # tin mới → bản đồ realtime; gửi trùng → 409
bash scripts/demo/luong.sh 3 --nhan      # trạng thái workflow phân công của tin bước 2 (--nhan: nhận nhiệm vụ)
bash scripts/demo/luong.sh 4             # app hiện trường gửi lại 2 lần cùng Idempotency-Key → 1 tin
bash scripts/demo/luong.sh 5             # trạm đo vượt ngưỡng → workflow cảnh báo → hộp thư
bash scripts/demo/luong.sh 6             # phiếu xuất kho → sổ cái → link trang Minh bạch + ledger-verify
bash scripts/demo/luong.sh 7             # Grafana (SSO Keycloak)
bash scripts/demo/luong.sh tat-ca        # chuan-bi rồi 1 → 7
```

- Mỗi lần chạy dùng SĐT giả mới (`090013xxxx`), nên chạy lại không bị chặn trùng. Trạng thái giữa các bước (mã tin, mã phiếu, token tạm) nằm ở `.data/demo/` (ngoài git, quyền 700).
- `chuan-bi` thêm 10 đội cứu hộ giả quanh Đại Lộc, Điện Bàn: seed chỉ có 2 đội sẵn sàng, 8 tin nền sẽ giữ hết.
- Sau khi `dieuphoi01` cài OTP trên web, lấy token bằng mật khẩu cũng phải kèm mã OTP. `luong.sh` đọc bí mật TOTP mà `quay-video.mjs` lưu ở `.data/demo/totp-dieuphoi01.txt`. Nếu cài OTP bằng điện thoại thì các bước cần token điều phối (`chuan-bi`, `1 --duyet`, `3`, `6`) cần chạy trước khi cài.
- Bước 5 chỉ có thông báo mới khi trạm đo đổi bước trong đợt (vượt ngưỡng, lên nguy hiểm, về dưới ngưỡng): mỗi bước báo đúng một lần, chạy lại ngay thì hộp thư không có tin mới.

*English: run `make up`, then `bash scripts/demo/luong.sh chuan-bi`, then steps `1` to `7` (or `tat-ca` for everything). Each run uses new fake phone numbers, so it can be repeated; state lives in `.data/demo/` (git-ignored).*

## Quay video dự phòng · *Record the backup video*

Cần stack đang chạy và đã `chuan-bi`, Node 22+, ffmpeg.

```bash
cd scripts/demo && npm ci && npx playwright install chromium
VIDEO_DIR=/đường/dẫn/ngoài/repo node quay-video.mjs
```

Video gồm 3 đoạn quay riêng rồi ghép lại:
- **Điều phối viên**, bước 1–3. Lần đầu đăng nhập, script tự cài OTP cho `dieuphoi01`.
- **Đội cứu hộ** (`cuuho01`) nhận nhiệm vụ.
- **Điều phối viên** tiếp tục bước 4–7, dùng lại phiên đăng nhập của đoạn đầu.

Mỗi luồng mở bằng một thẻ tiêu đề. Phần chạy bằng API thì kết quả thật in lên thẻ.

Kết quả là `disaster-dxos-demo.mp4` (H.264, 1280×720, 25 khung/giây). Nên quay trên volume vừa dựng: chạy lại trên stack cũ thì các đội gần đã bận và đợt vượt ngưỡng đã báo rồi.

**Không commit video.** Mặc định video ghi vào `.data/demo/video/` (ngoài git). Bản của đội để ở thư mục chung của nhóm, ngoài repo.

*English: needs the running stack after `chuan-bi`, Node 22+ and ffmpeg. The MP4 is a product, not source: it is written outside git (`.data/demo/video/` by default, or `VIDEO_DIR`). Record on freshly created volumes for the best result.*
