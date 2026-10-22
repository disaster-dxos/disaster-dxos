-- SPDX-License-Identifier: Apache-2.0
-- Kiểm thử bảng team_members (#26), chạy trong BEGIN … ROLLBACK như 0001.
-- Hàm pg_temp.expect_* tạo ở 0001 không còn (mỗi file một transaction riêng), nên tạo lại gọn.
\set QUIET on
\pset tuples_only on

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

INSERT INTO rescue_teams (id, name, member_count, contact_phone)
VALUES ('10000000-0000-4000-8000-000000000002', 'Đội thử thành viên', 2, '0980000020');
INSERT INTO team_members (user_id, team_id) VALUES ('kc-sub-thu', '10000000-0000-4000-8000-000000000002');

SELECT pg_temp.expect_error('team_members: một người không thuộc hai đội',
  $q$INSERT INTO team_members (user_id, team_id) VALUES ('kc-sub-thu', '10000000-0000-4000-8000-000000000002')$q$, '23505');
SELECT pg_temp.expect_error('team_members: đội không tồn tại bị chặn',
  $q$INSERT INTO team_members (user_id, team_id) VALUES ('kc-sub-khac', gen_random_uuid())$q$, '23503');
DELETE FROM rescue_teams WHERE id = '10000000-0000-4000-8000-000000000002';
DO $$ BEGIN
  IF EXISTS (SELECT FROM team_members WHERE user_id = 'kc-sub-thu') THEN
    RAISE EXCEPTION 'FAIL  team_members: xóa đội phải xóa liên kết thành viên';
  END IF;
END $$;
SELECT 'PASS  team_members: xóa đội thì xóa liên kết thành viên (ON DELETE CASCADE)';
