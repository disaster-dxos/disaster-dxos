-- SPDX-License-Identifier: Apache-2.0
-- Kiểm thử phân công tự động (#67): outbox khi có tin mới, thứ tự urgency, luật nhường đội, lịch sử
-- giao nhiệm vụ, quyền của cuu_tro_app. Chạy trong BEGIN … ROLLBACK như 0001 (NOTIFY không gửi đi).
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

-- Dữ liệu riêng của bài kiểm (giả, ở xa tin seed để không dính luật chặn trùng)
INSERT INTO rescue_teams (id, name, member_count, location, location_updated_at, status, contact_phone) VALUES
  ('a7000000-0000-4000-8000-000000000001', '[test 0007] đội gần', 5, ST_MakePoint(107.500, 15.500)::geography, now(), 'san_sang', '0907000010'),
  ('a7000000-0000-4000-8000-000000000002', '[test 0007] đội rất xa', 5, ST_MakePoint(106.000, 14.000)::geography, now(), 'san_sang', '0907000020');
INSERT INTO incidents (id, description, location, urgency, status, reporter_phone, assigned_team_id) VALUES
  ('b7000000-0000-4000-8000-000000000001', '[test 0007] thấp', ST_MakePoint(107.501, 15.501)::geography, 'thap', 'tiep_nhan', '0917000010', NULL),
  ('b7000000-0000-4000-8000-000000000002', '[test 0007] khẩn cấp', ST_MakePoint(107.505, 15.505)::geography, 'khan_cap', 'tiep_nhan', '0917000020', NULL),
  ('b7000000-0000-4000-8000-000000000003', '[test 0007] đã phân công sẵn', ST_MakePoint(107.510, 15.510)::geography, 'cao', 'phan_cong', '0917000030',
   'a7000000-0000-4000-8000-000000000002');

-- ---------- Outbox ----------
SELECT pg_temp.expect('tin tiep_nhan mới → có dòng trong assignment_queue',
  (SELECT count(*) FROM assignment_queue WHERE incident_id IN ('b7000000-0000-4000-8000-000000000001', 'b7000000-0000-4000-8000-000000000002')), 2::bigint);
SELECT pg_temp.expect('tin tạo sẵn ở phan_cong → không vào hàng đợi',
  (SELECT count(*) FROM assignment_queue WHERE incident_id = 'b7000000-0000-4000-8000-000000000003'), 0::bigint);
SELECT pg_temp.expect('dòng mới chưa khởi chạy (started_at NULL, attempts 0)',
  (SELECT bool_and(started_at IS NULL AND attempts = 0 AND seeking_at IS NULL) FROM assignment_queue
    WHERE incident_id::text LIKE 'b7000000-%'), true);
SET LOCAL cuu_tro.tu_phan_cong = off;
INSERT INTO incidents (id, description, location, urgency, reporter_phone) VALUES
  ('b7000000-0000-4000-8000-000000000004', '[test 0007] nạp seed', ST_MakePoint(107.520, 15.520)::geography, 'cao', '0917000040');
SELECT pg_temp.expect('cuu_tro.tu_phan_cong = off (seed) → không vào hàng đợi',
  (SELECT count(*) FROM assignment_queue WHERE incident_id = 'b7000000-0000-4000-8000-000000000004'), 0::bigint);
RESET cuu_tro.tu_phan_cong;
SELECT pg_temp.expect('trigger outbox chạy với quyền chủ bảng (SECURITY DEFINER)',
  (SELECT prosecdef FROM pg_proc WHERE oid = 'cuu_tro.incidents_enqueue_assignment()'::regprocedure), true);
INSERT INTO assignment_queue (incident_id) VALUES ('b7000000-0000-4000-8000-000000000004');
DELETE FROM incidents WHERE id = 'b7000000-0000-4000-8000-000000000004';
SELECT pg_temp.expect('xóa tin → xóa dòng hàng đợi (ON DELETE CASCADE)',
  (SELECT count(*) FROM assignment_queue WHERE incident_id = 'b7000000-0000-4000-8000-000000000004'), 0::bigint);

-- ---------- Thứ tự urgency ----------
SELECT pg_temp.expect('urgency_rank: khan_cap < cao < trung_binh < thap',
  (SELECT array_agg(u ORDER BY urgency_rank(u)) FROM unnest(ARRAY['thap', 'cao', 'khan_cap', 'trung_binh']) AS u),
  ARRAY['khan_cap', 'cao', 'trung_binh', 'thap']);
SELECT pg_temp.expect('hàng đợi lấy tin khẩn cấp trước dù tạo sau',
  (SELECT array_agg(i.urgency ORDER BY urgency_rank(i.urgency), q.created_at)
     FROM assignment_queue q JOIN incidents i ON i.id = q.incident_id WHERE q.incident_id::text LIKE 'b7000000-%'),
  ARRAY['khan_cap', 'thap']);

-- ---------- Luật nhường đội ----------
SELECT pg_temp.expect('chưa có tin nào đang tìm đội → không nhường',
  team_reserved_for_more_urgent('b7000000-0000-4000-8000-000000000001', 'a7000000-0000-4000-8000-000000000001', 20000, 150), false);
UPDATE assignment_queue SET seeking_at = now() WHERE incident_id = 'b7000000-0000-4000-8000-000000000002';
SELECT pg_temp.expect('tin khẩn cấp đang tìm đội trong bán kính → tin thấp nhường đội gần',
  team_reserved_for_more_urgent('b7000000-0000-4000-8000-000000000001', 'a7000000-0000-4000-8000-000000000001', 20000, 150), true);
SELECT pg_temp.expect('đội ngoài bán kính của tin khẩn cấp → không nhường',
  team_reserved_for_more_urgent('b7000000-0000-4000-8000-000000000001', 'a7000000-0000-4000-8000-000000000002', 20000, 150), false);
SELECT pg_temp.expect('tin khẩn cấp không nhường cho tin kém khẩn hơn',
  team_reserved_for_more_urgent('b7000000-0000-4000-8000-000000000002', 'a7000000-0000-4000-8000-000000000001', 20000, 150), false);
UPDATE assignment_queue SET seeking_at = now() - interval '10 minutes' WHERE incident_id = 'b7000000-0000-4000-8000-000000000002';
SELECT pg_temp.expect('seeking_at cũ hơn cửa sổ (workflow đã chết) → hết giữ đội',
  team_reserved_for_more_urgent('b7000000-0000-4000-8000-000000000001', 'a7000000-0000-4000-8000-000000000001', 20000, 150), false);

-- ---------- Lịch sử giao nhiệm vụ ----------
INSERT INTO incident_assignments (incident_id, team_id, workflow_run_id, attempt_no, urgency, distance_m, deadline_at)
  VALUES ('b7000000-0000-4000-8000-000000000001', 'a7000000-0000-4000-8000-000000000001', 'run-test', 1, 'thap', 150, now() + interval '5 minutes');
SELECT pg_temp.expect_error('lịch sử: trùng (workflow_run_id, attempt_no)',
  $$INSERT INTO incident_assignments (incident_id, team_id, workflow_run_id, attempt_no, urgency, deadline_at)
    VALUES ('b7000000-0000-4000-8000-000000000001', 'a7000000-0000-4000-8000-000000000002', 'run-test', 1, 'thap', now() + interval '1 minute')$$, '23505');
SELECT pg_temp.expect_error('lịch sử: kết quả ngoài danh sách',
  $$UPDATE incident_assignments SET result = 'bo_tron', responded_at = now() WHERE workflow_run_id = 'run-test'$$, '23514');
SELECT pg_temp.expect_error('lịch sử: đã phản hồi thì phải có responded_at',
  $$UPDATE incident_assignments SET result = 'tu_choi' WHERE workflow_run_id = 'run-test'$$, '23514');
SELECT pg_temp.expect_error('lịch sử: hạn nhận phải sau lúc giao',
  $$INSERT INTO incident_assignments (incident_id, team_id, workflow_run_id, attempt_no, urgency, deadline_at)
    VALUES ('b7000000-0000-4000-8000-000000000001', 'a7000000-0000-4000-8000-000000000001', 'run-test', 2, 'thap', now())$$, '23514');

-- ---------- Quyền cuu_tro_app ----------
SELECT pg_temp.expect(format('cuu_tro_app %s %s.%s', quyen, bang, cot),
                      has_column_privilege('cuu_tro_app', 'cuu_tro.' || bang, cot, quyen), mong_doi)
  FROM (VALUES
    ('assignment_queue', 'seeking_at', 'UPDATE', true),
    ('assignment_queue', 'started_at', 'UPDATE', true),
    ('assignment_queue', 'created_at', 'UPDATE', false),
    ('incident_assignments', 'result', 'UPDATE', true),
    ('incident_assignments', 'team_id', 'INSERT', true),
    ('incident_assignments', 'team_id', 'UPDATE', false),
    ('incident_assignments', 'deadline_at', 'UPDATE', false)
  ) AS t(bang, cot, quyen, mong_doi);
SELECT pg_temp.expect(format('cuu_tro_app %s cuu_tro.%s (toàn bảng)', quyen, bang),
                      has_table_privilege('cuu_tro_app', 'cuu_tro.' || bang, quyen), mong_doi)
  FROM (VALUES
    ('assignment_queue', 'SELECT', true), ('assignment_queue', 'DELETE', false),
    ('incident_assignments', 'SELECT', true), ('incident_assignments', 'DELETE', false)
  ) AS t(bang, quyen, mong_doi);

-- Đường thật của worker: tìm đội (làm mới seeking_at), giao, ghi lịch sử bằng role dịch vụ
-- (giống SQL_DANG_TIM của activities.py: chỉ ghi khi tin còn tiep_nhan)
UPDATE incidents SET status = 'tiep_nhan', assigned_team_id = NULL WHERE id = 'b7000000-0000-4000-8000-000000000003';
SET LOCAL ROLE cuu_tro_app;
INSERT INTO cuu_tro.assignment_queue (incident_id, started_at, seeking_at)
SELECT id, now(), now() FROM cuu_tro.incidents WHERE id = 'b7000000-0000-4000-8000-000000000003' AND status = 'tiep_nhan'
ON CONFLICT (incident_id) DO UPDATE SET seeking_at = EXCLUDED.seeking_at;
UPDATE cuu_tro.incident_assignments SET result = 'tu_choi', responded_at = now(), responded_by = 'cuuho01'
 WHERE workflow_run_id = 'run-test' AND attempt_no = 1 AND result = 'cho_nhan';
SELECT pg_temp.expect('cuu_tro_app: tin cao vừa đánh dấu đang tìm đội → tin thấp nhường đội (gọi được hàm luật)',
  cuu_tro.team_reserved_for_more_urgent('b7000000-0000-4000-8000-000000000001', 'a7000000-0000-4000-8000-000000000001', 20000, 150), true);
RESET ROLE;
SELECT pg_temp.expect('cuu_tro_app: upsert seeking_at cho tin khởi chạy tay (chưa có dòng hàng đợi)',
  (SELECT started_at IS NOT NULL AND seeking_at IS NOT NULL FROM assignment_queue
    WHERE incident_id = 'b7000000-0000-4000-8000-000000000003'), true);
SELECT pg_temp.expect('cuu_tro_app: ghi kết quả từ chối vào lịch sử',
  (SELECT result || ' ' || responded_by FROM incident_assignments WHERE workflow_run_id = 'run-test' AND attempt_no = 1),
  'tu_choi cuuho01');
