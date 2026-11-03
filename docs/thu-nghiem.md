<!-- SPDX-License-Identifier: Apache-2.0 -->
# Dùng thử với người dùng thật

Hướng dẫn tổ chức một buổi dùng thử Disaster DX-OS với 3–5 người ngoài đội: chuẩn bị máy, chọn người, giao nhiệm vụ, ghi phản hồi. Mỗi phản hồi thành **một issue** theo mẫu "Phản hồi dùng thử" (nhãn `user-feedback`), đội sửa theo issue như mọi việc khác.

Mục đích là xem người chưa từng thấy hệ thống có tự làm được việc của họ không, chứ không phải trình diễn. Người hỗ trợ **không chỉ tay, không làm thay**; người dùng bí ở đâu thì đó chính là phản hồi cần ghi.

## 1. Chuẩn bị

| Việc | Cách làm |
|---|---|
| Hệ thống | Dựng trên volume trống: `make up`, rồi `bash scripts/demo/luong.sh chuan-bi` (dữ liệu xã An Lạc giả định, 10 đội cứu hộ giả, 8 tin nền, trận lũ mẫu, nhập kho, thu quỹ, Grafana). Chạy `make smoke` trước một lần để chắc stack khỏe, rồi dựng lại volume trống trước buổi thử |
| Địa chỉ | Máy của đội: `http://localhost:9080/` (người dùng ngồi tại máy đội). Demo công khai có HTTPS: dùng địa chỉ đội gửi riêng, **không** ghi vào repo hay issue khi chưa công bố chính thức |
| Tài khoản | Tài khoản mẫu trong README mục "Tài khoản mẫu" (`dieuphoi01`, `cuuho01`, `tinhnguyen01`), đều là dữ liệu giả. Mật khẩu là `KC_DEMO_USER_PASSWORD` trong `.env` của máy chạy: người hỗ trợ **nói trực tiếp** cho người dùng tại buổi thử, không ghi vào tài liệu, issue, tin nhắn nhóm hay ảnh chụp. Demo công khai thì đặt mật khẩu riêng, đổi sau buổi thử |
| OTP | `dieuphoi01` phải cài OTP lần đầu đăng nhập web. Chuẩn bị sẵn điện thoại có app OTP mã nguồn mở (FreeOTP, Aegis) hoặc để người dùng tự cài bằng điện thoại của họ (đó cũng là một bước cần thử) |
| App hiện trường | Chỉ làm NV4 khi đã có APK chạy được trên Android thật (#136) và điện thoại vào được gateway (cùng máy qua `adb reverse`, hoặc demo HTTPS: xem `apps/cuu-tro/mobile/README.md` mục "Chạy app với stack trên máy dev"). Chưa có thì bỏ NV4 |
| Grafana | NV6 cần `make up-bi` |
| Ghi chép | Một người hỗ trợ, một người ghi (giấy hoặc máy). Đồng hồ bấm giờ từng nhiệm vụ. Xin phép trước nếu muốn quay màn hình; không quay mặt người dùng |

Mỗi buổi khoảng 45 phút cho một người: 5 phút giới thiệu, 30 phút nhiệm vụ, 10 phút hỏi cảm nhận và điền mẫu.

## 2. Người dùng mẫu

Chọn 3–5 người, mỗi vai ít nhất một người. Ưu tiên người có kinh nghiệm thật với bão lũ hoặc cứu trợ; không cần biết công nghệ.

| Vai | Ai phù hợp | Tài khoản | Nhiệm vụ chính |
|---|---|---|---|
| Cán bộ xã, người điều phối | Cán bộ xã/phường, thành viên ban chỉ huy phòng chống thiên tai, cán bộ đoàn | `dieuphoi01` | NV1, NV2, NV3 (phần điều phối), NV6 |
| Đội cứu hộ | Thành viên đội cứu hộ, dân quân, sinh viên tình nguyện từng đi cứu trợ | `cuuho01` | NV3 (phần nhận nhiệm vụ), NV4 |
| Tình nguyện viên | Sinh viên, người dân hay đi cứu trợ | `tinhnguyen01` | NV4 |
| Nhà tài trợ, báo chí | Người từng quyên góp, phóng viên, giảng viên | không cần tài khoản | NV5 |

Không dùng thông tin cá nhân thật của người dùng thử trong hệ thống: mọi tin kêu cứu, SĐT, địa chỉ nhập vào đều là dữ liệu giả (vd SĐT `0900130xxx`).

## 3. Nhiệm vụ

Đọc cho người dùng **bối cảnh** và **mục tiêu**, không đọc các bước. Cột "Quan sát" là điều người ghi chép cần để ý.

**Bối cảnh chung:** "Đêm nay xã An Lạc ngập sâu. Tin kêu cứu đến từ nhiều nơi, đội cứu hộ đang ở ngoài, nhà tài trợ hỏi hàng cứu trợ đi đâu. Anh/chị dùng hệ thống này để làm việc của mình."

| # | Vai | Mục tiêu đưa cho người dùng | Đạt khi | Quan sát |
|---|---|---|---|---|
| NV1 | Điều phối | "Có người nhắn tin kêu cứu viết vội, không dấu (người hỗ trợ đưa đoạn tin giả). Hãy đưa tin này vào hệ thống thành một tin kêu cứu đúng." | Tin mới xuất hiện trên bản đồ với mức khẩn, số người, vị trí hợp lý | Có tìm được trang **Duyệt tin AI** không; có đọc lại đề xuất của AI trước khi duyệt không; có sửa mức khẩn khi tin nhắc người già, trẻ nhỏ không |
| NV2 | Điều phối | "Theo dõi tin kêu cứu trên bản đồ. Một người dân báo lại đúng nhà vừa rồi lần nữa: chuyện gì xảy ra?" (người hỗ trợ chạy `bash scripts/demo/luong.sh 2`) | Người dùng thấy tin mới tự hiện và hiểu vì sao tin báo lại bị chặn trùng | Màu, chú thích mức khẩn có rõ không; có biết bấm vào tin để xem chi tiết không |
| NV3 | Điều phối + cứu hộ | Điều phối: "Tin vừa duyệt cần một đội đi cứu. Hãy xem ai được giao, còn bao lâu để đội nhận." Cứu hộ (máy khác hoặc cửa sổ hẹp như điện thoại): "Anh/chị là đội ca nô. Nhận nhiệm vụ mới, khi tới nơi thì báo đã tới, cứu xong thì xác nhận đã cứu." | Tin đi hết các bước tới hoàn thành; điều phối thấy trạng thái đổi | Đội cứu hộ có tìm được nút bằng một tay không; điều phối có hiểu đồng hồ hạn nhận và việc tự giao đội kế tiếp không |
| NV4 | Cứu hộ / tình nguyện | "Anh/chị ở vùng mất sóng. Gửi một tin kêu cứu mới có vị trí và ảnh (chụp đồ vật bất kỳ, không chụp người), rồi bật lại mạng." (người hỗ trợ bật chế độ máy bay trước) | Tin nằm trong hàng đợi khi mất sóng, tự gửi khi có sóng, trên web chỉ có một tin | Người dùng có biết tin chưa gửi đang chờ không; có lo mất tin không |
| NV5 | Nhà tài trợ | "Anh/chị đã góp gạo cho xã. Đây là đường link phiếu xuất kho (người hỗ trợ chạy `bash scripts/demo/luong.sh 6`, mở link ở cửa sổ ẩn danh). Kiểm xem hàng có thật đã xuất và số liệu có bị sửa không." | Người dùng đọc được kết quả tự kiểm và giải thích bằng lời của mình | Có hiểu "đã xác minh" nghĩa là gì không; có tin kết quả không, vì sao |
| NV6 | Điều phối | "Lãnh đạo xã hỏi: còn bao nhiêu tin chưa xử lý, kho còn bao nhiêu gạo, quỹ thu chi thế nào. Trả lời bằng hệ thống." | Trả lời đúng ba con số từ dashboard Grafana | Web điều phối chưa có liên kết sang Grafana: người hỗ trợ đưa địa chỉ `/grafana/`. Có đăng nhập một lần (SSO) mà không bị hỏi lại mật khẩu không; biểu đồ nào khó đọc |

Đoạn tin giả cho NV1 (có thể đổi chi tiết, giữ là dữ liệu giả): *"Cuu voi!! nha toi o thon 2 xa An Lac nuoc len toi mai roi, co 3 nguoi trong do 1 ba cu 80 tuoi. Toa do 15.8461, 108.1158. SDT 0900130xxx"*.

Kho cứu trợ hiện chưa có màn nhập/xuất trên web: phiếu kho lập qua API (`luong.sh 6`), người dùng thử phần kho qua trang Minh bạch (NV5) và tồn kho trên Grafana (NV6). Nếu người dùng hỏi "lập phiếu ở đâu" thì ghi lại, đó là phản hồi.

## 4. Sau mỗi nhiệm vụ và cuối buổi

Sau mỗi nhiệm vụ hỏi ngắn: "Dễ hay khó (1–5)? Chỗ nào làm anh/chị lúng túng?" Cuối buổi hỏi:

1. Nếu đêm lũ thật, anh/chị có dùng hệ thống này không? Vì sao?
2. Việc nào anh/chị đang làm bằng điện thoại, Zalo, giấy bút mà hệ thống này chưa thay được?
3. Một điều cần sửa trước tiên.

## 5. Báo lại phản hồi

- **Mỗi phản hồi một issue**, mẫu [Phản hồi dùng thử](https://github.com/disaster-dxos/disaster-dxos/issues/new?template=phan-hoi-dung-thu.yml), nhãn `user-feedback` tự gắn. Người dùng có tài khoản GitHub thì tự tạo; không có thì người ghi chép tạo thay, ghi rõ "ghi lại từ buổi thử ngày …, vai …".
- **Không ghi** mật khẩu, mã OTP, SĐT, họ tên thật, địa chỉ demo chưa công bố vào issue. Ảnh chụp màn hình che các thông tin đó.
- Người dùng thử muốn được ghi tên thì ghi tên/nick họ đồng ý, trong phần mô tả; không thì để ẩn danh.
- Đội phân loại trong 2 ngày: gắn thêm `bug` hoặc `enhancement`, giao người làm, liên kết PR sửa (`Closes #…`). Phản hồi không sửa trong cuộc thi thì ghi lý do và để mở.
- Cuối giai đoạn thử, tổng hợp số người, số nhiệm vụ tự làm xong, số issue `user-feedback` và số đã sửa vào CHANGELOG của bản phát hành kế tiếp (số liệu thật, không làm tròn lên).
