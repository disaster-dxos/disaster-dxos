-- SPDX-License-Identifier: Apache-2.0
-- Sổ cái minh bạch cho phiếu nhập/xuất (#28, D-007). Phiếu chỉ lập qua API cuu-tro-api (role dịch vụ
-- cuu_tro_app, vai trò người dùng dieu-phoi), không qua Hasura: API ghi phiếu, băm bản ghi chuẩn hóa,
-- ghi lá lên sổ cái của lõi (core/ledger) rồi điền ledger_* đúng một lần (trigger 0001 chặn sửa lại).
-- Trang công khai "Minh bạch cứu trợ" đọc lại phiếu để băm lại và so với sổ cái.
-- Không cấp created_by cho SELECT: người lập phiếu là dữ liệu định danh, không lên trang công khai.

GRANT SELECT (id, supply_id, direction, quantity, note, shelter_id, created_at,
              ledger_index, ledger_leaf_hash, ledger_logged_at)
  ON supply_movements TO cuu_tro_app;
GRANT INSERT (supply_id, direction, quantity, note, shelter_id, created_by)
  ON supply_movements TO cuu_tro_app;
GRANT UPDATE (ledger_index, ledger_leaf_hash, ledger_logged_at) ON supply_movements TO cuu_tro_app;

-- Tên/đơn vị hàng và tên điểm nhận để hiển thị kèm phiếu trên trang công khai
GRANT SELECT (id, item_name, unit, storage_name) ON supplies TO cuu_tro_app;
GRANT SELECT (id, name) ON shelters TO cuu_tro_app;

-- Trigger cộng/trừ tồn kho chạy với quyền chủ bảng (cuu_tro_owner): cuu_tro_app lập được phiếu mà
-- không cần quyền UPDATE trực tiếp trên supplies (tồn kho chỉ đổi qua phiếu). search_path của hàm đã
-- cố định (SET search_path FROM CURRENT, 0001) nên SECURITY DEFINER an toàn.
ALTER FUNCTION supply_movements_apply() SECURITY DEFINER;

COMMENT ON COLUMN supply_movements.ledger_index IS 'Vị trí lá trong sổ cái minh bạch của lõi (core/ledger, #28)';
COMMENT ON COLUMN supply_movements.ledger_leaf_hash IS 'Leaf hash RFC 6962 = SHA-256(0x00 || lá); lá chứa SHA-256 của bản ghi chuẩn hóa';
