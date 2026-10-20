-- SPDX-License-Identifier: Apache-2.0
-- Kiểm thử quyền tối thiểu của role dịch vụ cuu_tro_app (#29), chạy trong BEGIN … ROLLBACK như 0001.
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

-- Cột worker cần: đọc vị trí/trạng thái, ghi trạng thái + đội được gán. Không đọc SĐT/tên người báo.
SELECT pg_temp.expect(format('cuu_tro_app %s %s.%s', quyen, bang, cot),
                      has_column_privilege('cuu_tro_app', 'cuu_tro.' || bang, cot, quyen), mong_doi)
  FROM (VALUES
    ('incidents', 'location', 'SELECT', true),
    ('incidents', 'status', 'UPDATE', true),
    ('incidents', 'assigned_team_id', 'UPDATE', true),
    ('incidents', 'reporter_phone', 'SELECT', false),
    ('incidents', 'reporter_name', 'SELECT', false),
    ('incidents', 'description', 'UPDATE', false),
    ('rescue_teams', 'location', 'SELECT', true),
    ('rescue_teams', 'status', 'UPDATE', true),
    ('rescue_teams', 'contact_phone', 'SELECT', false),
    ('rescue_teams', 'location', 'UPDATE', false)
  ) AS t(bang, cot, quyen, mong_doi);

-- Không thêm/xóa tin hay đội, không chạm bảng khác của ứng dụng
SELECT pg_temp.expect(format('cuu_tro_app %s cuu_tro.%s', quyen, bang),
                      has_table_privilege('cuu_tro_app', 'cuu_tro.' || bang, quyen), false)
  FROM (VALUES
    ('incidents', 'INSERT'), ('incidents', 'DELETE'), ('rescue_teams', 'INSERT'),
    ('team_members', 'SELECT'), ('supplies', 'UPDATE'), ('supply_movements', 'SELECT')
  ) AS t(bang, quyen);

SELECT pg_temp.expect('cuu_tro_app: LOGIN, không superuser/CREATEDB/CREATEROLE, có giới hạn kết nối',
  (SELECT rolcanlogin AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole AND rolconnlimit > 0
     FROM pg_roles WHERE rolname = 'cuu_tro_app'), true);
