-- SPDX-License-Identifier: Apache-2.0
-- Kiểm thử hộp thư thông báo cảnh báo (#87, migration 0010) và câu SQL tính đầu đợt của consumer
-- ghi-csdl (cuu_tro_workflow/cam_bien_consumer.py SQL_DAU_DOT), BEGIN … ROLLBACK.
\set QUIET on
\pset tuples_only on

CREATE FUNCTION pg_temp.expect(label text, got text, want text) RETURNS text
LANGUAGE plpgsql AS $$
BEGIN
  IF got IS DISTINCT FROM want THEN
    RAISE EXCEPTION 'FAIL  %: % (mong đợi %)', label, got, want;
  END IF;
  RETURN format('PASS  %s → %s', label, got);
END $$;

CREATE FUNCTION pg_temp.expect_error(label text, stmt text, want_state text) RETURNS text
LANGUAGE plpgsql AS $$
DECLARE got text;
BEGIN
  BEGIN
    EXECUTE stmt;
  EXCEPTION WHEN OTHERS THEN
    GET STACKED DIAGNOSTICS got = RETURNED_SQLSTATE;
    IF got = want_state THEN RETURN format('PASS  %s → %s', label, got); END IF;
    RAISE EXCEPTION 'FAIL  %: SQLSTATE % (mong đợi %)', label, got, want_state;
  END;
  RAISE EXCEPTION 'FAIL  %: câu lệnh chạy được, mong đợi lỗi %', label, want_state;
END $$;

INSERT INTO sensors (id, code, name, kind, unit, location, warning_threshold, danger_threshold)
VALUES ('10000000-0000-4000-8000-0000000000b1', 'THU-CB-01', 'Trạm thử 0010', 'muc_nuoc', 'cm',
        ST_MakePoint(108.2, 15.9)::geography, 300, 400);
-- Hai đợt: 08:00 bình thường, 09:00–10:00 trên ngưỡng (đợt 1 bắt đầu 09:00), 11:00 bình thường,
-- 12:00 trên ngưỡng (đợt 2)
INSERT INTO sensor_readings (sensor_id, observed_at, value, level) VALUES
  ('10000000-0000-4000-8000-0000000000b1', '2026-10-24 08:00+07', 250, 'binh_thuong'),
  ('10000000-0000-4000-8000-0000000000b1', '2026-10-24 09:00+07', 320, 'canh_bao'),
  ('10000000-0000-4000-8000-0000000000b1', '2026-10-24 10:00+07', 410, 'nguy_hiem'),
  ('10000000-0000-4000-8000-0000000000b1', '2026-10-24 11:00+07', 280, 'binh_thuong'),
  ('10000000-0000-4000-8000-0000000000b1', '2026-10-24 12:00+07', 330, 'canh_bao');

CREATE FUNCTION pg_temp.dau_dot(t timestamptz) RETURNS text LANGUAGE sql AS $$
  SELECT to_char(min(observed_at) AT TIME ZONE 'Asia/Ho_Chi_Minh', 'HH24:MI') FROM cuu_tro.sensor_readings
   WHERE sensor_id = '10000000-0000-4000-8000-0000000000b1' AND observed_at <= t AND level <> 'binh_thuong'
     AND observed_at > coalesce((SELECT max(observed_at) FROM cuu_tro.sensor_readings
                                  WHERE sensor_id = '10000000-0000-4000-8000-0000000000b1' AND observed_at < t
                                    AND level = 'binh_thuong'), '-infinity'::timestamptz) $$;
SELECT pg_temp.expect('đầu đợt: vượt ngưỡng 09:00', pg_temp.dau_dot('2026-10-24 09:00+07'), '09:00');
SELECT pg_temp.expect('đầu đợt: lên cấp 10:00 vẫn thuộc đợt 09:00', pg_temp.dau_dot('2026-10-24 10:00+07'), '09:00');
SELECT pg_temp.expect('đầu đợt: về dưới ngưỡng 11:00 đóng đợt 09:00', pg_temp.dau_dot('2026-10-24 11:00+07'), '09:00');
SELECT pg_temp.expect('đầu đợt: lần vượt sau là đợt mới 12:00', pg_temp.dau_dot('2026-10-24 12:00+07'), '12:00');
SELECT pg_temp.expect('đầu đợt: bình thường không có đợt thì NULL', pg_temp.dau_dot('2026-10-24 08:00+07'), NULL);

INSERT INTO sensor_alert_notifications (sensor_code, episode_at, step, value, threshold, unit, observed_at, message, channel)
VALUES ('THU-CB-01', '2026-10-24 09:00+07', 'canh_bao', 320, 300, 'cm', '2026-10-24 09:00+07', 'tin', 'gia-lap');
SELECT pg_temp.expect_error('hộp thư: trùng trạm + đợt + bước bị chặn',
  $q$INSERT INTO sensor_alert_notifications (sensor_code, episode_at, step, value, unit, observed_at, message, channel)
     VALUES ('THU-CB-01', '2026-10-24 09:00+07', 'canh_bao', 1, 'cm', now(), 'x', 'gia-lap')$q$, '23505');
SELECT pg_temp.expect_error('hộp thư: bước lạ bị chặn',
  $q$INSERT INTO sensor_alert_notifications (sensor_code, episode_at, step, value, unit, observed_at, message, channel)
     VALUES ('THU-CB-01', now(), 'cao', 1, 'cm', now(), 'x', 'gia-lap')$q$, '23514');
SELECT pg_temp.expect_error('hộp thư: kênh lạ bị chặn',
  $q$INSERT INTO sensor_alert_notifications (sensor_code, episode_at, step, value, unit, observed_at, message, channel)
     VALUES ('THU-CB-01', now(), 'nguy_hiem', 1, 'cm', now(), 'x', 'sms')$q$, '23514');
SELECT pg_temp.expect_error('hộp thư: da_gui phải có sent_at',
  $q$UPDATE sensor_alert_notifications SET status = 'da_gui' WHERE sensor_code = 'THU-CB-01'$q$, '23514');
SELECT pg_temp.expect_error('hộp thư: trạm không có bị chặn',
  $q$INSERT INTO sensor_alert_notifications (sensor_code, episode_at, step, value, unit, observed_at, message, channel)
     VALUES ('KHONG-CO', now(), 'canh_bao', 1, 'cm', now(), 'x', 'gia-lap')$q$, '23503');

SELECT pg_temp.expect(format('cuu_tro_app %s sensor_alert_notifications.%s', quyen, cot),
                      has_column_privilege('cuu_tro_app', 'cuu_tro.sensor_alert_notifications', cot, quyen)::text,
                      mong_doi::text)
  FROM (VALUES
    ('message', 'INSERT', true), ('status', 'UPDATE', true), ('sent_at', 'UPDATE', true), ('attempts', 'UPDATE', true),
    ('message', 'UPDATE', false), ('step', 'UPDATE', false), ('value', 'UPDATE', false), ('status', 'INSERT', false)
  ) AS t(cot, quyen, mong_doi);
SELECT pg_temp.expect('cuu_tro_app không DELETE được hộp thư',
  has_table_privilege('cuu_tro_app', 'cuu_tro.sensor_alert_notifications', 'DELETE')::text, 'false');

-- Đúng câu lệnh của activity (canh_bao_gui.py SQL_GHI), chạy bằng role cuu_tro_app: lần 2 chỉ tăng attempts
SET LOCAL ROLE cuu_tro_app;
INSERT INTO cuu_tro.sensor_alert_notifications (sensor_code, episode_at, step, previous_level, value, threshold,
                                                unit, observed_at, message, channel)
VALUES ('THU-CB-01', '2026-10-24 09:00+07', 'canh_bao', 'binh_thuong', 320, 300, 'cm', '2026-10-24 09:00+07', 'tin',
        'gia-lap')
ON CONFLICT (sensor_code, episode_at, step) DO UPDATE SET attempts = sensor_alert_notifications.attempts + 1
RETURNING attempts || ' ' || status AS kq_ghi \gset
SELECT pg_temp.expect('activity ghi hộp thư bằng cuu_tro_app, chạy lại chỉ tăng attempts', :'kq_ghi', '2 dang_gui');
RESET ROLE;
