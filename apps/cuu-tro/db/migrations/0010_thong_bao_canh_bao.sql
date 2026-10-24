-- SPDX-License-Identifier: Apache-2.0
-- Hộp thư nội bộ của thông báo cảnh báo vượt ngưỡng (#87). Workflow CanhBaoVuotNguong (Temporal) gọi
-- activity gui_canh_bao (cuu_tro_workflow/canh_bao_gui.py, role cuu_tro_app) cho mỗi BƯỚC của một ĐỢT:
--   canh_bao | nguy_hiem (vượt ngưỡng / lên cấp) | ve_duoi_nguong (kết thúc đợt).
-- Mỗi (trạm, đợt, bước) đúng một dòng: activity chạy lại chỉ tăng attempts, dòng đã sent không gửi lại.
-- Ở kênh "gia-lap" (mặc định) đây là nơi nhận tin; ở kênh "telegram" là nhật ký đã gửi. Điều phối đọc qua
-- /graphql (Hasura). Không có dữ liệu cá nhân: chỉ trạm, giá trị đo, nội dung tin.

CREATE TABLE sensor_alert_notifications (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sensor_code    text NOT NULL REFERENCES sensors (code) ON UPDATE CASCADE ON DELETE CASCADE,
  -- Mã đợt: thời điểm lần đo đầu tiên trên ngưỡng của đợt (sự kiện cảnh báo mang trường "dot")
  episode_at     timestamptz NOT NULL,
  step           text NOT NULL CHECK (step IN ('canh_bao', 'nguy_hiem', 've_duoi_nguong')),
  previous_level text CHECK (previous_level IN ('binh_thuong', 'canh_bao', 'nguy_hiem')),
  value          numeric(10, 2) NOT NULL,
  threshold      numeric(10, 2),
  unit           text NOT NULL,
  observed_at    timestamptz NOT NULL,
  message        text NOT NULL CHECK (length(message) <= 2000),
  channel        text NOT NULL CHECK (channel IN ('gia-lap', 'telegram')),
  status         text NOT NULL DEFAULT 'dang_gui' CHECK (status IN ('dang_gui', 'da_gui', 'loi')),
  detail         text CHECK (length(detail) <= 500),
  attempts       integer NOT NULL DEFAULT 1 CHECK (attempts >= 1),
  created_at     timestamptz NOT NULL DEFAULT now(),
  sent_at        timestamptz,
  CONSTRAINT sensor_alert_notifications_once UNIQUE (sensor_code, episode_at, step),
  CHECK ((status = 'da_gui') = (sent_at IS NOT NULL))
);
CREATE INDEX sensor_alert_notifications_created_idx ON sensor_alert_notifications (created_at DESC);

COMMENT ON TABLE sensor_alert_notifications IS 'Thông báo cảnh báo vượt ngưỡng đã gửi (#87): mỗi trạm + đợt + bước một dòng';
COMMENT ON COLUMN sensor_alert_notifications.episode_at IS 'Đợt vượt ngưỡng: thời điểm lần đo đầu tiên trên ngưỡng';
COMMENT ON COLUMN sensor_alert_notifications.step IS 'canh_bao | nguy_hiem | ve_duoi_nguong';
COMMENT ON COLUMN sensor_alert_notifications.channel IS 'Kênh ngoài lúc gửi: gia-lap (chỉ hộp thư + web) | telegram';

-- Quyền tối thiểu cho activity (role dịch vụ cuu_tro_app): thêm dòng, đọc lại, cập nhật trạng thái gửi.
-- Không DELETE, không sửa nội dung đã ghi.
GRANT SELECT, INSERT (sensor_code, episode_at, step, previous_level, value, threshold, unit, observed_at, message,
                      channel)
  ON sensor_alert_notifications TO cuu_tro_app;
GRANT UPDATE (status, detail, sent_at, attempts) ON sensor_alert_notifications TO cuu_tro_app;
