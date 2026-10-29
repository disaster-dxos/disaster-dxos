<!-- SPDX-License-Identifier: Apache-2.0 -->
# Kịch bản trình bày chung kết 15 phút

Tài liệu cho buổi chấm chung kết OLP PMNM 2026. Theo thể lệ, 15 phút gồm 4 phần: giải pháp thiết kế và lựa chọn công nghệ, tính năng nền tảng và bài toán minh họa, demo, định hướng phát triển. Phần demo đi qua H-P-D-I bằng 7 luồng thật trên stack thật, dữ liệu là dữ liệu giả.

- Dựng dữ liệu, chạy từng luồng bằng lệnh: [`scripts/demo/`](../../scripts/demo/README.md).
- Video dự phòng (3–5 phút): quay bằng `scripts/demo/quay-video.mjs`. Video **không nằm trong repo**: bản của đội để ở thư mục chung của nhóm, mang theo trên máy trình bày và một USB.
- Thang điểm phần sản phẩm (50 điểm): nguyên gốc (10), hoàn thiện khi chạy demo (10), thân thiện người dùng (10), phát triển bền vững (10), phong cách trình diễn và thu hút cộng đồng (10). Mỗi đoạn dưới đây ghi tiêu chí nó nhắm tới.

## 1. Chuẩn bị (trước giờ trình bày)

| Khi nào | Việc | Lệnh / ghi chú |
|---|---|---|
| Hôm trước | Dựng stack trên volume trống, dữ liệu demo, chạy thử một lượt | `make up && bash scripts/demo/luong.sh chuan-bi`, rồi `bash scripts/demo/luong.sh tat-ca` trên một máy khác hoặc dựng lại sau khi thử |
| Hôm trước | Kiểm video dự phòng mở được trên máy trình bày và USB | Tệp MP4, H.264, 1280×720 |
| 30 phút trước | Dựng lại volume trống, `chuan-bi`, mở sẵn các tab | Tab 1 `http://localhost:9080/` (dieuphoi01, đã cài OTP trên điện thoại), tab 2 cửa sổ hẹp `…/phan-cong` (cuuho01), tab 3 `…/grafana/`, terminal ở gốc repo, chữ cỡ lớn |
| 30 phút trước | Tắt thông báo hệ điều hành, cắm sạc, kiểm cổng 8080/9080, tắt VPN | VPN làm Keycloak thấy IP công khai, lỗi `HTTPS required` |
| 5 phút trước | Lượt cuối: `bash scripts/demo/luong.sh 7` (Grafana sống), mở sẵn trang Duyệt tin AI | Không chạy lại `chuan-bi` sát giờ (mất ~1 phút) |

Phân vai (3 người): **người nói** (dẫn chuyện, lời thoại), **người thao tác** (máy demo), **người dự phòng** (terminal chạy `luong.sh`, theo dõi đồng hồ, cầm USB video).

## 2. Kịch bản theo phút

| Phút | Phần | Nội dung | Tiêu chí |
|---|---|---|---|
| 0:00–1:30 | Bài toán | Một đêm lũ ở xã An Lạc: tin kêu cứu rải rác, cứu trùng/sót, không có bức tranh thời gian thực, hàng cứu trợ khó kiểm | Phong cách |
| 1:30–4:00 | Thiết kế, công nghệ | Hai tầng Open-Core; 4 dịch vụ lõi bắt buộc; vì sao chọn từng thành phần (giấy phép OSI, chạy trên laptop 16 GB); module cắm–rút | Nguyên gốc |
| 4:00–12:00 | Demo 7 luồng | H-P-D-I trên stack thật (mục 3) | Hoàn thiện, thân thiện |
| 12:00–13:30 | Bền vững, cộng đồng | Tài liệu song ngữ, smoke 1033 ca, release `.tar.gz`, bộ mô phỏng trạm đo dùng độc lập, module mẫu thứ hai | Bền vững, cộng đồng |
| 13:30–15:00 | Định hướng, kết | VPS + HTTPS, thử với người dùng thật, bot Telegram cho người dân, v1.0.0 | Phong cách |

### 0:00–1:30 · Bài toán

> "Mười giờ đêm, nước lên tới mái. Cán bộ xã An Lạc cầm ba chiếc điện thoại: một người gọi kêu cứu không nói được địa chỉ, một nhóm Zalo báo cùng một nhà ba lần, còn đội ca nô thì không ai biết đang ở đâu. Sáng hôm sau, nhà tài trợ hỏi 800 ký gạo đã đi đâu. Disaster DX-OS giải bốn việc đó trên một hệ thống chung."

Slide: 4 thách thức (README mục Thách thức), một câu giải pháp cho mỗi cái.

### 1:30–4:00 · Thiết kế và lựa chọn công nghệ

> "Đề yêu cầu một lõi headless dùng lại được. Lõi của chúng em chỉ có API: Keycloak cho SSO có OTP, APISIX có tường lửa WAF làm cổng duy nhất, PostgreSQL + PostGIS với GraphQL tự sinh bằng Hasura, SeaweedFS cho ảnh, Temporal cho quy trình. Lõi không biết gì về thiên tai. Ứng dụng cứu trợ là một thư mục trong `apps/`; để chứng minh, repo có module thứ hai, mượn trả thiết bị, chạy trên cùng lõi mà không sửa một dòng `core/`."

Ý cần nói về lựa chọn:
- Mọi thành phần OSI; thành phần AGPL/GPL (Grafana, PostGIS, ClamAV) chạy như dịch vụ riêng bằng image gốc. Bỏ MongoDB, Vault, immudb vì giấy phép.
- Bí mật không nằm trong `.env`: OpenBao sinh và cấp cho từng dịch vụ.
- Sổ cái minh bạch là transparency log Tessera (như Certificate Transparency), không phải blockchain: không cần đồng thuận, ai cũng kiểm được bằng chứng.

### 4:00–12:00 · Demo 7 luồng

Mỗi luồng khoảng 1 phút. Cột "Dự phòng" là lệnh người dự phòng chạy khi giao diện hỏng (in ra đúng điều cần nói).

| # | Phút | H-P-D-I | Thao tác | Lời thoại ngắn | Dự phòng |
|---|---|---|---|---|---|
| 1 | 4:00 | [I] + [P] | Tab 1 → **Duyệt tin AI**. Dán: *"Cuu voi!! nha toi o thon 2 xa An Lac nuoc len toi mai roi, co 3 nguoi trong do 1 ba cu 80 tuoi. Toa do 15.8461, 108.1158. SDT 0900130xxx"* → **Bóc tách bằng AI** → chỉ vào đề xuất cạnh văn bản gốc → sửa mức khẩn lên "Khẩn cấp" (có người già) → **Duyệt và tạo tin** | "Tin thật là tin nhắn viết vội, không dấu. AI chỉ đề xuất, không tạo tin. Người duyệt sửa mức khẩn vì có cụ 80 tuổi; hệ thống ghi lại AI đề xuất gì, người sửa trường nào, ai duyệt." | `luong.sh 1 --duyet` |
| 2 | 5:10 | [D] | Tab 1 → **Bản đồ**. Người dự phòng chạy `luong.sh 2` | "Không ai bấm tải lại: tin mới hiện ngay, đỏ vì khẩn cấp. Người dân báo lại lần nữa thì CSDL chặn trùng trong 200 m: không có cứu trợ trùng." | `luong.sh 2` (in mã 201 và 409) |
| 3 | 6:20 | [P] | Tab 1 → **Phân công**: tin vừa tạo ở "Đang phân công", đồng hồ hạn nhận. Tab 2 (cuuho01, cửa sổ hẹp như điện thoại) → mở nhiệm vụ → **Nhận nhiệm vụ** | "Không ai chọn đội bằng tay: workflow Temporal tìm đội sẵn sàng gần nhất bằng PostGIS, hạn nhận theo mức khẩn, quá hạn tự giao đội kế tiếp. Đội cứu hộ chỉ thấy việc của đội mình, nút to bấm được bằng một tay." | `luong.sh 3 --nhan` |
| 4 | 7:30 | [H] | Slide ảnh app React Native (hàng đợi offline). Người dự phòng chạy `luong.sh 4` | "Ở vùng lũ mất sóng là chuyện thường. App hiện trường lưu mọi thao tác vào hàng đợi mã hóa trên máy, có sóng thì gửi lại kèm khóa idempotency. Vừa rồi app gửi lại hai lần: máy chủ trả cùng một tin, CSDL có đúng một bản ghi." | Đã là lệnh |
| 5 | 8:40 | [D] + [I] | Tab 1 → Bản đồ. Người dự phòng chạy `luong.sh 5` → bấm **Thông báo** | "Trạm đo Cẩm Lệ vừa vượt mức nguy hiểm. Mỗi đợt vượt ngưỡng là một workflow: báo đúng một lần khi vượt, khi lên nguy hiểm, khi về dưới ngưỡng; không spam. Trạm đo là bản sao số NGSI-LD trên Scorpio, dữ liệu mở cho hệ thống khác dùng." | `luong.sh 5` (in hộp thư cảnh báo) |
| 6 | 9:50 | [D] | Người dự phòng chạy `luong.sh 6` → mở link `/minh-bach/<mã>` ở cửa sổ ẩn danh (không đăng nhập) → chờ 5 bước tự kiểm → cuộn tới "Hàng từ kho tới điểm nhận" | "Nhà tài trợ không cần tài khoản, không cần tin chúng em: trình duyệt tự tải bằng chứng, tự kiểm chữ ký và đường Merkle. Ai muốn kiểm ngoài trình duyệt thì chạy CLI `ledger-verify`, kết quả ĐÃ XÁC MINH." | `luong.sh 6` (có `ledger-verify`) |
| 7 | 11:00 | [D] | Tab 3 → **Grafana** (SSO, không gõ lại mật khẩu) → dashboard Điều hành cứu trợ | "Lãnh đạo xã xem tổng hợp: tin theo trạng thái, thời gian phản hồi, mực nước, tồn kho, quỹ. Cùng tài khoản Keycloak: điều phối là Editor, cứu hộ chỉ xem. Grafana đọc bằng role chỉ đọc, không thấy SĐT hay họ tên người dân." | `luong.sh 7` |

### 12:00–13:30 · Phát triển bền vững và cộng đồng

> "Người ngoài chạy được từ máy sạch bằng ba lệnh, README song ngữ. Mỗi thay đổi đi qua issue, PR và CI; `make smoke` kiểm 1033 ca trên stack thật, volume trống. Mỗi bản phát hành có gói `.tar.gz` và checksum. Ai không cần cả hệ thống vẫn dùng được bộ mô phỏng trạm đo lũ và mô hình NGSI-LD của chúng em, chỉ cần Python."

Số liệu đưa lên slide (lấy lại ngay trước buổi, không làm tròn lên): số release, số issue/PR đã đóng, số ca smoke, số người đóng góp, sao/fork thật của repo.

### 13:30–15:00 · Định hướng và kết

> "Tiếp theo: đưa lên máy chủ có HTTPS để xã thật dùng thử, bot Telegram cho người dân tự kêu cứu, phát hành v1.0.0. Lõi mở để bất kỳ xã nào, bất kỳ đề tài nào cũng cắm ứng dụng của mình vào. Cảm ơn hội đồng."

## 3. Khi demo hỏng

Nguyên tắc: không gỡ lỗi trước hội đồng quá 20 giây. Người nói tiếp tục lời thoại, người dự phòng chuyển phương án.

| Sự cố | Dấu hiệu | Phương án |
|---|---|---|
| Một màn web lỗi hoặc treo | Trang trắng, quay mãi | Người dự phòng chạy lệnh ở cột "Dự phòng" của bước đó, chiếu terminal (chữ lớn); người nói đọc kết quả |
| Keycloak không cho đăng nhập / OTP lệch giờ | "Invalid authenticator code" | Dùng tab đã đăng nhập sẵn; đồng bộ giờ điện thoại; vẫn lỗi thì chuyển video |
| Bản đồ không hiện nền | Ô bản đồ xám | Nền bản đồ lấy từ Internet (OpenFreeMap); tin và trạm vẫn hiện trên nền xám. Nói rõ "mất mạng ngoài", demo tiếp |
| Bước 3 không có đội | "Không còn đội sẵn sàng" | Chính là tính năng: hệ thống báo điều phối. Bấm **Phân công tự động** lại sau khi `luong.sh chuan-bi` (thêm đội giả) |
| Bước 5 không có thông báo mới | Hộp thư trống | Đợt vượt ngưỡng đã báo trước đó (báo đúng một lần mỗi bước). Chạy `luong.sh 5` cho hộp thư từ CSDL |
| Cả stack chết, mất điện, máy treo | – | Chiếu video dự phòng (3–5 phút), người nói thuyết minh theo đúng kịch bản; sau đó quay lại slide |

## 4. Câu hỏi giám khảo có thể hỏi

| Câu hỏi | Trả lời ngắn |
|---|---|
| Lõi "headless" thật không, hay chỉ là thư mục? | Lõi chỉ có API, không có giao diện. Module thứ hai `apps/muon-thiet-bi/` chạy trên cùng lõi không sửa `core/`; smoke của nó chạy riêng (`make smoke-app`). Lõi suy mọi tên (schema, role, bí mật, bucket) từ `DXOS_APP` |
| AI sai thì sao? | AI không bao giờ tạo tin. Mọi đề xuất qua Poka-yoke giống tin nhập tay, rồi người duyệt. Có vết duyệt không sửa được. Không có mô hình thì bộ luật mặc định vẫn chạy (đo: Qwen2.5 7B đúng 58/59 trường trên bộ tin mẫu) |
| Vì sao Qwen2.5 7B mà không phải Llama/Gemma? | Giấy phép: Qwen2.5 7B là Apache-2.0; Llama, Gemma và Qwen 3B/72B có giấy phép riêng không OSI. Chạy CPU trên laptop ~11,5 giây/tin |
| Sổ cái có phải blockchain? Sao không dùng blockchain? | Không. Transparency log (Tessera, như Certificate Transparency): chỉ thêm, có chữ ký, ai cũng kiểm được bằng chứng Merkle. Xã là một bên ghi duy nhất nên không cần đồng thuận; chi phí gần như bằng không |
| Dữ liệu cá nhân người dân được bảo vệ thế nào? | SĐT chỉ vai được phép mới thấy (phân quyền theo cột trong Hasura), bản đồ che giữa số; sổ cái công khai không chứa thông tin cá nhân; Grafana và Parquet đọc bằng role không có quyền trên cột định danh; log không ghi SĐT |
| Mất mạng cả xã thì sao? | App hiện trường dùng được offline và gửi lại an toàn. Máy chủ có thể đặt tại xã (laptop 16 GB chạy được profile `core`). Kênh SMS/Telegram là hướng tiếp theo |
| Có người dùng thật chưa? | Chưa thử với cán bộ xã thật; đó là việc của tuần cuối và sau cuộc thi (cần VPS + HTTPS). Trả lời thẳng, không phóng đại |
| Tại sao nhiều thành phần vậy, có nặng không? | Đo thật: cả hệ thống ~2,3 GB RAM sau khởi động. Profile tách rời: AI, Grafana, ClamAV chỉ bật khi cần |
| Làm sao biết hệ thống chạy đúng? | `make smoke`: 1033 ca gọi thật qua gateway trên volume trống, chạy trước mỗi PR lớn và mỗi bản phát hành; CI 9 job (giấy phép, build từ mã nguồn, lint, pytest, go test, web, app) |
| Đóng góp của từng thành viên? | Mỗi thành viên trả lời phần mình làm, chỉ vào commit/PR của mình trên GitHub |
| Giấy phép AGPL của Grafana có ảnh hưởng Apache-2.0 không? | Không: Grafana chạy như dịch vụ riêng bằng image gốc, không sửa, không liên kết vào mã dự án; liệt kê trong NOTICE và DEPENDENCIES.md |

## 5. Dàn ý slide

Slide chưa làm; dưới đây là tiêu đề và ý chính từng trang (khoảng 12 trang, mỗi trang một ý, chữ to, nhiều hình).

| # | Tiêu đề | Ý chính |
|---|---|---|
| 1 | Disaster DX-OS | Logo, tên đội DTU_DZ_1, một câu: "Hệ điều hành ứng phó thiên tai và cứu trợ cộng đồng, mã nguồn mở" |
| 2 | Một đêm lũ ở xã An Lạc | Ảnh minh họa; 4 thách thức: tin rải rác, cứu trùng/sót, không có bức tranh thời gian thực, hàng tiền thiếu minh bạch |
| 3 | Bốn câu trả lời | Poka-yoke chặn sai từ đầu · phân công theo vị trí thật · số liệu hiện trường tự động · minh bạch kiểm chứng được |
| 4 | Kiến trúc hai tầng Open-Core | Ảnh kiến trúc tổng quan; lõi headless 4 dịch vụ bắt buộc; ứng dụng chỉ gọi qua APISIX |
| 5 | Vì sao chọn những thành phần này | Bảng ngắn: Keycloak, APISIX + Coraza, PostgreSQL/PostGIS + Hasura, SeaweedFS, Temporal, NATS, Tessera, OpenBao; tiêu chí: OSI, chạy laptop, bỏ MongoDB/Vault/immudb |
| 6 | Lõi dùng lại được | Module thứ hai mượn trả thiết bị; tên tự suy từ `DXOS_APP`; hướng dẫn viết module |
| 7 | H-P-D-I trên một trang | Bốn cột: [H] web, app, thông báo · [P] Poka-yoke, workflow phân công · [D] NGSI-LD, bản đồ, sổ cái, Parquet · [I] AI có người duyệt, cảnh báo |
| 8 | Demo | Danh sách 7 luồng (trang này để trong lúc demo) |
| 9 | AI có người duyệt | Ảnh trang Duyệt tin AI; số đo Qwen2.5 7B; AI không tạo tin |
| 10 | Minh bạch không cần tin máy chủ | Sơ đồ phiếu → băm → sổ cái → tự kiểm; ảnh trang Minh bạch |
| 11 | Bền vững và cộng đồng | Số liệu thật: release, issue/PR, smoke 1033 ca, CI; README song ngữ; bộ mô phỏng trạm đo cho cộng đồng |
| 12 | Tiếp theo | VPS + HTTPS, người dùng thật, bot Telegram, v1.0.0; link repo + QR; cảm ơn |
