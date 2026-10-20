-- SPDX-License-Identifier: Apache-2.0
-- Quyền tối thiểu cho role dịch vụ cuu_tro_app của backend workflow (#29).
-- Role do lõi tạo (core/postgres/sync-roles.sh: <schema>_app, LOGIN, không có quyền gì); migration
-- chạy bằng cuu_tro_owner (chủ các bảng) nên cấp được quyền trên bảng của mình.
-- Worker PhanCongCuuHo cần: đọc tin + vị trí, đọc đội + vị trí, gán đội / đổi trạng thái tin,
-- đổi trạng thái đội. Không INSERT/DELETE, không đọc SĐT/tên người báo, không chạm bảng khác.
-- UPDATE cột → được SELECT ... FOR UPDATE trên bảng đó (PostgreSQL cần quyền UPDATE ít nhất một cột).

GRANT USAGE ON SCHEMA cuu_tro TO cuu_tro_app;

GRANT SELECT (id, status, location, assigned_team_id, urgency, people_count)
  ON incidents TO cuu_tro_app;
GRANT UPDATE (status, assigned_team_id) ON incidents TO cuu_tro_app;

GRANT SELECT (id, name, status, location, member_count) ON rescue_teams TO cuu_tro_app;
GRANT UPDATE (status) ON rescue_teams TO cuu_tro_app;
