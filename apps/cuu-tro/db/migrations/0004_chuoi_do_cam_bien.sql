-- SPDX-License-Identifier: Apache-2.0
-- Chuỗi đo cảm biến (#30): bản tin MQTT → NATS JetStream → consumer cuu-tro-cam-bien → bảng này,
-- đồng thời cập nhật sensors.last_value / last_observed_at (lần đo mới nhất).
-- Mỗi (trạm, thời điểm đo) chỉ một dòng: bản tin gửi lại (JetStream giao lại khi chưa ack) không
-- tạo dòng trùng (ON CONFLICT DO NOTHING). Ràng buộc UNIQUE đồng thời là chỉ mục theo trạm + thời gian
-- cho truy vấn "chuỗi đo của trạm X trong khoảng thời gian" và "lần đo trước đó".

CREATE TABLE sensor_readings (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sensor_id   uuid NOT NULL REFERENCES sensors (id) ON DELETE CASCADE,
  -- Thời điểm thiết bị đo (trong bản tin), khác thời điểm lõi nhận được
  observed_at timestamptz NOT NULL,
  value       numeric(10, 2) NOT NULL,
  -- Mức so với ngưỡng của trạm TẠI LÚC ghi (ngưỡng có thể đổi sau đó)
  level       text NOT NULL CHECK (level IN ('binh_thuong', 'canh_bao', 'nguy_hiem')),
  received_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT sensor_readings_sensor_time_key UNIQUE (sensor_id, observed_at)
);
-- Dọn dữ liệu cũ / chuyển sang Parquet (tuần 4) quét theo thời gian nhận: BRIN nhỏ, hợp bảng chỉ thêm
CREATE INDEX sensor_readings_received_brin ON sensor_readings USING brin (received_at);

COMMENT ON TABLE sensor_readings IS 'Chuỗi đo của trạm cảm biến (từ NATS JetStream), mỗi trạm + thời điểm một dòng';
COMMENT ON COLUMN sensor_readings.level IS 'binh_thuong | canh_bao (>= ngưỡng cảnh báo) | nguy_hiem (>= ngưỡng nguy hiểm)';

-- Quyền tối thiểu cho consumer (role dịch vụ cuu_tro_app, như 0003): đọc thông tin trạm + ngưỡng,
-- ghi lần đo cuối; thêm và đọc chuỗi đo (đọc lần đo trước để quyết định phát cảnh báo).
-- Không UPDATE/DELETE chuỗi đo, không đổi ngưỡng hay tên trạm.
GRANT SELECT (id, code, name, kind, unit, warning_threshold, danger_threshold,
              last_value, last_observed_at, active)
  ON sensors TO cuu_tro_app;
GRANT UPDATE (last_value, last_observed_at) ON sensors TO cuu_tro_app;
GRANT SELECT, INSERT ON sensor_readings TO cuu_tro_app;
