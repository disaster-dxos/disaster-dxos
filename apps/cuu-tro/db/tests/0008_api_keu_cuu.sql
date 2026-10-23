-- SPDX-License-Identifier: Apache-2.0
-- Kiểm thử đường tạo tin của API kêu cứu (#66), chạy trong BEGIN … ROLLBACK như 0001.
-- INSERT thật bằng role dịch vụ cuu_tro_app (phiên test là superuser nên SET ROLE được), đúng câu lệnh
-- của API (cuu_tro_workflow/api.py SoTin). SĐT giả 0900066xxx. Gửi đồng thời (hai phiên) không làm được
-- trong một phiên psql: kiểm ở scripts/smoke-keu-cuu.sh.
\set QUIET on
\pset tuples_only on

CREATE FUNCTION pg_temp.expect(label text, got anyelement, want anyelement) RETURNS text
LANGUAGE plpgsql AS $$
BEGIN
  IF got IS DISTINCT FROM want THEN
    RAISE EXCEPTION 'FAIL  %: % (mong đợi %)', label, got, want;
  END IF;
  RETURN format('PASS  %s → %s', label, got);
END $$;

-- Chạy stmt, trả "SQLSTATE|constraint|detail" (rỗng nếu chạy được). EXECUTE giữ role hiện tại của phiên.
CREATE FUNCTION pg_temp.loi(stmt text) RETURNS text
LANGUAGE plpgsql AS $$
DECLARE st text; cn text; dt text;
BEGIN
  EXECUTE stmt;
  RETURN '';
EXCEPTION WHEN OTHERS THEN
  GET STACKED DIAGNOSTICS st = RETURNED_SQLSTATE, cn = CONSTRAINT_NAME, dt = PG_EXCEPTION_DETAIL;
  RETURN st || '|' || coalesce(cn, '') || '|' || coalesce(dt, '');
END $$;

-- Câu INSERT của API; tọa độ (lon, lat)
CREATE FUNCTION pg_temp.tao(sdt text, lon double precision, lat double precision) RETURNS text
LANGUAGE sql AS $$
  SELECT format($f$INSERT INTO cuu_tro.incidents (description, location, address_text, people_count, urgency,
                     reporter_phone, reporter_name, source, created_by)
                   VALUES ('[test 0008] kêu cứu', ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, NULL, 2,
                           'cao', %L, NULL, 'app', 'sub-test-0008')
                   RETURNING id, status, urgency, people_count, created_at$f$, lon, lat, sdt)
$$;
GRANT EXECUTE ON FUNCTION pg_temp.loi(text), pg_temp.tao(text, double precision, double precision) TO cuu_tro_app;

-- ---------- Quyền ----------
SELECT pg_temp.expect(format('cuu_tro_app %s incidents.%s', quyen, cot),
                      has_column_privilege('cuu_tro_app', 'cuu_tro.incidents', cot, quyen), mong_doi)
  FROM (VALUES
    ('description', 'INSERT', true), ('location', 'INSERT', true), ('reporter_phone', 'INSERT', true),
    ('created_by', 'INSERT', true), ('urgency', 'INSERT', true),
    ('status', 'INSERT', false), ('assigned_team_id', 'INSERT', false), ('created_at', 'INSERT', false),
    ('created_at', 'SELECT', true),
    -- API không đọc lại dữ liệu cá nhân
    ('reporter_phone', 'SELECT', false), ('reporter_name', 'SELECT', false), ('created_by', 'SELECT', false)
  ) AS t(cot, quyen, mong_doi);
SELECT pg_temp.expect('trigger chặn trùng chạy với quyền chủ bảng (SECURITY DEFINER)',
  (SELECT prosecdef FROM pg_proc WHERE oid = 'cuu_tro.incidents_block_duplicate()'::regprocedure), true);
SELECT pg_temp.expect('tham số chặn trùng: 200 m, 360 phút',
  (SELECT radius_m || ' m, ' || window_minutes || ' phút' FROM incident_dedup_config), '200 m, 360 phút');

-- ---------- Tạo tin bằng cuu_tro_app (lat 16.3, lon 108.3: 0.0017° vĩ độ ≈ 188 m, 0.0020° ≈ 221 m) ----------
RESET ROLE;
SET ROLE cuu_tro_app;
SELECT pg_temp.expect('cuu_tro_app tạo tin hợp lệ', pg_temp.loi(pg_temp.tao('0900066001', 108.3, 16.3)), '');
SELECT pg_temp.expect('thiếu tọa độ → 23502',
  split_part(pg_temp.loi(replace(pg_temp.tao('0900066009', 108.3, 16.3),
                                 'ST_SetSRID(ST_MakePoint(108.3, 16.3), 4326)::geography', 'NULL')), '|', 1), '23502');
SELECT pg_temp.expect('SĐT sai định dạng → 23514 (domain phone_vn)',
  split_part(pg_temp.loi(pg_temp.tao('12345', 108.31, 16.31)), '|', 1), '23514');
SELECT pg_temp.expect('cùng SĐT, cách ~188 m, tin còn mở → 23505 incidents_no_duplicate',
  split_part(pg_temp.loi(pg_temp.tao('0900066001', 108.3, 16.3017)), '|', 1) || '|' ||
  split_part(pg_temp.loi(pg_temp.tao('0900066001', 108.3, 16.3017)), '|', 2), '23505|incidents_no_duplicate');
SELECT pg_temp.expect('DETAIL đúng dạng API đọc được (incident_id, distance_m, radius_m, window_minutes)',
  split_part(pg_temp.loi(pg_temp.tao('0900066001', 108.3, 16.3017)), '|', 3)
    ~ '^incident_id=[0-9a-f-]{36} distance_m=1[89][0-9] radius_m=200 window_minutes=360$', true);
SELECT pg_temp.expect('khác SĐT, cùng chỗ → tạo được', pg_temp.loi(pg_temp.tao('0900066002', 108.3, 16.3)), '');
SELECT pg_temp.expect('cùng SĐT, cách ~221 m (ngoài 200 m) → tạo được',
  pg_temp.loi(pg_temp.tao('0900066001', 108.3, 16.3020)), '');
RESET ROLE;
SET ROLE cuu_tro_owner;

SELECT pg_temp.expect('tin tạo bằng API: tiep_nhan, chưa đội, created_by từ token, vào hàng đợi phân công',
  (SELECT count(*) FILTER (WHERE i.status = 'tiep_nhan' AND i.assigned_team_id IS NULL
                             AND i.created_by = 'sub-test-0008' AND q.incident_id IS NOT NULL)
     FROM incidents i LEFT JOIN assignment_queue q ON q.incident_id = i.id
    WHERE i.description = '[test 0008] kêu cứu'), 3::bigint);
SELECT pg_temp.expect('tin trùng không được tạo (chỉ 2 tin của 0900066001)',
  (SELECT count(*) FROM incidents WHERE reporter_phone = '0900066001'), 2::bigint);
