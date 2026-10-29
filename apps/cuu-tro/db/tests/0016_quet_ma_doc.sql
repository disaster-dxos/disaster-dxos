-- SPDX-License-Identifier: Apache-2.0
-- Kiểm thử cột kết quả quét mã độc (#111), chạy trong BEGIN … ROLLBACK như 0001. Đúng câu INSERT của API
-- (cuu_tro_workflow/api.py SoAnh.them) bằng role cuu_tro_app.
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
-- Câu INSERT của API: scanned_at do CSDL đặt khi đã quét
CREATE FUNCTION pg_temp.them(id text, trang_thai text, dong_co text) RETURNS text
LANGUAGE sql AS $$
  SELECT format($f$INSERT INTO cuu_tro.incident_media (id, incident_id, object_key, content_type, size_bytes, sha256,
                     uploaded_by, uploader_role, scan_status, scan_engine, scanned_at)
                   VALUES (%L, '20000000-0000-4000-8000-0000000016a1', 'su-co/20000000-0000-4000-8000-0000000016a1/' || %L || '.jpg', 'image/jpeg', 10,
                           repeat('a', 64), 'sub-0016', 'dieu-phoi', %L, %L,
                           CASE WHEN %L = 'chua_quet' THEN NULL ELSE now() END)$f$, id, id, trang_thai, dong_co, trang_thai)
$$;
GRANT EXECUTE ON FUNCTION pg_temp.loi(text), pg_temp.them(text, text, text) TO cuu_tro_app;

INSERT INTO incidents (id, description, location, reporter_phone)
VALUES ('20000000-0000-4000-8000-0000000016a1', '[test 0016] ảnh', ST_MakePoint(108.1, 15.85)::geography, '0900001601');

RESET ROLE;
SET ROLE cuu_tro_app;
SELECT pg_temp.expect('ảnh đã quét sạch: lưu phiên bản bộ chữ ký, scanned_at do CSDL đặt',
  pg_temp.loi(pg_temp.them('a1600000-0000-4000-8000-000000000001', 'sach', 'ClamAV 1.5.4/28165')), '');
SELECT pg_temp.expect('máy quét không có: chua_quet, không có scanned_at',
  pg_temp.loi(pg_temp.them('a1600000-0000-4000-8000-000000000002', 'chua_quet', NULL)), '');
SELECT pg_temp.expect('đọc lại kết quả quét',
  (SELECT string_agg(scan_status || ':' || (scanned_at IS NOT NULL)::text || ':' || coalesce(scan_engine, '-'), ' ' ORDER BY id)
     FROM cuu_tro.incident_media WHERE uploaded_by = 'sub-0016'), 'sach:true:ClamAV 1.5.4/28165 chua_quet:false:-');
SELECT pg_temp.expect('cuu_tro_app không sửa được kết quả quét → 42501',
  pg_temp.loi($q$UPDATE cuu_tro.incident_media SET scan_status = 'sach' WHERE uploaded_by = 'sub-0016'$q$), '42501|');
RESET ROLE;
SET ROLE cuu_tro_owner;
SELECT pg_temp.expect('đã quét mà thiếu scanned_at → CHECK',
  pg_temp.loi($q$INSERT INTO incident_media (incident_id, object_key, content_type, size_bytes, sha256, uploaded_by,
    uploader_role, scan_status) VALUES ('20000000-0000-4000-8000-0000000016a1', 'su-co/20000000-0000-4000-8000-0000000016a1/a1600000-0000-4000-8000-0000000000b0.jpg', 'image/jpeg', 1,
    repeat('b', 64), 's', 'dieu-phoi', 'sach')$q$), '23514|incident_media_scan_consistent');
SELECT pg_temp.expect('chưa quét mà có scanned_at → CHECK',
  pg_temp.loi($q$INSERT INTO incident_media (incident_id, object_key, content_type, size_bytes, sha256, uploaded_by,
    uploader_role, scan_status, scanned_at) VALUES ('20000000-0000-4000-8000-0000000016a1', 'su-co/20000000-0000-4000-8000-0000000016a1/a1600000-0000-4000-8000-0000000000c0.jpg', 'image/jpeg', 1,
    repeat('c', 64), 's', 'dieu-phoi', 'chua_quet', now())$q$), '23514|incident_media_scan_consistent');
