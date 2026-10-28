<!-- SPDX-License-Identifier: Apache-2.0 -->
# Rà soát UX app hiện trường (#113)

Phạm vi: app React Native `apps/cuu-tro/mobile/` (D-011) cho tình nguyện viên và đội cứu hộ. Có 4 tiêu chí, lấy từ tuần 6 của `docs/PLAN.md`: **thao tác một tay**, **mạng yếu**, **chữ lớn**, **tương phản**. Bối cảnh người dùng: điện thoại phổ thông, ngoài trời, nắng gắt hoặc mưa, tay ướt hoặc đeo găng, sóng chập chờn, đang căng thẳng.

Cách rà: đọc mã từng màn và thành phần dùng chung, tính tỷ lệ tương phản WCAG 2.2 của mọi cặp màu đang dùng, đối chiếu với HIG/Material, WCAG 2.2 AA và nguyên tắc sản phẩm ("không để người dùng tưởng dữ liệu cũ là mới", "bấm được bằng một tay"). Lần này chưa chạy trên máy thật vì máy dựng không có Android SDK và Xcode (xem mục cuối).

Mức độ: **P0** chặn việc · **P1** khó khăn lớn hoặc vi phạm chuẩn · **P2** phiền, có cách khác · **P3** trau chuốt.

## Kết quả

| # | Tiêu chí | Phát hiện | Vị trí | Mức | Xử lý |
|---|---|---|---|---|---|
| 1 | Tương phản | Nút chính **Gửi tin kêu cứu** và huy hiệu tab Hàng đợi dùng chữ trắng trên cam `#F07B1D`, chỉ đạt 2,78:1 (AA cần 4,5:1). Ngoài nắng gần như không đọc được đúng nút quan trọng nhất | `Nut.tsx` (kiểu `cam`), `MainTabs.tsx` | P1 | Đã sửa: chữ tối `#0F1B2D` trên cam, đạt 6,2:1, giữ màu cam nhận diện |
| 2 | Tương phản | Viền ô nhập, ô chọn, nút phụ là `#D5DCE5`, chỉ 1,38:1 (WCAG 1.4.11 cần 3:1). Ngoài trời không thấy ô nhập ở đâu | `OVanBan.tsx`, `ChonMuc.tsx`, `Nut.tsx` (kiểu `phu`) | P1 | Đã sửa: token mới `vienO` `#6B7A8C`, đạt ≥ 3:1 trên nền trắng và nền xám. Viền thẻ (chỉ trang trí) giữ nguyên |
| 3 | Tương phản | Chữ phụ (trạng thái, địa chỉ, mô tả màn) `#475569` trên nền màn chỉ đạt 7,0:1, sát mức AAA | `theme/mau.ts` | P3 | Đã sửa: `#424F63`, đạt 7,7:1 |
| 4 | Một tay | Nút Gửi ở chân màn, nhưng khi form sai thì lỗi hiện ở các ô phía trên đã cuộn khuất. Người dùng một tay bấm Gửi và thấy như không có gì xảy ra | `KeuCuuScreen.tsx` | P1 | Đã sửa: tóm tắt lỗi hiện ngay trên nút Gửi ("còn 3 ô cần sửa: Vị trí, SĐT, Tình hình"), trình đọc màn hình đọc to, màn tự cuộn tới ô lỗi đầu tiên, chạm vào tóm tắt cũng cuộn tới đó. Sửa ô nào thì lỗi ô đó tắt ngay |
| 5 | Một tay | Ở màn Dán tin, hai nút Bóc tách / Chuyển cho điều phối nằm giữa nội dung. Sau khi dán tin dài, bàn phím che nút | `DanTinScreen.tsx` | P2 | Đã sửa: hai nút chuyển xuống chân màn, luôn ở trên bàn phím và trong tầm ngón cái |
| 6 | Một tay | Chân màn của các màn trong ngăn xếp (Dán tin, Chọn vị trí) không chừa vùng an toàn dưới, nên nút nằm dưới thanh cử chỉ/home indicator. Android 15 (targetSdk 35) bắt buộc edge-to-edge, dễ vuốt về màn chính khi định bấm nút | `ManHinh.tsx`, `ChonViTriScreen.tsx` | P1 | Đã sửa: chân màn đệm theo vùng an toàn dưới. Màn trong tab không bị đệm thừa |
| 7 | Mạng yếu | Đội cứu hộ tắt máy cho đỡ pin rồi mở lại ở chỗ mất sóng: danh sách nhiệm vụ trống vì cache chỉ nằm trong bộ nhớ, và không cập nhật được vị trí đội vì thiếu mã đội | `useDuLieuHienTruong.ts` | P1 | Đã sửa: bản sao danh sách tin và đội lưu **mã hóa** trong Keychain/Keystore như hàng đợi, gắn với người dùng + vai, bỏ bản quá 7 ngày (`services/banSao.ts`) |
| 8 | Mạng yếu | Danh sách Hiện trường không nói dữ liệu tải lúc nào. Mất mạng thì người dùng dễ tưởng danh sách cũ là mới (trái nguyên tắc sản phẩm 2) | `HienTruongScreen.tsx` | P1 | Đã sửa: dòng "Cập nhật … phút trước", tự cập nhật mỗi 30 giây. Mất mạng thì có khung "Mất mạng: đang xem danh sách đã tải 12 phút trước, có thể đã cũ" và không báo thêm lỗi tải |
| 9 | Mạng yếu | GPS trong nhà hoặc dưới mưa có thể lệch hàng trăm mét mà app không cho biết, đội cứu hộ tới sai chỗ | `KeuCuuScreen.tsx`, `useViTri.ts` | P1 | Đã sửa: hiện sai số ("GPS sai số khoảng 12 m"). Từ 100 m trở lên thì cảnh báo, gợi ý ra chỗ thoáng hoặc chỉnh trên bản đồ. Vị trí chọn tay hoặc lấy từ tin nhắn không mang sai số GPS cũ |
| 10 | Mạng yếu | Mất mạng thì nền bản đồ trắng mà không có lời giải thích, người dùng tưởng app hỏng | `KeuCuuScreen.tsx`, `ChonViTriScreen.tsx`, `ChiTietTinScreen.tsx` | P2 | Đã sửa: báo "nền bản đồ có thể không hiện, vị trí GPS vẫn lấy được". Gói bản đồ offline chưa làm (mục dưới) |
| 11 | Mạng yếu | Bóc tách AI lỗi (mạng yếu, AI quá 120 giây) chỉ báo lỗi, không chỉ lối khác | `DanTinScreen.tsx` | P2 | Đã sửa: gợi ý ngay "Chuyển cho điều phối duyệt" (không cần chờ mạng) |
| 12 | Chữ lớn | Băng "Mất mạng / đang chờ gửi" (thông tin quan trọng nhất của màn) và chữ báo lỗi dưới ô chỉ 14 sp | `BangMang.tsx`, `OVanBan.tsx` | P1 | Đã sửa: 17 sp đậm, biểu tượng 24 dp |
| 13 | Chữ lớn | Hàng nhãn (mức khẩn + trạng thái + mã tin, loại bản ghi + trạng thái) không xuống dòng, tràn khi phóng to chữ hệ thống | `HienTruongScreen.tsx`, `ChiTietTinScreen.tsx`, `TheBanGhi.tsx` | P2 | Đã sửa: cho xuống dòng. Trạng thái tin lên cỡ chữ thường |
| 14 | Chữ lớn | Hai nút cạnh nhau (Lấy GPS / Chọn trên bản đồ, Gửi lại / Xóa) bị ngắt chữ vụn khi phóng to chữ | `KeuCuuScreen.tsx`, `TheBanGhi.tsx` | P2 | Đã sửa: từ mức phóng to 1,3× thì xếp dọc (`hooks/useChuLon.ts`). App không chặn phóng to chữ ở đâu |
| 15 | Trợ năng | Nhãn trợ năng của bản đồ là chữ tiếng Anh cố định "map" | `BanDo.tsx` | P3 | Đã sửa: nhãn theo ngôn ngữ, nói rõ "chạm để đặt ghim" khi chọn vị trí |

Giữ nguyên vì đã ổn:
- vùng chạm ≥ 52 dp;
- nhãn chữ luôn đi kèm biểu tượng, trạng thái hàng đợi có cả chữ lẫn biểu tượng (không chỉ màu), ô đang chọn có dấu tích;
- xác nhận trước khi xóa bản ghi chưa gửi và trước khi đăng xuất khi còn bản ghi chờ;
- băng mất mạng nói rõ dữ liệu vẫn được giữ;
- chỉ có giao diện sáng, cố ý vì dùng ngoài nắng.

## Kiểm thử chống tái phạm

- `__tests__/tuongPhan.test.ts`:
  - tính tỷ lệ WCAG cho mọi cặp màu khai báo trong `CAP_MAU` (`src/theme/mau.ts`);
  - chữ đọc chính ≥ 7:1, mọi chữ khác ≥ 4,5:1, viền thành phần ≥ 3:1;
  - thêm màu hoặc cặp mới thì thêm vào `CAP_MAU`.
- `__tests__/KeuCuuScreen.test.tsx`:
  - tóm tắt lỗi được đọc to, cập nhật khi sửa từng ô;
  - sai số GPS, cảnh báo khi sai số lớn;
  - báo nền bản đồ khi mất mạng;
  - nút xếp dọc khi chữ lớn.
- `__tests__/HienTruongScreen.test.tsx`:
  - mở lại app khi mất mạng thì hiện bản sao kèm thời điểm đã tải;
  - bản sao của người khác không hiện;
  - có mạng thì ghi bản sao;
  - gợi ý "Chuyển cho điều phối" khi bóc tách lỗi;
  - ngưỡng chữ lớn, thẻ hàng đợi, cỡ chữ băng mạng.
- `__tests__/banSao.test.ts`: lưu trong Keychain chỉ trên máy này, gắn người dùng + vai, bỏ bản hỏng, quá cũ, ở tương lai; kho lỗi không làm hỏng màn hình.

## Chưa làm

- **Thử trên máy thật** (P1, cần máy có Android SDK hoặc Xcode, hoặc bản APK do CI dựng). Cần kiểm:
  - cỡ chữ hệ thống lớn nhất (Android 200 %, iOS Accessibility Sizes);
  - TalkBack/VoiceOver đọc tóm tắt lỗi;
  - ngoài nắng thật;
  - thanh cử chỉ Android 15;
  - chạy trên máy RAM 3 GB.
- **Gói bản đồ offline** (P2): tải trước ô bản đồ vùng xã (MapLibre offline pack). Hiện mất mạng vẫn có tọa độ GPS và chữ báo.
- **Thử với người dùng thật** (tình nguyện viên, đội cứu hộ): chờ demo công khai trên VPS. Mỗi phản hồi một issue `user-feedback` (việc đầu tiên của tuần 6).
