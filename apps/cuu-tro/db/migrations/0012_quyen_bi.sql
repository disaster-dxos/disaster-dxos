-- SPDX-License-Identifier: Apache-2.0
-- Quyền của role CHỈ ĐỌC cuu_tro_bi (#91, #92): dashboard Grafana (datasource PostgreSQL) và bộ xuất
-- Parquet (cuu_tro_workflow/luu_tru.py). postgres-roles tạo role (không quyền gì, phiên mặc định
-- read-only); ở đây chỉ GRANT SELECT các cột KHÔNG định danh.
-- KHÔNG cấp: SĐT/họ tên/mô tả tự do/địa chỉ của tin kêu cứu, người tạo tin, người nhận/từ chối nhiệm vụ,
-- ghi chú giao nhiệm vụ, SĐT/người liên hệ của đội và điểm trú ẩn, người lập phiếu/bút toán, thành viên đội.
-- Tọa độ tin kêu cứu được cấp (bản đồ nhiệt, số liệu theo vùng) nhưng bộ xuất Parquet làm tròn ~1 km.

GRANT USAGE ON SCHEMA cuu_tro TO cuu_tro_bi;

GRANT SELECT (id, location, people_count, urgency, status, source, assigned_team_id, created_at, updated_at)
  ON incidents TO cuu_tro_bi;
GRANT SELECT (id, incident_id, team_id, attempt_no, urgency, distance_m, assigned_at, deadline_at, result,
              responded_at)
  ON incident_assignments TO cuu_tro_bi;
GRANT SELECT (id, name, member_count, status, created_at) ON rescue_teams TO cuu_tro_bi;
GRANT SELECT (id, name, location, capacity, current_occupancy, status) ON shelters TO cuu_tro_bi;
GRANT SELECT (id, item_name, unit, quantity, storage_name, shelter_id, updated_at) ON supplies TO cuu_tro_bi;
GRANT SELECT (id, supply_id, direction, quantity, shelter_id, created_at, ledger_index, ledger_logged_at)
  ON supply_movements TO cuu_tro_bi;
GRANT SELECT (id, direction, amount, currency, category, purpose, shelter_id, supply_movement_id, created_at,
              ledger_index, ledger_logged_at)
  ON relief_fund_entries TO cuu_tro_bi;
GRANT SELECT (id, code, name, kind, unit, location, warning_threshold, danger_threshold, last_value,
              last_observed_at, active)
  ON sensors TO cuu_tro_bi;
GRANT SELECT ON sensor_readings TO cuu_tro_bi;
GRANT SELECT (id, sensor_code, episode_at, step, value, threshold, unit, observed_at, channel, status, created_at,
              sent_at)
  ON sensor_alert_notifications TO cuu_tro_bi;
