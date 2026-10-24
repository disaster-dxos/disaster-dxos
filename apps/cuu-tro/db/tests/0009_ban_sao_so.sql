-- SPDX-License-Identifier: Apache-2.0
-- Kiểm thử quyền đọc của consumer bản sao số (#85, migration 0009), BEGIN … ROLLBACK.
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

INSERT INTO sensors (code, name, kind, unit, location, warning_threshold, danger_threshold, ngsi_ld_id)
VALUES ('THU-NGSI-01', 'Trạm thử 0009', 'muc_nuoc', 'cm', ST_MakePoint(108.115, 15.886)::geography, 900, 1000,
        'urn:ngsi-ld:WaterLevelStation:THU-NGSI-01');

SELECT pg_temp.expect(format('cuu_tro_app %s sensors.%s', quyen, cot),
                      has_column_privilege('cuu_tro_app', 'cuu_tro.sensors', cot, quyen)::text, mong_doi::text)
  FROM (VALUES
    ('location', 'SELECT', true), ('ngsi_ld_id', 'SELECT', true),
    ('location', 'UPDATE', false), ('ngsi_ld_id', 'UPDATE', false)
  ) AS t(cot, quyen, mong_doi);

-- Đúng câu truy vấn của consumer (cuu_tro_workflow/ban_sao_so.py SQL_TRAM), chạy bằng role cuu_tro_app
SET LOCAL ROLE cuu_tro_app;
SELECT pg_temp.expect('cuu_tro_app đọc được trạm để dựng thực thể NGSI-LD',
  (SELECT format('%s %s %s %s %s', code, kind, round(ST_X(location::geometry)::numeric, 3),
                 round(ST_Y(location::geometry)::numeric, 3), ngsi_ld_id)
     FROM cuu_tro.sensors WHERE code = 'THU-NGSI-01'),
  'THU-NGSI-01 muc_nuoc 108.115 15.886 urn:ngsi-ld:WaterLevelStation:THU-NGSI-01');
RESET ROLE;
