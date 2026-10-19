# Kế hoạch Team 1 – Disaster DX-OS

Lịch làm việc: Thứ 2 – Thứ 4. Đánh dấu [x] khi xong (dùng `/update-mapping`). Việc gắn (SV) nên giao sinh viên tự làm và commit.

## Tuần 1 · 15–21/10 · Nền móng → v0.0.1
- [x] Xác minh LICENSE trên GitHub chính thức: Stellio, Scorpio (chọn 1), Hasura v2, immudb, Centrifugo, SeaweedFS → ghi NOTICE + DECISIONS (D-004: chọn Scorpio, loại immudb, Hasura `-ce`)
- [x] `docs/architecture.md`: sơ đồ 3 tầng (Mermaid) + luồng dữ liệu kêu cứu và cảm biến
- [x] `docker-compose.yml` profile `core` bước 1: PostgreSQL+PostGIS, Keycloak, APISIX (standalone, không etcd); `.env.example`
- [ ] Tạo repo GitHub công khai, bật Issues, đẩy khung; tạo issue cho các việc tuần 2
- [ ] Release v0.0.1

## Tuần 2 · 22–28/10 · Lõi headless → v0.1.0
- [ ] Schema PostGIS: incidents, rescue_teams, shelters, supplies, sensors (migration)
- [ ] Hasura trên schema, phân quyền theo vai trò Keycloak (JWT claims)
- [ ] APISIX: route `/graphql`, `/files`, `/workflow`, xác thực JWT Keycloak
- [ ] SeaweedFS S3 + API tải ảnh hiện trường
- [ ] Temporal server + worker Python "hello" gọi được qua gateway
- [ ] NATS JetStream bật MQTT
- [ ] OpenBao giữ bí mật DB/Keycloak client
- [ ] README: hướng dẫn chạy từ máy sạch · Release v0.1.0

## Tuần 3 · 29/10–04/11 · Luồng nghiệp vụ chính
- [ ] API kêu cứu + Poka-yoke (bắt buộc tọa độ, chặn trùng SĐT trong bán kính 200 m)
- [ ] Temporal workflow: tiếp nhận → phân công đội gần nhất → xác nhận đã cứu → đóng
- [ ] Web Nuxt: đăng nhập Keycloak, bản đồ MapLibre hiển thị sự cố realtime (subscription) (SV)
- [ ] Màn hình phân công + cập nhật trạng thái (SV)

## Tuần 4 · 05–11/11 · Tầng [D] → v0.2.0
- [ ] Mô phỏng cảm biến mực nước (Python → MQTT) (SV)
- [ ] NATS → broker NGSI-LD: thực thể trạm đo (bản sao số)
- [ ] Cảnh báo vượt ngưỡng → Temporal → thông báo
- [ ] Transparency log (Tessera đề xuất / Trillian, chốt ở tuần 2 – D-004): niêm phong nhập/xuất hàng cứu trợ + endpoint xác minh
- [ ] Xuất dữ liệu cũ ra Parquet + truy vấn DuckDB
- [ ] Grafana dashboard điều hành (SV) · Release v0.2.0

## Tuần 5 · 12–18/11 · Tầng [I] + demo công khai
- [ ] Ollama + Qwen2.5 7B (không dùng 3B): bóc tách tin kêu cứu tự do → JSON (địa chỉ, số người, mức khẩn cấp)
- [ ] Hàng chờ duyệt HITL trên web điều phối (SV)
- [ ] App Flutter: gửi kêu cứu/cập nhật hiện trường, hàng đợi offline (SV)
- [ ] Triển khai demo công khai trên Internet, mời người dùng thử

## Tuần 6 · 19–25/11 · Hoàn thiện → v0.3.0
- [ ] Sửa lỗi theo phản hồi, ghi issue từ người dùng ngoài
- [ ] README song ngữ đầy đủ, hướng dẫn viết module cắm–rút + 1 module mẫu
- [ ] Release v0.3.0

## Tuần 7 · 26/11–06/12 · Nộp bài → v1.0.0
- [ ] `/pof-check` đạt toàn bộ · đóng băng tính năng · `/release 1.0.0`
- [ ] Gửi email nộp bài (xem `docs/contest/`)
- [ ] Slide 15 phút + video demo dự phòng
