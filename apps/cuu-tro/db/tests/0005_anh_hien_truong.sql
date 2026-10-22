-- SPDX-License-Identifier: Apache-2.0
-- Kiểm thử bảng incident_media và quyền của cuu_tro_app (#27), chạy trong BEGIN … ROLLBACK như 0001.
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

INSERT INTO incidents (id, description, location, reporter_phone)
VALUES ('20000000-0000-4000-8000-0000000000a1', 'Tin thử ảnh', ST_MakePoint(108.1, 15.85)::geography, '0900000270');
INSERT INTO incident_media (id, incident_id, object_key, content_type, size_bytes, sha256, uploaded_by, uploader_role)
VALUES ('20000000-0000-4000-8000-0000000000b1', '20000000-0000-4000-8000-0000000000a1',
        'su-co/20000000-0000-4000-8000-0000000000a1/20000000-0000-4000-8000-0000000000b1.jpg',
        'image/jpeg', 1024, repeat('a', 64), 'nguoi-thu', 'dieu-phoi');
SELECT pg_temp.expect('incident_media: dòng hợp lệ, scan_status mặc định chua_quet',
  (SELECT scan_status = 'chua_quet' FROM incident_media WHERE id = '20000000-0000-4000-8000-0000000000b1'), true);

SELECT pg_temp.expect_error('incident_media: loại không phải ảnh cho phép bị chặn',
  $q$INSERT INTO incident_media (incident_id, object_key, content_type, size_bytes, sha256, uploaded_by, uploader_role)
     VALUES ('20000000-0000-4000-8000-0000000000a1',
             'su-co/20000000-0000-4000-8000-0000000000a1/20000000-0000-4000-8000-0000000000b2.jpg',
             'image/gif', 10, repeat('a', 64), 'x', 'dieu-phoi')$q$, '23514');
SELECT pg_temp.expect_error('incident_media: object_key ngoài quy ước (tên tệp người dùng) bị chặn',
  $q$INSERT INTO incident_media (incident_id, object_key, content_type, size_bytes, sha256, uploaded_by, uploader_role)
     VALUES ('20000000-0000-4000-8000-0000000000a1', '../khac/anh.jpg', 'image/jpeg', 10, repeat('a', 64), 'x', 'dieu-phoi')$q$, '23514');
SELECT pg_temp.expect_error('incident_media: sha256 sai định dạng bị chặn',
  $q$INSERT INTO incident_media (incident_id, object_key, content_type, size_bytes, sha256, uploaded_by, uploader_role)
     VALUES ('20000000-0000-4000-8000-0000000000a1',
             'su-co/20000000-0000-4000-8000-0000000000a1/20000000-0000-4000-8000-0000000000b3.png',
             'image/png', 10, 'abc', 'x', 'dieu-phoi')$q$, '23514');
SELECT pg_temp.expect_error('incident_media: kích thước 0 bị chặn',
  $q$INSERT INTO incident_media (incident_id, object_key, content_type, size_bytes, sha256, uploaded_by, uploader_role)
     VALUES ('20000000-0000-4000-8000-0000000000a1',
             'su-co/20000000-0000-4000-8000-0000000000a1/20000000-0000-4000-8000-0000000000b4.png',
             'image/png', 0, repeat('a', 64), 'x', 'dieu-phoi')$q$, '23514');
SELECT pg_temp.expect_error('incident_media: tin kêu cứu không tồn tại bị chặn',
  $q$INSERT INTO incident_media (incident_id, object_key, content_type, size_bytes, sha256, uploaded_by, uploader_role)
     VALUES (gen_random_uuid(), 'su-co/20000000-0000-4000-8000-0000000000a9/20000000-0000-4000-8000-0000000000b5.png',
             'image/png', 10, repeat('a', 64), 'x', 'dieu-phoi')$q$, '23503');
SELECT pg_temp.expect_error('incident_media: không xóa được tin còn ảnh (RESTRICT)',
  $q$DELETE FROM incidents WHERE id = '20000000-0000-4000-8000-0000000000a1'$q$, '23503');

-- Quyền của cuu-tro-api (cuu_tro_app): chỉ thêm và đọc, không sửa/xóa
SELECT pg_temp.expect(format('cuu_tro_app %s cuu_tro.incident_media', quyen),
                      has_table_privilege('cuu_tro_app', 'cuu_tro.incident_media', quyen), mong_doi)
  FROM (VALUES ('INSERT', true), ('SELECT', true), ('UPDATE', false), ('DELETE', false)) AS t(quyen, mong_doi);
