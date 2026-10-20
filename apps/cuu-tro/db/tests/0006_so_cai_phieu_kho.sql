-- SPDX-License-Identifier: Apache-2.0
-- Kiểm thử quyền của cuu_tro_app trên phiếu nhập/xuất cho sổ cái (#28), chạy trong BEGIN … ROLLBACK như 0001.
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

CREATE FUNCTION pg_temp.expect_ok(label text, stmt text) RETURNS text
LANGUAGE plpgsql AS $$
BEGIN
  EXECUTE stmt;
  RETURN format('PASS  %s', label);
EXCEPTION WHEN OTHERS THEN
  RAISE EXCEPTION 'FAIL  %: %', label, SQLERRM;
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

-- Quyền theo cột: đọc phiếu nhưng không đọc người lập; chỉ sửa được cột ledger_*
SELECT pg_temp.expect(format('cuu_tro_app %s supply_movements.%s', quyen, cot),
                      has_column_privilege('cuu_tro_app', 'cuu_tro.supply_movements', cot, quyen), mong_doi)
  FROM (VALUES
    ('id', 'SELECT', true), ('quantity', 'SELECT', true), ('ledger_leaf_hash', 'SELECT', true),
    ('created_by', 'SELECT', false), ('created_by', 'INSERT', true), ('quantity', 'INSERT', true),
    ('ledger_index', 'INSERT', false), ('ledger_index', 'UPDATE', true), ('quantity', 'UPDATE', false)
  ) AS t(cot, quyen, mong_doi);
SELECT pg_temp.expect(format('cuu_tro_app %s cuu_tro.%s (toàn bảng)', quyen, bang),
                      has_table_privilege('cuu_tro_app', 'cuu_tro.' || bang, quyen), false)
  FROM (VALUES ('supply_movements', 'DELETE'), ('supplies', 'UPDATE'), ('supplies', 'INSERT')) AS t(bang, quyen);
SELECT pg_temp.expect('supply_movements_apply chạy với quyền chủ bảng (SECURITY DEFINER)',
  (SELECT prosecdef FROM pg_proc WHERE oid = 'cuu_tro.supply_movements_apply()'::regprocedure), true);

-- Đóng vai cuu-tro-api: lập phiếu, tồn kho đổi qua trigger, điền ledger_* một lần
INSERT INTO supplies (id, item_name, unit, storage_name)
VALUES ('30000000-0000-4000-8000-0000000006a1', 'Hàng thử sổ cái', 'thùng', 'Kho thử sổ cái');
SET LOCAL ROLE cuu_tro_app;
-- Không đặt được id (không có quyền cột id): lọc theo mặt hàng thử, chỉ có đúng phiếu này
INSERT INTO cuu_tro.supply_movements (supply_id, direction, quantity, note, created_by)
VALUES ('30000000-0000-4000-8000-0000000006a1', 'nhap', 12, 'thử', 'dieuphoi01');
SELECT pg_temp.expect_ok('cuu_tro_app: điền ledger_* lần đầu được',
  $q$UPDATE cuu_tro.supply_movements SET ledger_index = 9000000000000000002, ledger_leaf_hash = sha256('la'::bytea), ledger_logged_at = now()
     WHERE supply_id = '30000000-0000-4000-8000-0000000006a1'$q$);
SELECT pg_temp.expect_error('cuu_tro_app: đổi ledger_* đã ghi bị chặn (trigger)',
  $q$UPDATE cuu_tro.supply_movements SET ledger_index = 9000000000000000003 WHERE supply_id = '30000000-0000-4000-8000-0000000006a1'$q$, '23001');
SELECT pg_temp.expect_error('cuu_tro_app: sửa số lượng bị chặn (không có quyền cột)',
  $q$UPDATE cuu_tro.supply_movements SET quantity = 1 WHERE supply_id = '30000000-0000-4000-8000-0000000006a1'$q$, '42501');
SELECT pg_temp.expect_error('cuu_tro_app: xuất quá tồn bị chặn',
  $q$INSERT INTO cuu_tro.supply_movements (supply_id, direction, quantity) VALUES ('30000000-0000-4000-8000-0000000006a1', 'xuat', 13)$q$, '23514');
RESET ROLE;
SELECT pg_temp.expect('tồn kho cộng qua trigger khi cuu_tro_app lập phiếu',
  (SELECT quantity = 12 FROM supplies WHERE id = '30000000-0000-4000-8000-0000000006a1'), true);
