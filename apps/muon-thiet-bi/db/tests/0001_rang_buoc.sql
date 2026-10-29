-- SPDX-License-Identifier: Apache-2.0
-- Kiểm thử ràng buộc của module mẫu (#110), chạy bằng `make test-db` (migrate.sh test: BEGIN … ROLLBACK, quyền
-- role chủ schema). Không phụ thuộc dữ liệu seed.
\set QUIET on
\pset tuples_only on

CREATE FUNCTION pg_temp.loi(stmt text) RETURNS text
LANGUAGE plpgsql AS $$
DECLARE st text; cn text;
BEGIN
  EXECUTE stmt;
  RETURN '';
EXCEPTION WHEN OTHERS THEN
  GET STACKED DIAGNOSTICS st = RETURNED_SQLSTATE, cn = CONSTRAINT_NAME;
  RETURN st || '|' || coalesce(cn, '');
END $$;

CREATE FUNCTION pg_temp.expect(label text, got text, want text) RETURNS text
LANGUAGE plpgsql AS $$
BEGIN
  IF got IS DISTINCT FROM want THEN
    RAISE EXCEPTION 'FAIL  %: % (mong đợi %)', label, got, want;
  END IF;
  RETURN format('PASS  %s → %s', label, got);
END $$;

INSERT INTO devices (id, code, name, kind, condition) VALUES
  ('d1000000-0000-4000-8000-000000000001', 'T-TOT', '[test] tốt', 'dung_cu', 'tot'),
  ('d1000000-0000-4000-8000-000000000002', 'T-HONG', '[test] hỏng', 'dung_cu', 'hong');

SELECT pg_temp.expect('mượn thiết bị tốt', pg_temp.loi($q$INSERT INTO loans (id, device_id, borrower_sub, due_at)
  VALUES ('a1000000-0000-4000-8000-000000000001', 'd1000000-0000-4000-8000-000000000001', 'u1', now() + interval '2 days')$q$), '');
SELECT pg_temp.expect('mượn thiết bị đang có người mượn → 23505',
  pg_temp.loi($q$INSERT INTO loans (device_id, borrower_sub, due_at)
    VALUES ('d1000000-0000-4000-8000-000000000001', 'u2', now() + interval '1 day')$q$), '23505|loans_one_open_per_device');
SELECT pg_temp.expect('mượn thiết bị hỏng → 23514',
  pg_temp.loi($q$INSERT INTO loans (device_id, borrower_sub, due_at)
    VALUES ('d1000000-0000-4000-8000-000000000002', 'u2', now() + interval '1 day')$q$), '23514|loans_device_usable');
SELECT pg_temp.expect('hạn trả trước lúc mượn → 23514',
  pg_temp.loi($q$INSERT INTO loans (device_id, borrower_sub, borrowed_at, due_at)
    VALUES ('d1000000-0000-4000-8000-000000000001', 'u2', now(), now() - interval '1 hour')$q$), '23514|loans_due_after_borrow');
SELECT pg_temp.expect('hạn trả quá 30 ngày → 23514',
  split_part(pg_temp.loi($q$UPDATE devices SET condition = 'tot' WHERE code = 'T-HONG';
    INSERT INTO loans (device_id, borrower_sub, due_at)
    VALUES ('d1000000-0000-4000-8000-000000000002', 'u2', now() + interval '31 days')$q$), '|', 2), 'loans_max_30_days');
SELECT pg_temp.expect('không đổi người mượn → 23001',
  split_part(pg_temp.loi($q$UPDATE loans SET borrower_sub = 'u9' WHERE id = 'a1000000-0000-4000-8000-000000000001'$q$), '|', 1), '23001');
SELECT pg_temp.expect('trả thiết bị', pg_temp.loi($q$UPDATE loans SET returned_at = now()
  WHERE id = 'a1000000-0000-4000-8000-000000000001'$q$), '');
SELECT pg_temp.expect('trả xong thì mượn lại được', pg_temp.loi($q$INSERT INTO loans (device_id, borrower_sub, due_at)
  VALUES ('d1000000-0000-4000-8000-000000000001', 'u2', now() + interval '1 day')$q$), '');
SELECT pg_temp.expect('lượt đã trả không mở lại → 23001',
  split_part(pg_temp.loi($q$UPDATE loans SET returned_at = NULL WHERE id = 'a1000000-0000-4000-8000-000000000001'$q$), '|', 1), '23001');
SELECT pg_temp.expect('mã thiết bị sai dạng → 23514',
  split_part(pg_temp.loi($q$INSERT INTO devices (code, name, kind) VALUES ('ma thuong', 'x', 'khac')$q$), '|', 1), '23514');
SELECT pg_temp.expect('Hasura chỉ có DML, không DDL trên schema',
  has_schema_privilege('hasura', 'muon_thiet_bi', 'CREATE')::text, 'false');
