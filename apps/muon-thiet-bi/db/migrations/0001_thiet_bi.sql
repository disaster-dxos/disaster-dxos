-- SPDX-License-Identifier: Apache-2.0
-- Module mẫu muon-thiet-bi (#110): kho thiết bị dùng chung của tổ dân phố / trường học (máy phát điện, máy
-- bơm, loa kéo…) và lượt mượn. Chạy bằng cơ chế migration chung của lõi (core/postgres/migrate.sh): schema
-- muon_thiet_bi (từ DXOS_APP), chủ sở hữu muon_thiet_bi_owner, role Hasura chỉ có DML. Không dùng gì riêng
-- của apps/cuu-tro.
--
-- Poka-yoke ở tầng dữ liệu (mọi đường ghi đều qua, kể cả SQL tay):
--   - một thiết bị chỉ có một lượt mượn đang mở (chỉ mục duy nhất có điều kiện, an toàn khi gửi đồng thời);
--   - không cho mượn thiết bị đang hỏng hoặc ngừng dùng (trigger);
--   - hạn trả sau lúc mượn và tối đa 30 ngày; ngày trả không trước ngày mượn;
--   - lượt mượn đã trả không mở lại, không đổi người mượn / thiết bị (trigger).

CREATE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END $$;

CREATE TABLE devices (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code       text NOT NULL UNIQUE CHECK (code ~ '^[A-Z0-9][A-Z0-9-]{1,31}$'),
  name       text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 200),
  kind       text NOT NULL CHECK (kind IN ('may_phat_dien', 'may_bom', 'loa', 'may_chieu', 'dung_cu', 'khac')),
  condition  text NOT NULL DEFAULT 'tot' CHECK (condition IN ('tot', 'can_sua', 'hong', 'ngung_dung')),
  location   text CHECK (length(location) <= 200),
  note       text CHECK (length(note) <= 500),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER devices_updated_at BEFORE UPDATE ON devices FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE loans (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id     uuid NOT NULL REFERENCES devices (id) ON DELETE RESTRICT,
  -- sub Keycloak của người mượn (Hasura gán từ JWT, người dùng không tự đặt được)
  borrower_sub  text NOT NULL CHECK (btrim(borrower_sub) <> ''),
  borrower_name text CHECK (length(borrower_name) <= 100),
  purpose       text CHECK (length(purpose) <= 300),
  borrowed_at   timestamptz NOT NULL DEFAULT now(),
  due_at        timestamptz NOT NULL,
  returned_at   timestamptz,
  return_note   text CHECK (length(return_note) <= 300),
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT loans_due_after_borrow CHECK (due_at > borrowed_at),
  CONSTRAINT loans_max_30_days CHECK (due_at <= borrowed_at + interval '30 days'),
  CONSTRAINT loans_return_after_borrow CHECK (returned_at IS NULL OR returned_at >= borrowed_at)
);
CREATE UNIQUE INDEX loans_one_open_per_device ON loans (device_id) WHERE returned_at IS NULL;
CREATE INDEX loans_borrower_idx ON loans (borrower_sub, borrowed_at DESC);
CREATE TRIGGER loans_updated_at BEFORE UPDATE ON loans FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Không mượn thiết bị hỏng / ngừng dùng; lượt đã trả bất biến; không đổi thiết bị, người mượn, lúc mượn
CREATE FUNCTION loans_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
DECLARE tinh_trang text;
BEGIN
  IF TG_OP = 'INSERT' THEN
    SELECT condition INTO tinh_trang FROM devices WHERE id = NEW.device_id FOR SHARE;
    IF tinh_trang IN ('hong', 'ngung_dung') THEN
      RAISE EXCEPTION 'Thiết bị % đang %, không cho mượn', NEW.device_id, tinh_trang
        USING ERRCODE = 'check_violation', CONSTRAINT = 'loans_device_usable';
    END IF;
    RETURN NEW;
  END IF;
  IF OLD.returned_at IS NOT NULL THEN
    RAISE EXCEPTION 'Lượt mượn % đã trả, không sửa được', OLD.id USING ERRCODE = 'restrict_violation';
  END IF;
  IF (NEW.device_id, NEW.borrower_sub, NEW.borrowed_at) IS DISTINCT FROM (OLD.device_id, OLD.borrower_sub, OLD.borrowed_at) THEN
    RAISE EXCEPTION 'Không đổi thiết bị, người mượn hay lúc mượn của lượt %', OLD.id USING ERRCODE = 'restrict_violation';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER loans_guard BEFORE INSERT OR UPDATE ON loans FOR EACH ROW EXECUTE FUNCTION loans_guard();

COMMENT ON TABLE devices IS 'Thiết bị dùng chung (module mẫu muon-thiet-bi, #110)';
COMMENT ON TABLE loans IS 'Lượt mượn thiết bị; một thiết bị chỉ một lượt đang mở (loans_one_open_per_device)';
