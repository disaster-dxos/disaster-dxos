-- SPDX-License-Identifier: Apache-2.0
-- Kiểm trước tin trùng cho đề xuất của AI bóc tách tin kêu cứu (#102), KHÔNG tạo tin.
-- Đề xuất của AI chưa phải tin kêu cứu: điều phối viên duyệt rồi mới tạo (HITL). Để người duyệt biết ngay
-- "số này đã báo một tin còn mở gần đây", API hỏi hàm dưới đây với đúng điều kiện của trigger
-- incidents_no_duplicate (0001): cùng SĐT, tin còn mở, trong incident_dedup_config.radius_m mét và
-- window_minutes phút. Trigger vẫn là chốt chặn cuối khi tạo tin (có khóa advisory).
-- cuu_tro_app không có SELECT reporter_phone (0008): hàm chạy với quyền chủ bảng và chỉ trả mã tin +
-- khoảng cách, không trả dữ liệu cá nhân.

CREATE FUNCTION incident_find_duplicate(p_phone text, p_lon double precision, p_lat double precision)
RETURNS TABLE (incident_id uuid, distance_m double precision, radius_m double precision, window_minutes integer)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path FROM CURRENT AS $$
  SELECT i.id, round(ST_Distance(i.location, p.g)::numeric)::double precision, c.radius_m, c.window_minutes
    FROM incident_dedup_config c,
         LATERAL (SELECT ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)::geography AS g) p,
         incidents i
   WHERE i.reporter_phone = p_phone
     AND i.status NOT IN ('da_cuu', 'dong')
     AND i.created_at > now() - make_interval(mins => c.window_minutes)
     AND ST_DWithin(i.location, p.g, c.radius_m)
   ORDER BY i.created_at DESC
   LIMIT 1
$$;

REVOKE ALL ON FUNCTION incident_find_duplicate(text, double precision, double precision) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION incident_find_duplicate(text, double precision, double precision) TO cuu_tro_app;

COMMENT ON FUNCTION incident_find_duplicate(text, double precision, double precision)
  IS 'Tin còn mở trùng (cùng điều kiện trigger incidents_no_duplicate) để kiểm trước đề xuất AI (#102); không khóa, không tạo tin';
