-- SPDX-License-Identifier: Apache-2.0
-- Kiểm thử role chỉ đọc cuu_tro_bi (#91, #92, migration 0012): chỉ đọc cột không định danh, không ghi được,
-- phiên mặc định read-only; BEGIN … ROLLBACK.
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

SELECT pg_temp.expect('cuu_tro_bi: không superuser, không tạo CSDL/role',
  (SELECT rolsuper::text || rolcreatedb::text || rolcreaterole::text FROM pg_roles WHERE rolname = 'cuu_tro_bi'),
  'falsefalsefalse');
SELECT pg_temp.expect('cuu_tro_bi: phiên mặc định read-only',
  (SELECT bool_or(c = 'default_transaction_read_only=on')::text FROM pg_db_role_setting s
     JOIN pg_roles r ON r.oid = s.setrole, unnest(s.setconfig) c WHERE r.rolname = 'cuu_tro_bi'), 'true');

SELECT pg_temp.expect(format('cuu_tro_bi SELECT %s.%s', bang, cot),
                      has_column_privilege('cuu_tro_bi', 'cuu_tro.' || bang, cot, 'SELECT')::text, mong_doi::text)
  FROM (VALUES
    ('incidents', 'status', true), ('incidents', 'location', true), ('incidents', 'created_at', true),
    ('incidents', 'reporter_phone', false), ('incidents', 'reporter_name', false), ('incidents', 'description', false),
    ('incidents', 'address_text', false), ('incidents', 'created_by', false),
    ('incident_assignments', 'responded_at', true), ('incident_assignments', 'responded_by', false),
    ('incident_assignments', 'note', false),
    ('rescue_teams', 'name', true), ('rescue_teams', 'contact_phone', false), ('rescue_teams', 'contact_name', false),
    ('shelters', 'name', true), ('shelters', 'contact_phone', false), ('shelters', 'address_text', false),
    ('supply_movements', 'quantity', true), ('supply_movements', 'created_by', false), ('supply_movements', 'note', false),
    ('relief_fund_entries', 'amount', true), ('relief_fund_entries', 'created_by', false),
    ('sensor_readings', 'value', true), ('sensors', 'last_value', true)
  ) AS t(bang, cot, mong_doi);
SELECT pg_temp.expect(format('cuu_tro_bi không %s cuu_tro.%s', quyen, bang),
                      has_table_privilege('cuu_tro_bi', 'cuu_tro.' || bang, quyen)::text, 'false')
  FROM (VALUES ('incidents', 'INSERT'), ('incidents', 'UPDATE'), ('incidents', 'DELETE'),
               ('supplies', 'UPDATE'), ('relief_fund_entries', 'INSERT'), ('team_members', 'SELECT'),
               ('assignment_queue', 'SELECT')) AS t(bang, quyen);

-- Chạy bằng chính role: đọc được số liệu tổng hợp, đọc SĐT hay ghi đều bị từ chối
SET LOCAL ROLE cuu_tro_bi;
SELECT pg_temp.expect('cuu_tro_bi đếm tin kêu cứu theo trạng thái',
  (SELECT (count(*) >= 0)::text FROM cuu_tro.incidents), 'true');
SELECT pg_temp.expect_error('cuu_tro_bi đọc SĐT người báo bị từ chối',
  $q$SELECT reporter_phone FROM cuu_tro.incidents LIMIT 1$q$, '42501');
SELECT pg_temp.expect_error('cuu_tro_bi ghi bị từ chối',
  $q$UPDATE cuu_tro.supplies SET quantity = 0$q$, '42501');
RESET ROLE;
