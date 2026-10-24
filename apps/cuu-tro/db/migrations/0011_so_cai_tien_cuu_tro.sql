-- SPDX-License-Identifier: Apache-2.0
-- Tiền cứu trợ thu/chi trên sổ cái minh bạch (#89, D-007), cùng mô hình phiếu nhập/xuất hàng (#28, 0006).
-- Bút toán chỉ lập qua API cuu-tro-api (role cuu_tro_app, vai trò dieu-phoi): API ghi bút toán, băm bản ghi
-- chuẩn hóa, ghi lá lên core/ledger rồi điền ledger_* đúng một lần. Dòng có ledger_index NULL là outbox
-- (cùng transaction với bút toán): bộ niêm phong trong worker (so_cai_niem_phong.py) ghi bù khi API chưa
-- ghi được (sổ cái tạm dừng, API chết giữa chừng).
-- KHÔNG có dữ liệu cá nhân: không tên/SĐT/số tài khoản của người ủng hộ hay người nhận; chi cho hộ dân
-- chỉ ghi hạng mục + điểm nhận. Nội dung (purpose) hiện công khai, API chặn dãy số dạng SĐT/CCCD.

CREATE TABLE relief_fund_entries (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  direction          text NOT NULL CHECK (direction IN ('thu', 'chi')),
  -- Đồng Việt Nam, số nguyên
  amount             numeric(16, 0) NOT NULL CHECK (amount > 0),
  currency           text NOT NULL DEFAULT 'VND' CHECK (currency = 'VND'),
  category           text NOT NULL CHECK (category IN ('ung_ho', 'ngan_sach', 'mua_hang', 'ho_tro_ho_dan',
                                                       'van_chuyen', 'khac')),
  purpose            text CHECK (length(purpose) <= 200),
  -- Nơi nhận khoản chi (điểm trú ẩn), phiếu nhập hàng mua bằng khoản chi
  shelter_id         uuid REFERENCES shelters (id) ON DELETE RESTRICT,
  supply_movement_id uuid REFERENCES supply_movements (id) ON DELETE RESTRICT,
  created_by         text,
  created_at         timestamptz NOT NULL DEFAULT now(),
  ledger_index       bigint UNIQUE CHECK (ledger_index >= 0),
  ledger_leaf_hash   bytea CHECK (octet_length(ledger_leaf_hash) = 32),
  ledger_logged_at   timestamptz,
  CHECK ((ledger_index IS NULL) = (ledger_leaf_hash IS NULL)
         AND (ledger_index IS NULL) = (ledger_logged_at IS NULL)),
  CONSTRAINT relief_fund_entries_category_direction CHECK (
    (direction = 'thu' AND category IN ('ung_ho', 'ngan_sach', 'khac'))
    OR (direction = 'chi' AND category IN ('mua_hang', 'ho_tro_ho_dan', 'van_chuyen', 'khac')))
);
CREATE INDEX relief_fund_entries_created_idx ON relief_fund_entries (created_at);
CREATE INDEX relief_fund_entries_unlogged_idx ON relief_fund_entries (created_at) WHERE ledger_index IS NULL;

-- Chi không vượt số dư quỹ. Khóa advisory theo transaction: hai khoản chi đồng thời không cùng lọt.
-- Chạy với quyền chủ bảng (như trigger tồn kho của 0006) để luật không phụ thuộc quyền SELECT của người gọi.
CREATE FUNCTION relief_fund_entries_balance() RETURNS trigger
LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
DECLARE so_du numeric;
BEGIN
  IF NEW.direction = 'chi' THEN
    PERFORM pg_advisory_xact_lock(hashtext('cuu_tro.relief_fund_entries'));
    SELECT coalesce(sum(CASE direction WHEN 'thu' THEN amount ELSE -amount END), 0) INTO so_du
      FROM relief_fund_entries;
    IF so_du < NEW.amount THEN
      RAISE EXCEPTION 'Khoản chi % đồng vượt số dư quỹ % đồng', NEW.amount, so_du
        USING ERRCODE = 'check_violation', CONSTRAINT = 'relief_fund_entries_balance';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER relief_fund_entries_balance BEFORE INSERT ON relief_fund_entries
  FOR EACH ROW EXECUTE FUNCTION relief_fund_entries_balance();
ALTER FUNCTION relief_fund_entries_balance() SECURITY DEFINER;

-- Bút toán đã lập không sửa/xóa được (chỉ điền ledger_* một lần); sai thì lập bút toán điều chỉnh
CREATE FUNCTION relief_fund_entries_immutable() RETURNS trigger
LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'Bút toán % không xóa được, lập bút toán điều chỉnh', OLD.id USING ERRCODE = 'restrict_violation';
  END IF;
  IF (NEW.direction, NEW.amount, NEW.currency, NEW.category, NEW.purpose, NEW.shelter_id, NEW.supply_movement_id,
      NEW.created_by, NEW.created_at)
     IS DISTINCT FROM
     (OLD.direction, OLD.amount, OLD.currency, OLD.category, OLD.purpose, OLD.shelter_id, OLD.supply_movement_id,
      OLD.created_by, OLD.created_at)
     OR (OLD.ledger_index IS NOT NULL AND
         (NEW.ledger_index, NEW.ledger_leaf_hash, NEW.ledger_logged_at)
         IS DISTINCT FROM (OLD.ledger_index, OLD.ledger_leaf_hash, OLD.ledger_logged_at)) THEN
    RAISE EXCEPTION 'Bút toán % không sửa được, lập bút toán điều chỉnh', OLD.id USING ERRCODE = 'restrict_violation';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER relief_fund_entries_immutable BEFORE UPDATE OR DELETE ON relief_fund_entries
  FOR EACH ROW EXECUTE FUNCTION relief_fund_entries_immutable();

COMMENT ON TABLE relief_fund_entries IS 'Bút toán thu/chi tiền cứu trợ, ghi sổ cái Tessera (#89), không chứa dữ liệu cá nhân';
COMMENT ON COLUMN relief_fund_entries.amount IS 'Số tiền (đồng), số nguyên dương';
COMMENT ON COLUMN relief_fund_entries.category IS 'thu: ung_ho | ngan_sach | khac; chi: mua_hang | ho_tro_ho_dan | van_chuyen | khac';
COMMENT ON COLUMN relief_fund_entries.ledger_index IS 'Vị trí lá trong sổ cái minh bạch của lõi (core/ledger); NULL = chờ niêm phong';

-- Quyền tối thiểu cho API và bộ niêm phong (cuu_tro_app). Không SELECT created_by (người lập không công khai).
GRANT SELECT (id, direction, amount, currency, category, purpose, shelter_id, supply_movement_id, created_at,
              ledger_index, ledger_leaf_hash, ledger_logged_at)
  ON relief_fund_entries TO cuu_tro_app;
GRANT INSERT (direction, amount, category, purpose, shelter_id, supply_movement_id, created_by)
  ON relief_fund_entries TO cuu_tro_app;
GRANT UPDATE (ledger_index, ledger_leaf_hash, ledger_logged_at) ON relief_fund_entries TO cuu_tro_app;
