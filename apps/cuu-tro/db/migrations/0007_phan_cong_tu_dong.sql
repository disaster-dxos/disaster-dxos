-- SPDX-License-Identifier: Apache-2.0
-- Phân công tự động (#67): mỗi tin kêu cứu mới tự khởi chạy workflow PhanCongCuuHo, tin khẩn hơn
-- được ưu tiên giành đội, đội không nhận trong hạn thì phân công lại và có lịch sử.
--
-- Nguồn sự kiện là outbox trong chính PostgreSQL: trigger AFTER INSERT trên incidents ghi một dòng
-- vào assignment_queue CÙNG transaction với tin (không mất tin khi Temporal/NATS đang lỗi, mọi đường
-- tạo tin đều đi qua: Hasura, API #66, SQL) rồi pg_notify để bộ khởi chạy trong worker
-- (cuu_tro_workflow/khoi_chay.py) dậy ngay; worker vẫn quét định kỳ phòng lỡ NOTIFY.
-- Seed dữ liệu mẫu đặt "SET LOCAL cuu_tro.tu_phan_cong = off" để tin mẫu giữ nguyên trạng thái.

-- ---------- Thứ tự ưu tiên của urgency (1 = khẩn nhất) ----------
-- Dùng chung cho thứ tự khởi chạy, priority_key của Temporal và luật nhường đội bên dưới.
CREATE FUNCTION urgency_rank(u text) RETURNS integer
LANGUAGE sql IMMUTABLE PARALLEL SAFE RETURN
  CASE u WHEN 'khan_cap' THEN 1 WHEN 'cao' THEN 2 WHEN 'trung_binh' THEN 3 WHEN 'thap' THEN 4 END;

-- ---------- Hàng đợi phân công (outbox) ----------
CREATE TABLE assignment_queue (
  incident_id uuid PRIMARY KEY REFERENCES incidents (id) ON DELETE CASCADE,
  created_at  timestamptz NOT NULL DEFAULT now(),
  -- Đã khởi chạy workflow phan-cong-<incident_id> (NULL = chưa, bộ khởi chạy sẽ làm)
  started_at  timestamptz,
  attempts    integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  last_error  text,
  -- Workflow đang tìm đội mà chưa gán được: làm mới mỗi vòng tìm, xóa khi đã gán / dừng.
  -- Luật nhường đội chỉ tính tin có seeking_at còn mới (workflow chết thì tự hết hiệu lực).
  seeking_at  timestamptz
);
CREATE INDEX assignment_queue_pending_idx ON assignment_queue (created_at) WHERE started_at IS NULL;
CREATE INDEX assignment_queue_seeking_idx ON assignment_queue (seeking_at) WHERE seeking_at IS NOT NULL;

CREATE FUNCTION incidents_enqueue_assignment() RETURNS trigger
LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
BEGIN
  IF NEW.status <> 'tiep_nhan' OR current_setting('cuu_tro.tu_phan_cong', true) = 'off' THEN
    RETURN NULL;
  END IF;
  INSERT INTO assignment_queue (incident_id) VALUES (NEW.id) ON CONFLICT DO NOTHING;
  -- Chỉ gửi khi transaction commit; payload = id tin (không có dữ liệu cá nhân)
  PERFORM pg_notify('cuu_tro_tin_moi', NEW.id::text);
  RETURN NULL;
END $$;
-- Chạy với quyền chủ bảng: role của Hasura/API tạo tin không cần quyền gì trên hàng đợi
ALTER FUNCTION incidents_enqueue_assignment() SECURITY DEFINER;
CREATE TRIGGER incidents_enqueue_assignment AFTER INSERT ON incidents
  FOR EACH ROW EXECUTE FUNCTION incidents_enqueue_assignment();

-- ---------- Luật ưu tiên: nhường đội cho tin khẩn hơn đang chờ ----------
-- true khi có tin KHÁC khẩn hơn hẳn (urgency_rank nhỏ hơn), còn tiep_nhan, đang được workflow tìm
-- đội (seeking_at trong p_window_s giây gần nhất) và đội p_team nằm trong bán kính của tin đó.
-- Khi đó workflow của p_incident không gán đội này (activity gan_doi trả "nhuong").
CREATE FUNCTION team_reserved_for_more_urgent(p_incident uuid, p_team uuid, p_radius_m double precision,
                                              p_window_s integer) RETURNS boolean
LANGUAGE sql STABLE SET search_path FROM CURRENT AS $$
  SELECT EXISTS (
    SELECT 1
      FROM incidents me
      JOIN rescue_teams t ON t.id = p_team AND t.location IS NOT NULL
      JOIN assignment_queue q ON q.incident_id <> me.id
                             AND q.seeking_at > now() - make_interval(secs => p_window_s)
      JOIN incidents o ON o.id = q.incident_id AND o.status = 'tiep_nhan'
     WHERE me.id = p_incident
       AND urgency_rank(o.urgency) < urgency_rank(me.urgency)
       AND ST_DWithin(o.location, t.location, p_radius_m))
$$;

-- ---------- Lịch sử giao nhiệm vụ ----------
-- Mỗi lần workflow gán một đội là một dòng; kết quả cập nhật khi đội nhận/từ chối, quá hạn hoặc
-- điều phối hủy. (workflow_run_id, attempt_no) duy nhất: activity chạy lại không ghi trùng.
CREATE TABLE incident_assignments (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_id     uuid NOT NULL REFERENCES incidents (id) ON DELETE CASCADE,
  team_id         uuid NOT NULL REFERENCES rescue_teams (id) ON DELETE RESTRICT,
  workflow_run_id text NOT NULL CHECK (btrim(workflow_run_id) <> ''),
  attempt_no      integer NOT NULL CHECK (attempt_no BETWEEN 1 AND 100),
  urgency         text NOT NULL CHECK (urgency IN ('khan_cap', 'cao', 'trung_binh', 'thap')),
  distance_m      double precision CHECK (distance_m >= 0),
  assigned_at     timestamptz NOT NULL DEFAULT now(),
  deadline_at     timestamptz NOT NULL,
  result          text NOT NULL DEFAULT 'cho_nhan'
                  CHECK (result IN ('cho_nhan', 'da_nhan', 'tu_choi', 'qua_han', 'huy')),
  responded_at    timestamptz,
  -- Tên đăng nhập Keycloak của người nhận/từ chối/hủy (NULL khi quá hạn)
  responded_by    text,
  note            text CHECK (length(note) <= 500),
  UNIQUE (workflow_run_id, attempt_no),
  CHECK (deadline_at > assigned_at),
  CHECK ((result = 'cho_nhan') = (responded_at IS NULL))
);
CREATE INDEX incident_assignments_incident_idx ON incident_assignments (incident_id, assigned_at);
CREATE INDEX incident_assignments_team_idx ON incident_assignments (team_id, assigned_at);

-- ---------- Quyền của role dịch vụ cuu_tro_app (worker) ----------
GRANT SELECT, INSERT (incident_id, started_at, seeking_at),
      UPDATE (started_at, attempts, last_error, seeking_at)
  ON assignment_queue TO cuu_tro_app;
GRANT SELECT, INSERT (incident_id, team_id, workflow_run_id, attempt_no, urgency, distance_m, deadline_at),
      UPDATE (result, responded_at, responded_by, note)
  ON incident_assignments TO cuu_tro_app;

-- Hasura (#26) chỉ đọc lịch sử giao (metadata cuu_tro_incident_assignments.yaml); hàng đợi không track
COMMENT ON TABLE assignment_queue IS 'Hàng đợi khởi chạy workflow phân công tự động (outbox, #67), nội bộ';
COMMENT ON TABLE incident_assignments IS 'Lịch sử giao nhiệm vụ cho đội cứu hộ: nhận, từ chối, quá hạn, hủy (#67)';
COMMENT ON FUNCTION team_reserved_for_more_urgent(uuid, uuid, double precision, integer)
  IS 'Đội đang được giữ cho tin khẩn hơn đang chờ trong bán kính (luật ưu tiên của #67)';
