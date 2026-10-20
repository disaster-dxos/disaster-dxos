-- SPDX-License-Identifier: Apache-2.0
-- Kiểm thử bảng sensor_readings và quyền của cuu_tro_app trên luồng cảm biến (#30), BEGIN … ROLLBACK.
\set QUIET on
\pset tuples_only on

CREATE FUNCTION pg_temp.expect(label text, got boolean, want boolean) RETURNS text
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
VALUES ('10000000-0000-4000-8000-0000000000a1', 'THU-MN-01', 'Trạm thử', 'muc_nuoc', 'cm',
        ST_MakePoint(108.1, 15.85)::geography, 300, 400);
INSERT INTO sensor_readings (sensor_id, observed_at, value, level)
VALUES ('10000000-0000-4000-8000-0000000000a1', '2026-10-20 08:00+07', 280, 'binh_thuong');

SELECT pg_temp.expect_error('sensor_readings: trùng trạm + thời điểm bị chặn',
  $q$INSERT INTO sensor_readings (sensor_id, observed_at, value, level)
     VALUES ('10000000-0000-4000-8000-0000000000a1', '2026-10-20 08:00+07', 281, 'binh_thuong')$q$, '23505');
SELECT pg_temp.expect_error('sensor_readings: mức không hợp lệ bị chặn',
  $q$INSERT INTO sensor_readings (sensor_id, observed_at, value, level)
     VALUES ('10000000-0000-4000-8000-0000000000a1', now(), 1, 'cao')$q$, '23514');
SELECT pg_temp.expect_error('sensor_readings: trạm không tồn tại bị chặn',
  $q$INSERT INTO sensor_readings (sensor_id, observed_at, value, level)
     VALUES (gen_random_uuid(), now(), 1, 'binh_thuong')$q$, '23503');
DELETE FROM sensors WHERE id = '10000000-0000-4000-8000-0000000000a1';
SELECT pg_temp.expect('sensor_readings: xóa trạm thì xóa chuỗi đo (ON DELETE CASCADE)',
  NOT EXISTS (SELECT FROM sensor_readings WHERE sensor_id = '10000000-0000-4000-8000-0000000000a1'), true);
SELECT pg_temp.expect('sensor_readings: có chỉ mục (sensor_id, observed_at)',
  EXISTS (SELECT FROM pg_indexes WHERE schemaname = 'cuu_tro' AND tablename = 'sensor_readings'
           AND indexdef LIKE '%(sensor_id, observed_at)%'), true);

-- Quyền của consumer (cuu_tro_app)
SELECT pg_temp.expect(format('cuu_tro_app %s %s.%s', quyen, bang, cot),
                      has_column_privilege('cuu_tro_app', 'cuu_tro.' || bang, cot, quyen), mong_doi)
  FROM (VALUES
    ('sensors', 'code', 'SELECT', true),
    ('sensors', 'danger_threshold', 'SELECT', true),
    ('sensors', 'last_value', 'UPDATE', true),
    ('sensors', 'last_observed_at', 'UPDATE', true),
    ('sensors', 'warning_threshold', 'UPDATE', false),
    ('sensors', 'danger_threshold', 'UPDATE', false),
    ('sensors', 'name', 'UPDATE', false),
    ('sensors', 'active', 'UPDATE', false)
  ) AS t(bang, cot, quyen, mong_doi);
SELECT pg_temp.expect(format('cuu_tro_app %s cuu_tro.%s', quyen, bang),
                      has_table_privilege('cuu_tro_app', 'cuu_tro.' || bang, quyen), mong_doi)
  FROM (VALUES
    ('sensor_readings', 'INSERT', true), ('sensor_readings', 'SELECT', true),
    ('sensor_readings', 'UPDATE', false), ('sensor_readings', 'DELETE', false),
    ('sensors', 'INSERT', false), ('sensors', 'DELETE', false)
  ) AS t(bang, quyen, mong_doi);
