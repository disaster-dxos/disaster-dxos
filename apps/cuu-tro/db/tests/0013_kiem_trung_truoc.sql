-- SPDX-License-Identifier: Apache-2.0
-- Kiểm thử hàm kiểm trước tin trùng incident_find_duplicate (#102), chạy trong BEGIN … ROLLBACK như 0001.
-- Hàm phải trả đúng tin mà trigger incidents_no_duplicate sẽ chặn, và không gì khác. SĐT giả 0900102xxx.
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

-- lat 16.4, lon 108.4: 0.0017° vĩ độ ≈ 188 m, 0.0020° ≈ 221 m
INSERT INTO incidents (description, location, people_count, urgency, reporter_phone, source)
VALUES ('[test 0013] mở', ST_SetSRID(ST_MakePoint(108.4, 16.4), 4326)::geography, 2, 'cao', '0900102001', 'app'),
       ('[test 0013] đã cứu', ST_SetSRID(ST_MakePoint(108.5, 16.5), 4326)::geography, 1, 'cao', '0900102002', 'app');
UPDATE incidents SET status = 'da_cuu' WHERE description = '[test 0013] đã cứu';
-- cuu_tro_app không đọc được description: lấy mã tin trước khi đổi role
SELECT id AS id_mo FROM incidents WHERE description = '[test 0013] mở' \gset

SELECT pg_temp.expect('cuu_tro_app được gọi hàm',
  has_function_privilege('cuu_tro_app', 'cuu_tro.incident_find_duplicate(text, double precision, double precision)',
                         'EXECUTE'), true);
SELECT pg_temp.expect('PUBLIC không được gọi hàm (tinh-nguyen/Hasura không dò được SĐT)',
  (SELECT bool_or(a.grantee = 0) FROM pg_proc p, aclexplode(p.proacl) a
    WHERE p.oid = 'cuu_tro.incident_find_duplicate(text, double precision, double precision)'::regprocedure),
  false);

SET ROLE cuu_tro_app;
SELECT pg_temp.expect('cùng SĐT, cách ~188 m, tin còn mở → trả tin đó, khoảng cách và tham số',
  (SELECT d.incident_id = :'id_mo'::uuid AND d.distance_m BETWEEN 180 AND 195 AND d.radius_m = 200
          AND d.window_minutes = 360
     FROM incident_find_duplicate('0900102001', 108.4, 16.4017) d), true);
SELECT pg_temp.expect('cùng SĐT, cách ~221 m → không trùng',
  (SELECT count(*) FROM incident_find_duplicate('0900102001', 108.4, 16.4020)), 0::bigint);
SELECT pg_temp.expect('khác SĐT, cùng chỗ → không trùng',
  (SELECT count(*) FROM incident_find_duplicate('0900102009', 108.4, 16.4)), 0::bigint);
SELECT pg_temp.expect('tin đã cứu (đóng) → không trùng',
  (SELECT count(*) FROM incident_find_duplicate('0900102002', 108.5, 16.5)), 0::bigint);
RESET ROLE;
SET ROLE cuu_tro_owner;

-- Trùng khớp với trigger: chỗ hàm báo trùng thì INSERT bị chặn 23505, chỗ hàm báo không thì INSERT được
SELECT pg_temp.expect('hàm và trigger cùng kết luận (trùng → INSERT bị chặn)',
  (SELECT CASE WHEN EXISTS (SELECT 1 FROM incident_find_duplicate('0900102001', 108.4, 16.4017)) THEN 'trung' END),
  'trung');
DO $$
BEGIN
  INSERT INTO incidents (description, location, people_count, urgency, reporter_phone, source)
  VALUES ('[test 0013] thử', ST_SetSRID(ST_MakePoint(108.4, 16.4017), 4326)::geography, 1, 'cao', '0900102001', 'app');
  RAISE EXCEPTION 'FAIL  trigger không chặn tin mà hàm báo trùng';
EXCEPTION WHEN unique_violation THEN
  NULL;
END $$;
SELECT 'PASS  trigger chặn đúng tin mà hàm báo trùng → 23505';
