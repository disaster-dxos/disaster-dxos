-- SPDX-License-Identifier: Apache-2.0
-- Kiểm thử ràng buộc schema cuu_tro (#25). migrate.sh test chạy file trong BEGIN … ROLLBACK
-- bằng role cuu_tro_owner, nên không để lại dữ liệu. Ca nào sai thì RAISE → psql thoát mã ≠ 0.
-- Tự tạo dữ liệu riêng (SĐT 098xxxxxx0), không phụ thuộc seed.
\set QUIET on
\pset tuples_only on

CREATE FUNCTION pg_temp.expect_error(label text, stmt text, want_state text) RETURNS text
LANGUAGE plpgsql AS $$
DECLARE got text; msg text;
BEGIN
  BEGIN
    EXECUTE stmt;
  EXCEPTION WHEN OTHERS THEN
    GET STACKED DIAGNOSTICS got = RETURNED_SQLSTATE, msg = MESSAGE_TEXT;
    IF got = want_state THEN
      RETURN format('PASS  %s → %s (%s)', label, got, msg);
    END IF;
    RAISE EXCEPTION 'FAIL  %: SQLSTATE % (mong đợi %): %', label, got, want_state, msg;
  END;
  RAISE EXCEPTION 'FAIL  %: câu lệnh chạy được, mong đợi lỗi %', label, want_state;
END $$;

CREATE FUNCTION pg_temp.expect_ok(label text, stmt text) RETURNS text
LANGUAGE plpgsql AS $$
BEGIN
  EXECUTE stmt;
  RETURN format('PASS  %s', label);
EXCEPTION WHEN OTHERS THEN
  RAISE EXCEPTION 'FAIL  %: %', label, SQLERRM;
END $$;

-- Dữ liệu thử: một đội, một tin gốc
INSERT INTO rescue_teams (id, name, member_count, location, location_updated_at, contact_phone)
VALUES ('10000000-0000-4000-8000-000000000001', 'Đội thử', 3, ST_MakePoint(108.2000, 16.0000)::geography, now(), '0980000010');
INSERT INTO incidents (id, description, location, reporter_phone)
VALUES ('20000000-0000-4000-8000-000000000001', 'Tin gốc', ST_MakePoint(108.2010, 16.0010)::geography, '0981111110');

-- Poka-yoke: tọa độ bắt buộc
SELECT pg_temp.expect_error('incidents: thiếu tọa độ bị chặn',
  $q$INSERT INTO incidents (description, location, reporter_phone) VALUES ('x', NULL, '0981111120')$q$, '23502');
-- Poka-yoke: chặn trùng SĐT trong 200 m (điểm cách tin gốc ~100 m)
SELECT pg_temp.expect_error('incidents: cùng SĐT, cách ~100 m, trong 6 giờ bị chặn',
  $q$INSERT INTO incidents (description, location, reporter_phone)
     VALUES ('Báo lại', ST_Project(ST_MakePoint(108.2010, 16.0010)::geography, 100, radians(45))::geography, '0981111110')$q$,
  '23505');
SELECT pg_temp.expect_ok('incidents: cùng SĐT, cách ~500 m được tạo',
  $q$INSERT INTO incidents (description, location, reporter_phone)
     VALUES ('Chỗ khác', ST_Project(ST_MakePoint(108.2010, 16.0010)::geography, 500, radians(45))::geography, '0981111110')$q$);
SELECT pg_temp.expect_ok('incidents: SĐT khác, cùng chỗ được tạo',
  $q$INSERT INTO incidents (description, location, reporter_phone)
     VALUES ('Hàng xóm báo', ST_MakePoint(108.2010, 16.0010)::geography, '0981111130')$q$);
-- Tin gốc đã đóng thì báo lại cùng chỗ là sự cố mới
UPDATE incidents SET status = 'dong' WHERE id = '20000000-0000-4000-8000-000000000001';
SELECT pg_temp.expect_ok('incidents: tin cũ đã đóng, báo lại cùng chỗ được tạo',
  $q$INSERT INTO incidents (description, location, reporter_phone)
     VALUES ('Lũ lên lại', ST_MakePoint(108.2010, 16.0010)::geography, '0981111110')$q$);
-- Ngoài khoảng thời gian 6 giờ
SELECT pg_temp.expect_ok('incidents: cùng SĐT, cùng chỗ, tin cũ 7 giờ trước được tạo',
  $q$INSERT INTO incidents (description, location, reporter_phone, created_at)
     VALUES ('Tin cũ', ST_MakePoint(108.3000, 16.1000)::geography, '0981111140', now() - interval '7 hours');
     INSERT INTO incidents (description, location, reporter_phone)
     VALUES ('Tin mới', ST_MakePoint(108.3000, 16.1000)::geography, '0981111140')$q$);
-- Sửa vị trí một tin vào sát tin khác cùng SĐT cũng bị chặn
SELECT pg_temp.expect_error('incidents: UPDATE vị trí thành trùng bị chặn',
  $q$UPDATE incidents SET location = ST_MakePoint(108.3000, 16.1000)::geography
      WHERE reporter_phone = '0981111140' AND description = 'Tin cũ'$q$, '23505');

SELECT pg_temp.expect_error('incidents: SĐT sai định dạng bị chặn',
  $q$INSERT INTO incidents (description, location, reporter_phone) VALUES ('x', ST_MakePoint(108, 16)::geography, '12345')$q$, '23514');
SELECT pg_temp.expect_error('incidents: trạng thái lạ bị chặn',
  $q$INSERT INTO incidents (description, location, reporter_phone, status) VALUES ('x', ST_MakePoint(108, 16)::geography, '0981111150', 'xong')$q$, '23514');
SELECT pg_temp.expect_error('incidents: phan_cong mà chưa có đội bị chặn',
  $q$INSERT INTO incidents (description, location, reporter_phone, status) VALUES ('x', ST_MakePoint(108, 16)::geography, '0981111160', 'phan_cong')$q$, '23514');
SELECT pg_temp.expect_error('incidents: số người = 0 bị chặn',
  $q$INSERT INTO incidents (description, location, reporter_phone, people_count) VALUES ('x', ST_MakePoint(108, 16)::geography, '0981111170', 0)$q$, '23514');

-- Truy vấn không gian: đội sẵn sàng gần tin gốc nhất (KNN trên chỉ mục GiST)
SELECT format('PASS  đội sẵn sàng gần nhất: %s (%s m)', t.name, round(ST_Distance(t.location, i.location)))
  FROM incidents i
  CROSS JOIN LATERAL (
    SELECT name, location FROM rescue_teams
     WHERE status = 'san_sang' AND location IS NOT NULL
     ORDER BY location <-> i.location LIMIT 1) t
 WHERE i.id = '20000000-0000-4000-8000-000000000001' AND t.name = 'Đội thử';
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM incidents i CROSS JOIN LATERAL (
      SELECT name FROM rescue_teams WHERE status = 'san_sang' AND location IS NOT NULL
       ORDER BY location <-> i.location LIMIT 1) t
     WHERE i.id = '20000000-0000-4000-8000-000000000001' AND t.name = 'Đội thử') THEN
    RAISE EXCEPTION 'FAIL  truy vấn đội gần nhất không trả về Đội thử';
  END IF;
END $$;

-- Điểm trú ẩn: số người hiện tại ≤ sức chứa
SELECT pg_temp.expect_error('shelters: quá sức chứa bị chặn',
  $q$INSERT INTO shelters (name, location, capacity, current_occupancy) VALUES ('Điểm thử', ST_MakePoint(108, 16)::geography, 10, 11)$q$, '23514');
SELECT pg_temp.expect_error('shelters: sức chứa 0 bị chặn',
  $q$INSERT INTO shelters (name, location, capacity) VALUES ('Điểm thử 2', ST_MakePoint(108, 16)::geography, 0)$q$, '23514');

-- Hàng cứu trợ: tồn ≥ 0, phiếu nhập/xuất cập nhật tồn, xuất quá tồn bị chặn, phiếu không sửa/xóa
INSERT INTO supplies (id, item_name, unit, storage_name) VALUES ('30000000-0000-4000-8000-000000000001', 'Gạo thử', 'kg', 'Kho thử');
INSERT INTO supply_movements (supply_id, direction, quantity) VALUES ('30000000-0000-4000-8000-000000000001', 'nhap', 100);
INSERT INTO supply_movements (supply_id, direction, quantity) VALUES ('30000000-0000-4000-8000-000000000001', 'xuat', 30);
DO $$ BEGIN
  IF (SELECT quantity FROM supplies WHERE id = '30000000-0000-4000-8000-000000000001') <> 70 THEN
    RAISE EXCEPTION 'FAIL  supplies: tồn sau nhập 100 xuất 30 phải là 70';
  END IF;
END $$;
SELECT 'PASS  supplies: nhập 100, xuất 30 → tồn 70';
SELECT pg_temp.expect_error('supplies: xuất quá tồn bị chặn',
  $q$INSERT INTO supply_movements (supply_id, direction, quantity) VALUES ('30000000-0000-4000-8000-000000000001', 'xuat', 71)$q$, '23514');
SELECT pg_temp.expect_error('supplies: tồn âm bị chặn',
  $q$UPDATE supplies SET quantity = -1 WHERE id = '30000000-0000-4000-8000-000000000001'$q$, '23514');
SELECT pg_temp.expect_error('supply_movements: sửa số lượng phiếu bị chặn',
  $q$UPDATE supply_movements SET quantity = 1 WHERE supply_id = '30000000-0000-4000-8000-000000000001' AND direction = 'nhap'$q$, '23001');
SELECT pg_temp.expect_error('supply_movements: xóa phiếu bị chặn',
  $q$DELETE FROM supply_movements WHERE supply_id = '30000000-0000-4000-8000-000000000001'$q$, '23001');
SELECT pg_temp.expect_ok('supply_movements: điền ledger_* lần đầu được',
  $q$UPDATE supply_movements SET ledger_index = 0, ledger_leaf_hash = sha256('leaf'::bytea), ledger_logged_at = now()
      WHERE supply_id = '30000000-0000-4000-8000-000000000001' AND direction = 'nhap'$q$);
SELECT pg_temp.expect_error('supply_movements: đổi ledger_* đã ghi bị chặn',
  $q$UPDATE supply_movements SET ledger_index = 5
      WHERE supply_id = '30000000-0000-4000-8000-000000000001' AND direction = 'nhap'$q$, '23001');

-- Cảm biến: ngưỡng nguy hiểm ≥ ngưỡng cảnh báo, mã trạm đúng dạng
SELECT pg_temp.expect_error('sensors: ngưỡng nguy hiểm < cảnh báo bị chặn',
  $q$INSERT INTO sensors (code, name, kind, unit, location, warning_threshold, danger_threshold)
     VALUES ('T-01', 'Trạm thử', 'muc_nuoc', 'cm', ST_MakePoint(108, 16)::geography, 300, 200)$q$, '23514');
SELECT pg_temp.expect_error('sensors: mã trạm sai dạng bị chặn',
  $q$INSERT INTO sensors (code, name, kind, unit, location) VALUES ('tram 1', 'Trạm thử', 'muc_nuoc', 'cm', ST_MakePoint(108, 16)::geography)$q$, '23514');

-- Trigger chạy đúng từ phiên không có cuu_tro trong search_path (như Hasura)
SET search_path = public;
SELECT pg_temp.expect_error('incidents: chặn trùng khi search_path không có cuu_tro',
  $q$INSERT INTO cuu_tro.incidents (description, location, reporter_phone)
     VALUES ('Báo lại', ST_MakePoint(108.2010, 16.0010)::geography, '0981111130')$q$, '23505');
SELECT pg_temp.expect_ok('supply_movements: cập nhật tồn khi search_path không có cuu_tro',
  $q$INSERT INTO cuu_tro.supply_movements (supply_id, direction, quantity) VALUES ('30000000-0000-4000-8000-000000000001', 'nhap', 1)$q$);
SET search_path = cuu_tro, public;

-- Mỗi bảng có updated_at đều có trigger set_updated_at (now() cố định trong transaction nên
-- không so được giá trị trước/sau ở đây)
DO $$ BEGIN
  IF (SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
       WHERE c.relnamespace = 'cuu_tro'::regnamespace AND t.tgname LIKE '%_updated_at') <> 5 THEN
    RAISE EXCEPTION 'FAIL  thiếu trigger updated_at';
  END IF;
END $$;
SELECT 'PASS  5 bảng có trigger updated_at';
