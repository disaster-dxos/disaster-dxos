-- SPDX-License-Identifier: Apache-2.0
-- Liên kết người dùng Keycloak ↔ đội cứu hộ (#26). Hasura dùng bảng này để lọc theo hàng cho
-- vai trò cuu-ho: thành viên chỉ thấy và cập nhật tin kêu cứu được phân công cho đội mình
-- (incidents.assigned_team → rescue_teams.members.user_id = X-Hasura-User-Id).
-- Vì sao bảng trong DB mà không phải thuộc tính Keycloak (claim x-hasura-team-id): cán bộ điều phối
-- đổi đội cho thành viên ngay trong ứng dụng, có hiệu lực ở truy vấn kế tiếp, không phải chờ token
-- mới và không cần quyền quản trị Keycloak. Mỗi người thuộc tối đa một đội.

CREATE TABLE team_members (
  -- "sub" của người dùng Keycloak (= claim x-hasura-user-id)
  user_id    text PRIMARY KEY CHECK (btrim(user_id) <> ''),
  team_id    uuid NOT NULL REFERENCES rescue_teams (id) ON DELETE CASCADE,
  -- Tên đăng nhập để người đọc dễ nhận ra, không dùng để phân quyền
  username   text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX team_members_team_idx ON team_members (team_id);
CREATE TRIGGER team_members_updated_at BEFORE UPDATE ON team_members
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE team_members IS 'Thành viên đội cứu hộ: người dùng Keycloak (sub) thuộc đội nào, dùng để phân quyền cuu-ho';
