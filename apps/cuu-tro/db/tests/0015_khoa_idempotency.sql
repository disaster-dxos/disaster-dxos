-- SPDX-License-Identifier: Apache-2.0
-- Kiểm thử bảng khóa idempotency (#106), chạy trong BEGIN … ROLLBACK như 0001. Đúng câu lệnh của
-- cuu_tro_workflow/idempotency.py (SoIdempotency) bằng role dịch vụ cuu_tro_app. Hai yêu cầu đồng thời cùng
-- khóa (hai phiên) không làm được trong một phiên psql: kiểm ở scripts/smoke-mobile.sh.
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
-- Câu giữ khóa của API (SoIdempotency.chay): true nếu giữ được, false nếu khóa đã có
CREATE FUNCTION pg_temp.giu(sub text, k text, sha text) RETURNS boolean
LANGUAGE plpgsql AS $$
DECLARE r boolean;
BEGIN
  INSERT INTO cuu_tro.idempotency_keys (owner_sub, key, endpoint, request_sha256)
  VALUES (sub, k, 'POST /keu-cuu', sha256(convert_to(sha, 'UTF8')))
  ON CONFLICT DO NOTHING RETURNING true INTO r;
  RETURN coalesce(r, false);
END $$;
-- Câu dọn khóa hết hạn của API (SoIdempotency.don): số dòng đã xóa
CREATE FUNCTION pg_temp.don() RETURNS bigint
LANGUAGE plpgsql AS $$
DECLARE n bigint;
BEGIN
  DELETE FROM cuu_tro.idempotency_keys WHERE created_at <= now() - make_interval(hours => 72);
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END $$;
GRANT EXECUTE ON FUNCTION pg_temp.loi(text), pg_temp.giu(text, text, text), pg_temp.don() TO cuu_tro_app;

SELECT pg_temp.expect(format('cuu_tro_app %s idempotency_keys', quyen),
                      has_table_privilege('cuu_tro_app', 'cuu_tro.idempotency_keys', quyen), mong_doi)
  FROM (VALUES ('SELECT', true), ('INSERT', true), ('DELETE', true), ('TRUNCATE', false)) AS t(quyen, mong_doi);
SELECT pg_temp.expect(format('cuu_tro_app UPDATE idempotency_keys.%s', cot),
                      has_column_privilege('cuu_tro_app', 'cuu_tro.idempotency_keys', cot, 'UPDATE'), mong_doi)
  FROM (VALUES ('status_code', true), ('response', true), ('endpoint', false), ('request_sha256', false),
               ('owner_sub', false)) AS t(cot, mong_doi);
SELECT pg_temp.expect('cuu_tro_bi (dashboard) không đọc khóa idempotency',
  has_table_privilege('cuu_tro_bi', 'cuu_tro.idempotency_keys', 'SELECT'), false);

RESET ROLE;
SET ROLE cuu_tro_app;
-- Lần đầu: giữ khóa (status_code NULL) → làm việc → điền phản hồi
SELECT pg_temp.expect('giữ khóa lần đầu (INSERT … ON CONFLICT DO NOTHING RETURNING true)',
  pg_temp.giu('sub-0015', 'k-0015-aaaaaaaa', 'x'), true);
SELECT pg_temp.expect('cùng người, cùng khóa lần hai → không giữ được (phát lại)',
  pg_temp.giu('sub-0015', 'k-0015-aaaaaaaa', 'x'), false);
SELECT pg_temp.expect('người khác cùng khóa → khóa riêng', pg_temp.giu('sub-khac', 'k-0015-aaaaaaaa', 'y'), true);
SELECT pg_temp.expect('điền phản hồi 201',
  pg_temp.loi($q$UPDATE cuu_tro.idempotency_keys SET status_code = 201, response = '{"id": "x"}'
                WHERE owner_sub = 'sub-0015' AND key = 'k-0015-aaaaaaaa'$q$), '');
SELECT pg_temp.expect('đọc lại để phát lại (trong 72 giờ)',
  (SELECT status_code || ':' || (response->>'id') FROM cuu_tro.idempotency_keys
    WHERE owner_sub = 'sub-0015' AND key = 'k-0015-aaaaaaaa' AND status_code IS NOT NULL
      AND created_at > now() - make_interval(hours => 72)), '201:x');
SELECT pg_temp.expect('chỉ lưu phản hồi 2xx → CHECK',
  split_part(pg_temp.loi($q$UPDATE cuu_tro.idempotency_keys SET status_code = 409 WHERE owner_sub = 'sub-khac'$q$),
             '|', 1), '23514');
SELECT pg_temp.expect('mã có phản hồi thì phải có nội dung (và ngược lại) → CHECK',
  split_part(pg_temp.loi($q$UPDATE cuu_tro.idempotency_keys SET status_code = 201 WHERE owner_sub = 'sub-khac'$q$),
             '|', 1), '23514');
SELECT pg_temp.expect('khóa sai dạng (dấu cách, quá ngắn) → CHECK',
  split_part(pg_temp.loi($q$INSERT INTO cuu_tro.idempotency_keys (owner_sub, key, endpoint, request_sha256)
                            VALUES ('s', 'co dau cach', 'POST /keu-cuu', sha256('x'::bytea))$q$), '|', 1), '23514');
SELECT pg_temp.expect('băm yêu cầu phải đúng 32 byte → CHECK',
  split_part(pg_temp.loi($q$INSERT INTO cuu_tro.idempotency_keys (owner_sub, key, endpoint, request_sha256)
                            VALUES ('s', 'k-0015-bbbbbbbb', 'POST /keu-cuu', '\x00'::bytea)$q$), '|', 1), '23514');
SELECT pg_temp.expect('không đổi được endpoint/băm của khóa đã giữ → 42501',
  pg_temp.loi($q$UPDATE cuu_tro.idempotency_keys SET endpoint = 'POST /khac' WHERE owner_sub = 'sub-0015'$q$),
  '42501|');
RESET ROLE;
SET ROLE cuu_tro_owner;
UPDATE idempotency_keys SET created_at = now() - interval '73 hours' WHERE owner_sub = 'sub-khac';
RESET ROLE;
SET ROLE cuu_tro_app;
SELECT pg_temp.expect('dọn khóa hết hạn (câu DELETE của API)', pg_temp.don(), 1::bigint);
SELECT pg_temp.expect('khóa còn hạn vẫn còn', (SELECT count(*) FROM cuu_tro.idempotency_keys
                                               WHERE owner_sub = 'sub-0015'), 1::bigint);
