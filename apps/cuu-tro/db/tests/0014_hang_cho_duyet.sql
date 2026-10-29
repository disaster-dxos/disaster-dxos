-- SPDX-License-Identifier: Apache-2.0
-- Kiểm thử hàng chờ duyệt tin do AI bóc tách (#104), chạy trong BEGIN … ROLLBACK như 0001.
-- Đúng câu lệnh của API (cuu_tro_workflow/hang_cho.py SoHangCho) bằng role dịch vụ cuu_tro_app: thêm mục,
-- duyệt (khóa dòng → tạo tin → đánh dấu), hủy; quyền theo cột (không đọc dữ liệu người dân), ràng buộc trạng
-- thái, vết không sửa được. Hai phiên duyệt cùng lúc: scripts/smoke-hang-cho.sh. SĐT giả 0900104xxx.
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

-- Chạy stmt, trả "SQLSTATE|constraint" (rỗng nếu chạy được). EXECUTE giữ role hiện tại của phiên.
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

-- Câu INSERT của API khi đưa vào hàng chờ
CREATE FUNCTION pg_temp.them(van_ban text, nguoi text) RETURNS text
LANGUAGE sql AS $$
  SELECT format($f$INSERT INTO cuu_tro.ai_intake_reviews
                     (raw_text, text_source, ai_result, ai_provider, ai_model, ai_fallback, ai_duration_ms, ai_urgency,
                      ai_valid, submitted_by, submitted_by_name, submitted_role)
                   VALUES (%L, 'zalo', '{"de_xuat": {"urgency": "cao"}, "tin_keu_cuu": {"reporter_phone": "0900104001"}}',
                           'gia-lap', NULL, false, 3, 'cao', true, %L, 'tinhnguyen01', 'tinh-nguyen')
                   RETURNING id, status, created_at$f$, van_ban, nguoi)
$$;
GRANT EXECUTE ON FUNCTION pg_temp.loi(text), pg_temp.them(text, text) TO cuu_tro_app;

-- ---------- Quyền theo cột của cuu_tro_app ----------
SELECT pg_temp.expect(format('cuu_tro_app %s ai_intake_reviews.%s', quyen, cot),
                      has_column_privilege('cuu_tro_app', 'cuu_tro.ai_intake_reviews', cot, quyen), mong_doi)
  FROM (VALUES
    ('raw_text', 'INSERT', true), ('ai_result', 'INSERT', true), ('submitted_by', 'INSERT', true),
    ('status', 'INSERT', false), ('reviewed_by', 'INSERT', false), ('incident_id', 'INSERT', false),
    ('id', 'SELECT', true), ('status', 'SELECT', true), ('submitted_by', 'SELECT', true),
    ('reviewed_by_name', 'SELECT', true), ('incident_id', 'SELECT', true),
    -- Không đọc lại dữ liệu người dân (SĐT, tên nằm trong văn bản, đề xuất, nội dung tin)
    ('raw_text', 'SELECT', false), ('ai_result', 'SELECT', false), ('final_body', 'SELECT', false),
    ('edited_fields', 'SELECT', false),
    ('status', 'UPDATE', true), ('final_body', 'UPDATE', true), ('cancel_reason', 'UPDATE', true),
    -- Đề xuất của AI và người gửi không sửa được bằng quyền (trigger chặn cả role chủ bảng)
    ('ai_result', 'UPDATE', false), ('raw_text', 'UPDATE', false), ('submitted_by', 'UPDATE', false)
  ) AS t(cot, quyen, mong_doi);
SELECT pg_temp.expect('cuu_tro_app không DELETE hàng chờ (vết duyệt)',
  has_table_privilege('cuu_tro_app', 'cuu_tro.ai_intake_reviews', 'DELETE'), false);
SELECT pg_temp.expect('cuu_tro_bi (dashboard) không đọc hàng chờ',
  has_table_privilege('cuu_tro_bi', 'cuu_tro.ai_intake_reviews', 'SELECT'), false);

-- ---------- Thêm, duyệt, hủy bằng cuu_tro_app ----------
RESET ROLE;
SET ROLE cuu_tro_app;
SELECT pg_temp.expect('cuu_tro_app thêm mục vào hàng chờ', pg_temp.loi(pg_temp.them('[test 0014] a', 'sub-tn')), '');
SELECT pg_temp.expect('văn bản rỗng → CHECK', split_part(pg_temp.loi(pg_temp.them('   ', 'sub-tn')), '|', 1), '23514');
SELECT pg_temp.expect('văn bản > 2000 ký tự → CHECK',
  split_part(pg_temp.loi(pg_temp.them(repeat('a', 2001), 'sub-tn')), '|', 1), '23514');
SELECT pg_temp.expect('cuu_tro_app không đọc được văn bản gốc',
  pg_temp.loi('SELECT raw_text FROM cuu_tro.ai_intake_reviews'), '42501|');
RESET ROLE;
SET ROLE cuu_tro_owner;
INSERT INTO ai_intake_reviews (raw_text, text_source, ai_result, ai_provider, ai_model, ai_fallback, ai_duration_ms,
                               ai_urgency, ai_valid, submitted_by, submitted_role)
VALUES ('[test 0014] b', 'sms', '{"de_xuat": {}, "tin_keu_cuu": {}}', 'ollama', 'qwen2.5:7b', true, 9000,
        'khan_cap', false, 'sub-dp', 'dieu-phoi'),
       ('[test 0014] c', 'sms', '{"de_xuat": {}, "tin_keu_cuu": {}}', 'gia-lap', NULL, false, 1,
        'thap', true, 'sub-dp', 'dieu-phoi');
SELECT id AS id_a FROM ai_intake_reviews WHERE raw_text = '[test 0014] a' \gset
SELECT id AS id_b FROM ai_intake_reviews WHERE raw_text = '[test 0014] b' \gset
SELECT id AS id_c FROM ai_intake_reviews WHERE raw_text = '[test 0014] c' \gset
SELECT pg_temp.expect('mục mới ở trạng thái cho_duyet, chưa có người duyệt',
  (SELECT status || ':' || coalesce(reviewed_by, '-') FROM ai_intake_reviews WHERE id = :'id_a'), 'cho_duyet:-');
SELECT pg_temp.expect('ai_result phải có de_xuat và tin_keu_cuu',
  split_part(pg_temp.loi(format($q$INSERT INTO ai_intake_reviews (raw_text, text_source, ai_result, ai_provider,
    ai_fallback, ai_duration_ms, ai_urgency, ai_valid, submitted_by, submitted_role)
    VALUES ('x', 'sms', '{"de_xuat": {}}', 'gia-lap', false, 1, 'cao', true, 's', 'dieu-phoi')$q$)), '|', 1), '23514');
SELECT pg_temp.expect('nhà cung cấp tat không vào hàng chờ (tính năng tắt)',
  split_part(pg_temp.loi(format($q$INSERT INTO ai_intake_reviews (raw_text, text_source, ai_result, ai_provider,
    ai_fallback, ai_duration_ms, ai_urgency, ai_valid, submitted_by, submitted_role)
    VALUES ('x', 'sms', '{"de_xuat": {}, "tin_keu_cuu": {}}', 'tat', false, 1, 'cao', true, 's', 'dieu-phoi')$q$)),
    '|', 1), '23514');

-- Duyệt như API: khóa dòng → tạo tin (created_by = người gửi) → đánh dấu trong cùng transaction
RESET ROLE;
SET ROLE cuu_tro_app;
SELECT pg_temp.expect('cuu_tro_app khóa được dòng (SELECT … FOR UPDATE)',
  (SELECT status || ':' || submitted_by FROM cuu_tro.ai_intake_reviews WHERE id = :'id_a' FOR UPDATE), 'cho_duyet:sub-tn');
INSERT INTO cuu_tro.incidents (description, location, address_text, people_count, urgency, reporter_phone,
                               reporter_name, source, created_by)
VALUES ('[test 0014] tin từ hàng chờ', ST_SetSRID(ST_MakePoint(108.42, 16.42), 4326)::geography, NULL, 3, 'cao',
        '0900104001', NULL, 'mang_xa_hoi', 'sub-tn')
RETURNING id AS id_tin \gset
SELECT pg_temp.expect('duyệt thiếu mã tin → CHECK ai_intake_reviews_decision',
  pg_temp.loi(format($q$UPDATE cuu_tro.ai_intake_reviews SET status = 'da_duyet', reviewed_by = 'sub-dp',
    reviewed_at = now(), final_body = '{}', edited_fields = '{}' WHERE id = %L$q$, :'id_a')),
  '23514|ai_intake_reviews_decision');
SELECT pg_temp.expect('duyệt đủ cột (câu UPDATE của API)',
  pg_temp.loi(format($q$UPDATE cuu_tro.ai_intake_reviews
     SET status = 'da_duyet', final_body = '{"people_count": 3}', edited_fields = '{"people_count": {"ai": 1, "nguoi": 3}}',
         reviewed_by = 'sub-dp', reviewed_by_name = 'dieuphoi01', reviewed_at = now(), incident_id = %L
   WHERE id = %L RETURNING reviewed_at$q$, :'id_tin', :'id_a')), '');
SELECT pg_temp.expect('đọc lại trạng thái + người duyệt + mã tin (cột không định danh)',
  (SELECT status || ':' || reviewed_by_name || ':' || (incident_id = :'id_tin')
     FROM cuu_tro.ai_intake_reviews WHERE id = :'id_a'), 'da_duyet:dieuphoi01:true');
SELECT pg_temp.expect('mục đã duyệt không đổi được nữa',
  split_part(pg_temp.loi(format($q$UPDATE cuu_tro.ai_intake_reviews SET status = 'da_huy', cancel_reason = 'x',
    final_body = NULL, edited_fields = NULL, incident_id = NULL WHERE id = %L$q$, :'id_a')), '|', 1), '23001');
SELECT pg_temp.expect('một tin không gắn với hai mục hàng chờ',
  pg_temp.loi(format($q$UPDATE cuu_tro.ai_intake_reviews SET status = 'da_duyet', final_body = '{}',
    edited_fields = '{}', reviewed_by = 'sub-dp', reviewed_at = now(), incident_id = %L WHERE id = %L$q$,
    :'id_tin', :'id_c')), '23505|ai_intake_reviews_incident_id_key');
SELECT pg_temp.expect('hủy (câu UPDATE của API)',
  pg_temp.loi(format($q$UPDATE cuu_tro.ai_intake_reviews SET status = 'da_huy', cancel_reason = 'Tin rác',
    reviewed_by = 'sub-dp', reviewed_by_name = 'dieuphoi01', reviewed_at = now() WHERE id = %L$q$, :'id_c')), '');
SELECT pg_temp.expect('hủy mà gắn mã tin → CHECK',
  pg_temp.loi(format($q$UPDATE cuu_tro.ai_intake_reviews SET status = 'da_huy', reviewed_by = 'sub-dp',
    reviewed_at = now(), incident_id = %L WHERE id = %L$q$, :'id_tin', :'id_b')), '23514|ai_intake_reviews_decision');
SELECT pg_temp.expect('cuu_tro_app không xóa được mục',
  pg_temp.loi(format('DELETE FROM cuu_tro.ai_intake_reviews WHERE id = %L', :'id_b')), '42501|');

-- ---------- Vết không sửa được, kể cả role chủ bảng ----------
RESET ROLE;
SET ROLE cuu_tro_owner;
SELECT pg_temp.expect('sửa đề xuất của AI khi còn chờ duyệt',
  split_part(pg_temp.loi(format($q$UPDATE ai_intake_reviews SET ai_result = '{"de_xuat": {}, "tin_keu_cuu": {"lat": 1}}'
    WHERE id = %L$q$, :'id_b')), '|', 1), '23001');
SELECT pg_temp.expect('sửa văn bản gốc / người gửi',
  split_part(pg_temp.loi(format($q$UPDATE ai_intake_reviews SET raw_text = 'khác', submitted_by = 'x' WHERE id = %L$q$,
    :'id_b')), '|', 1), '23001');
SELECT pg_temp.expect('mục đã hủy không sửa lý do được',
  split_part(pg_temp.loi(format($q$UPDATE ai_intake_reviews SET cancel_reason = 'khác' WHERE id = %L$q$, :'id_c')),
    '|', 1), '23001');
SELECT pg_temp.expect('tin kêu cứu có vết duyệt không xóa được',
  split_part(pg_temp.loi(format('DELETE FROM incidents WHERE id = %L', :'id_tin')), '|', 1), '23503');
SELECT pg_temp.expect('tin tạo từ hàng chờ vẫn vào outbox phân công tự động (#67)',
  (SELECT count(*) FROM assignment_queue WHERE incident_id = :'id_tin'), 1::bigint);
SELECT pg_temp.expect('Hasura (role hasura) đọc được bảng để phục vụ quyền theo vai',
  has_table_privilege('hasura', 'cuu_tro.ai_intake_reviews', 'SELECT'), true);
