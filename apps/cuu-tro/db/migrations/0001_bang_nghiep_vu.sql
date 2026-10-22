-- SPDX-License-Identifier: Apache-2.0
-- Schema nghiệp vụ cứu trợ (#25): 5 bảng incidents, rescue_teams, shelters, supplies, sensors
-- và bảng phiếu nhập/xuất supply_movements (chừa chỗ cho sổ cái Tessera ở #28).
-- Chạy bởi core/postgres/migrate.sh: SET ROLE cuu_tro_owner, search_path = cuu_tro, public,
-- cả file trong một transaction. Tọa độ: geography(Point,4326), khoảng cách tính bằng mét.
-- Giá trị trạng thái viết không dấu, gạch dưới để dễ dùng làm enum GraphQL (#26).
-- Hàm dùng "SET search_path FROM CURRENT" (= cuu_tro, public lúc migrate) để chạy đúng khi được
-- gọi từ phiên có search_path khác (Hasura kết nối với search_path mặc định).

-- ---------- Hàm dùng chung ----------
CREATE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END $$;

-- Số điện thoại Việt Nam dạng nội địa 10 số (0 + 9 số). Dữ liệu mẫu dùng dạng 09xxxxxxx0.
CREATE DOMAIN phone_vn AS text
  CHECK (VALUE ~ '^0[0-9]{9}$');

-- ---------- Đội cứu hộ ----------
CREATE TABLE rescue_teams (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name                text NOT NULL UNIQUE CHECK (btrim(name) <> ''),
  member_count        integer NOT NULL CHECK (member_count BETWEEN 1 AND 500),
  -- Vị trí hiện tại (app hiện trường cập nhật); NULL khi chưa có tín hiệu
  location            geography(Point, 4326),
  location_updated_at timestamptz,
  status              text NOT NULL DEFAULT 'san_sang'
                      CHECK (status IN ('san_sang', 'dang_lam_nhiem_vu', 'nghi')),
  contact_name        text,
  contact_phone       phone_vn NOT NULL,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  CHECK (location IS NULL OR location_updated_at IS NOT NULL)
);
CREATE INDEX rescue_teams_location_gix ON rescue_teams USING gist (location);
CREATE INDEX rescue_teams_status_idx ON rescue_teams (status);
CREATE TRIGGER rescue_teams_updated_at BEFORE UPDATE ON rescue_teams
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------- Tin kêu cứu ----------
CREATE TABLE incidents (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  description      text NOT NULL CHECK (btrim(description) <> ''),
  -- Poka-yoke: không có tọa độ thì không tạo được tin kêu cứu
  location         geography(Point, 4326) NOT NULL,
  address_text     text,
  people_count     integer NOT NULL DEFAULT 1 CHECK (people_count BETWEEN 1 AND 10000),
  urgency          text NOT NULL DEFAULT 'trung_binh'
                   CHECK (urgency IN ('khan_cap', 'cao', 'trung_binh', 'thap')),
  -- tiep_nhan → phan_cong → dang_cuu → da_cuu → dong (luồng Temporal ở #29)
  status           text NOT NULL DEFAULT 'tiep_nhan'
                   CHECK (status IN ('tiep_nhan', 'phan_cong', 'dang_cuu', 'da_cuu', 'dong')),
  reporter_phone   phone_vn NOT NULL,
  reporter_name    text,
  source           text NOT NULL DEFAULT 'dien_thoai'
                   CHECK (source IN ('dien_thoai', 'web', 'app', 'telegram', 'mang_xa_hoi', 'khac')),
  assigned_team_id uuid REFERENCES rescue_teams (id) ON DELETE RESTRICT,
  -- sub của người dùng Keycloak tạo tin (NULL khi đến từ kênh công khai)
  created_by       text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  -- Đã phân công / đang cứu thì phải biết đội nào
  CONSTRAINT incidents_team_required
    CHECK (status NOT IN ('phan_cong', 'dang_cuu') OR assigned_team_id IS NOT NULL)
);
CREATE INDEX incidents_location_gix ON incidents USING gist (location);
CREATE INDEX incidents_status_idx ON incidents (status, urgency);
CREATE INDEX incidents_phone_created_idx ON incidents (reporter_phone, created_at);
CREATE INDEX incidents_team_idx ON incidents (assigned_team_id);
CREATE TRIGGER incidents_updated_at BEFORE UPDATE ON incidents
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Poka-yoke chính: chặn tin kêu cứu trùng. Cùng SĐT, cách tin còn mở (chưa da_cuu/dong) không quá
-- 200 m, tạo trong vòng 6 giờ → coi là trùng, báo lỗi unique_violation kèm id tin cũ để giao diện
-- gợi ý cập nhật tin cũ (thêm số người, mô tả) thay vì tạo mới. Exclusion constraint không dùng
-- được (điều kiện "trong 6 giờ" và "tin còn mở" phụ thuộc thời điểm), nên dùng trigger + khóa
-- advisory theo SĐT để hai yêu cầu đồng thời không cùng lọt qua.
CREATE TABLE incident_dedup_config (
  id             boolean PRIMARY KEY DEFAULT true CHECK (id),
  radius_m       double precision NOT NULL DEFAULT 200 CHECK (radius_m > 0),
  window_minutes integer NOT NULL DEFAULT 360 CHECK (window_minutes > 0)
);
INSERT INTO incident_dedup_config DEFAULT VALUES;

CREATE FUNCTION incidents_block_duplicate() RETURNS trigger
LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
DECLARE
  cfg incident_dedup_config%ROWTYPE;
  dup record;
BEGIN
  SELECT * INTO cfg FROM incident_dedup_config;
  PERFORM pg_advisory_xact_lock(hashtextextended('cuu_tro.incidents:' || NEW.reporter_phone, 0));
  SELECT i.id, i.created_at, round(ST_Distance(i.location, NEW.location)) AS dist
    INTO dup
    FROM incidents i
   WHERE i.reporter_phone = NEW.reporter_phone
     AND i.id <> NEW.id
     AND i.status NOT IN ('da_cuu', 'dong')
     AND i.created_at > now() - make_interval(mins => cfg.window_minutes)
     AND ST_DWithin(i.location, NEW.location, cfg.radius_m)
   ORDER BY i.created_at DESC
   LIMIT 1;
  IF FOUND THEN
    RAISE EXCEPTION 'Tin kêu cứu trùng: cùng số điện thoại đã báo sự cố % cách % m lúc %',
        dup.id, dup.dist, to_char(dup.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh', 'HH24:MI DD/MM/YYYY')
      USING ERRCODE = 'unique_violation',
            CONSTRAINT = 'incidents_no_duplicate',
            DETAIL = format('incident_id=%s distance_m=%s radius_m=%s window_minutes=%s',
                            dup.id, dup.dist, cfg.radius_m, cfg.window_minutes),
            HINT = 'Cập nhật tin kêu cứu đã có (số người, mô tả) thay vì tạo tin mới.';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER incidents_no_duplicate
  BEFORE INSERT OR UPDATE OF reporter_phone, location ON incidents
  FOR EACH ROW EXECUTE FUNCTION incidents_block_duplicate();

-- ---------- Điểm trú ẩn ----------
CREATE TABLE shelters (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name              text NOT NULL UNIQUE CHECK (btrim(name) <> ''),
  location          geography(Point, 4326) NOT NULL,
  address_text      text,
  capacity          integer NOT NULL CHECK (capacity > 0),
  current_occupancy integer NOT NULL DEFAULT 0 CHECK (current_occupancy >= 0),
  status            text NOT NULL DEFAULT 'mo' CHECK (status IN ('mo', 'tam_dong')),
  contact_phone     phone_vn,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT shelters_not_over_capacity CHECK (current_occupancy <= capacity)
);
CREATE INDEX shelters_location_gix ON shelters USING gist (location);
CREATE TRIGGER shelters_updated_at BEFORE UPDATE ON shelters
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------- Hàng cứu trợ (tồn kho theo mặt hàng × điểm lưu) ----------
CREATE TABLE supplies (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  item_name    text NOT NULL CHECK (btrim(item_name) <> ''),
  unit         text NOT NULL CHECK (btrim(unit) <> ''),
  quantity     numeric(14, 2) NOT NULL DEFAULT 0 CHECK (quantity >= 0),
  -- Kho hoặc điểm lưu: tên kho; nếu hàng để tại điểm trú ẩn thì gắn shelter_id
  storage_name text NOT NULL CHECK (btrim(storage_name) <> ''),
  shelter_id   uuid REFERENCES shelters (id) ON DELETE RESTRICT,
  location     geography(Point, 4326),
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT supplies_item_storage_key UNIQUE (item_name, unit, storage_name)
);
CREATE INDEX supplies_location_gix ON supplies USING gist (location);
CREATE TRIGGER supplies_updated_at BEFORE UPDATE ON supplies
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Phiếu nhập/xuất: mỗi phiếu cập nhật tồn kho trong cùng transaction (xuất quá tồn bị CHECK
-- quantity >= 0 chặn). #28 ghi mỗi phiếu thành một leaf của sổ cái Tessera rồi điền ledger_*.
-- D-007: phiếu và leaf KHÔNG chứa dữ liệu cá nhân (không tên, SĐT người nhận/người cho).
CREATE TABLE supply_movements (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  supply_id        uuid NOT NULL REFERENCES supplies (id) ON DELETE RESTRICT,
  direction        text NOT NULL CHECK (direction IN ('nhap', 'xuat')),
  quantity         numeric(14, 2) NOT NULL CHECK (quantity > 0),
  -- Lý do/chứng từ, không ghi dữ liệu cá nhân
  note             text,
  -- Nơi nhận hàng xuất (nếu là điểm trú ẩn)
  shelter_id       uuid REFERENCES shelters (id) ON DELETE RESTRICT,
  created_by       text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  -- Vị trí leaf trong sổ cái Tessera và hash leaf (SHA-256), điền sau khi ghi sổ (#28)
  ledger_index     bigint UNIQUE CHECK (ledger_index >= 0),
  ledger_leaf_hash bytea CHECK (octet_length(ledger_leaf_hash) = 32),
  ledger_logged_at timestamptz,
  CHECK ((ledger_index IS NULL) = (ledger_leaf_hash IS NULL)
         AND (ledger_index IS NULL) = (ledger_logged_at IS NULL))
);
CREATE INDEX supply_movements_supply_idx ON supply_movements (supply_id, created_at);
CREATE INDEX supply_movements_unlogged_idx ON supply_movements (created_at) WHERE ledger_index IS NULL;

CREATE FUNCTION supply_movements_apply() RETURNS trigger
LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
BEGIN
  UPDATE supplies
     SET quantity = quantity + CASE NEW.direction WHEN 'nhap' THEN NEW.quantity ELSE -NEW.quantity END
   WHERE id = NEW.supply_id;
  RETURN NEW;
END $$;
CREATE TRIGGER supply_movements_apply AFTER INSERT ON supply_movements
  FOR EACH ROW EXECUTE FUNCTION supply_movements_apply();

-- Phiếu đã lập không sửa được nội dung (chỉ được điền ledger_* một lần), không xóa được
CREATE FUNCTION supply_movements_immutable() RETURNS trigger
LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'Phiếu nhập/xuất % không xóa được, lập phiếu điều chỉnh', OLD.id
      USING ERRCODE = 'restrict_violation';
  END IF;
  IF (NEW.supply_id, NEW.direction, NEW.quantity, NEW.note, NEW.shelter_id, NEW.created_by, NEW.created_at)
     IS DISTINCT FROM
     (OLD.supply_id, OLD.direction, OLD.quantity, OLD.note, OLD.shelter_id, OLD.created_by, OLD.created_at)
     OR (OLD.ledger_index IS NOT NULL AND
         (NEW.ledger_index, NEW.ledger_leaf_hash, NEW.ledger_logged_at)
         IS DISTINCT FROM (OLD.ledger_index, OLD.ledger_leaf_hash, OLD.ledger_logged_at)) THEN
    RAISE EXCEPTION 'Phiếu nhập/xuất % không sửa được, lập phiếu điều chỉnh', OLD.id
      USING ERRCODE = 'restrict_violation';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER supply_movements_immutable BEFORE UPDATE OR DELETE ON supply_movements
  FOR EACH ROW EXECUTE FUNCTION supply_movements_immutable();

-- ---------- Trạm cảm biến (chuỗi đo theo thời gian ở #30) ----------
CREATE TABLE sensors (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code              text NOT NULL UNIQUE CHECK (code ~ '^[A-Z0-9][A-Z0-9_-]{1,31}$'),
  name              text NOT NULL CHECK (btrim(name) <> ''),
  kind              text NOT NULL CHECK (kind IN ('muc_nuoc', 'luong_mua', 'gio')),
  unit              text NOT NULL CHECK (unit IN ('cm', 'mm', 'm/s')),
  location          geography(Point, 4326) NOT NULL,
  warning_threshold numeric(10, 2),
  danger_threshold  numeric(10, 2),
  last_value        numeric(10, 2),
  last_observed_at  timestamptz,
  -- id thực thể NGSI-LD tương ứng trên Scorpio (bản sao số trạm đo, #30)
  ngsi_ld_id        text UNIQUE CHECK (ngsi_ld_id LIKE 'urn:ngsi-ld:%'),
  active            boolean NOT NULL DEFAULT true,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT sensors_threshold_order
    CHECK (warning_threshold IS NULL OR danger_threshold IS NULL OR danger_threshold >= warning_threshold),
  CHECK ((last_value IS NULL) = (last_observed_at IS NULL))
);
CREATE INDEX sensors_location_gix ON sensors USING gist (location);
CREATE TRIGGER sensors_updated_at BEFORE UPDATE ON sensors
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------- Chú thích (Hasura dùng làm mô tả trong schema GraphQL) ----------
COMMENT ON TABLE incidents IS 'Tin kêu cứu: bắt buộc tọa độ, chặn trùng theo SĐT + 200 m + 6 giờ';
COMMENT ON TABLE rescue_teams IS 'Đội cứu hộ và vị trí hiện tại';
COMMENT ON TABLE shelters IS 'Điểm trú ẩn, sức chứa';
COMMENT ON TABLE supplies IS 'Hàng cứu trợ tồn theo mặt hàng và điểm lưu';
COMMENT ON TABLE supply_movements IS 'Phiếu nhập/xuất hàng, ghi sổ cái Tessera (#28), không chứa dữ liệu cá nhân';
COMMENT ON TABLE sensors IS 'Trạm cảm biến (mực nước, lượng mưa, gió) và lần đo cuối';
COMMENT ON TABLE incident_dedup_config IS 'Tham số chặn tin trùng (một dòng): bán kính và khoảng thời gian';
