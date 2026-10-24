-- SPDX-License-Identifier: Apache-2.0
-- Kiểm thử bút toán tiền cứu trợ (#89, migration 0011): số dư, bất biến, hạng mục theo chiều, quyền của
-- cuu_tro_app, câu truy vấn outbox của bộ niêm phong; BEGIN … ROLLBACK.
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

-- Bắt đầu từ quỹ trống trong transaction này (seed có thể đã nạp bút toán: dời số dư về 0 bằng một khoản chi)
DO $$
DECLARE so_du numeric;
BEGIN
  SELECT coalesce(sum(CASE direction WHEN 'thu' THEN amount ELSE -amount END), 0) INTO so_du FROM relief_fund_entries;
  IF so_du > 0 THEN
    INSERT INTO relief_fund_entries (direction, amount, category, purpose) VALUES ('chi', so_du, 'khac', 'test 0011');
  END IF;
END $$;

SELECT pg_temp.expect_error('chi khi quỹ trống bị chặn (vượt số dư)',
  $q$INSERT INTO relief_fund_entries (direction, amount, category) VALUES ('chi', 1, 'mua_hang')$q$, '23514');
INSERT INTO relief_fund_entries (id, direction, amount, category, purpose)
VALUES ('10000000-0000-4000-8000-0000000000c1', 'thu', 1000000, 'ung_ho', 'test 0011');
INSERT INTO relief_fund_entries (direction, amount, category) VALUES ('chi', 600000, 'mua_hang');
SELECT pg_temp.expect_error('chi vượt số dư còn lại (400.000) bị chặn',
  $q$INSERT INTO relief_fund_entries (direction, amount, category) VALUES ('chi', 400001, 'van_chuyen')$q$, '23514');
INSERT INTO relief_fund_entries (direction, amount, category) VALUES ('chi', 400000, 'van_chuyen');
SELECT pg_temp.expect('chi đúng bằng số dư còn lại được nhận, số dư về 0',
  (SELECT sum(CASE direction WHEN 'thu' THEN amount ELSE -amount END)::text FROM relief_fund_entries), '0');
SELECT pg_temp.expect_error('thu với hạng mục chi bị chặn',
  $q$INSERT INTO relief_fund_entries (direction, amount, category) VALUES ('thu', 1, 'mua_hang')$q$, '23514');
SELECT pg_temp.expect_error('số tiền âm bị chặn',
  $q$INSERT INTO relief_fund_entries (direction, amount, category) VALUES ('thu', -5, 'ung_ho')$q$, '23514');
SELECT pg_temp.expect_error('đơn vị khác VND bị chặn',
  $q$INSERT INTO relief_fund_entries (direction, amount, currency, category) VALUES ('thu', 5, 'USD', 'ung_ho')$q$, '23514');
SELECT pg_temp.expect_error('bút toán không sửa được số tiền',
  $q$UPDATE relief_fund_entries SET amount = 2 WHERE id = '10000000-0000-4000-8000-0000000000c1'$q$, '23001');
SELECT pg_temp.expect_error('bút toán không xóa được',
  $q$DELETE FROM relief_fund_entries WHERE id = '10000000-0000-4000-8000-0000000000c1'$q$, '23001');
UPDATE relief_fund_entries SET ledger_index = 999999001, ledger_leaf_hash = decode(repeat('ab', 32), 'hex'),
       ledger_logged_at = now() WHERE id = '10000000-0000-4000-8000-0000000000c1';
SELECT pg_temp.expect_error('đã niêm phong thì không đổi ledger_index',
  $q$UPDATE relief_fund_entries SET ledger_index = 999999002 WHERE id = '10000000-0000-4000-8000-0000000000c1'$q$, '23001');
SELECT pg_temp.expect_error('ledger_* phải điền đủ cùng lúc',
  $q$INSERT INTO relief_fund_entries (direction, amount, category, ledger_index) VALUES ('thu', 1, 'ung_ho', 999999003)$q$, '23514');

SELECT pg_temp.expect(format('cuu_tro_app %s relief_fund_entries.%s', quyen, cot),
                      has_column_privilege('cuu_tro_app', 'cuu_tro.relief_fund_entries', cot, quyen)::text, mong_doi::text)
  FROM (VALUES
    ('amount', 'SELECT', true), ('ledger_index', 'UPDATE', true), ('amount', 'INSERT', true),
    ('created_by', 'SELECT', false), ('amount', 'UPDATE', false), ('purpose', 'UPDATE', false),
    ('currency', 'INSERT', false)
  ) AS t(cot, quyen, mong_doi);
SELECT pg_temp.expect('cuu_tro_app không DELETE bút toán',
  has_table_privilege('cuu_tro_app', 'cuu_tro.relief_fund_entries', 'DELETE')::text, 'false');

-- Đúng câu truy vấn outbox của bộ niêm phong (so_cai_niem_phong.py), chạy bằng cuu_tro_app: dòng chưa niêm phong
INSERT INTO relief_fund_entries (id, direction, amount, category, created_at)
VALUES ('10000000-0000-4000-8000-0000000000c2', 'thu', 7, 'khac', now() - interval '1 minute');
SET LOCAL ROLE cuu_tro_app;
SELECT pg_temp.expect('bộ niêm phong thấy bút toán chưa niêm phong cũ hơn 5 giây',
  (SELECT string_agg(id::text, ',') FROM (
     SELECT id FROM cuu_tro.relief_fund_entries
      WHERE ledger_index IS NULL AND created_at < now() - make_interval(secs => 5) AND amount = 7
      ORDER BY created_at LIMIT 20 FOR UPDATE SKIP LOCKED) x), '10000000-0000-4000-8000-0000000000c2');
RESET ROLE;
