-- SPDX-License-Identifier: Apache-2.0
-- Tiếp nhận tin kêu cứu qua API cuu-tro-api (#66): POST /workflow/keu-cuu.
-- API kiểm dữ liệu trước (Poka-yoke tầng API, cuu_tro_workflow/keu_cuu.py) rồi INSERT bằng role dịch vụ
-- cuu_tro_app. Chặn trùng vẫn do trigger incidents_no_duplicate của 0001 (cùng SĐT, tin còn mở,
-- ST_DWithin 200 m trên geography, 6 giờ, khóa advisory theo SĐT nên gửi đồng thời không cùng lọt);
-- tự phân công vẫn do trigger outbox của 0007. Migration này chỉ cấp quyền và cho trigger chặn trùng
-- chạy với quyền chủ bảng.

-- cuu_tro_app chỉ thêm được các cột người báo nhập + created_by (sub Keycloak do API gán từ JWT).
-- Không có status/assigned_team_id: tin mới luôn tiep_nhan, chưa có đội (giống quyền tinh-nguyen ở Hasura).
GRANT INSERT (description, location, address_text, people_count, urgency, reporter_phone, reporter_name,
              source, created_by)
  ON incidents TO cuu_tro_app;
-- RETURNING của API: id, status, urgency, people_count đã có từ 0003; thêm created_at. Vẫn KHÔNG đọc được
-- reporter_phone, reporter_name (API không cần đọc lại dữ liệu cá nhân).
GRANT SELECT (created_at) ON incidents TO cuu_tro_app;

-- Trigger chặn trùng đọc reporter_phone của tin khác và bảng incident_dedup_config: chạy với quyền chủ bảng
-- (cuu_tro_owner) để role chỉ có quyền INSERT theo cột vẫn được kiểm đủ. search_path của hàm đã cố định
-- (SET search_path FROM CURRENT, 0001) nên SECURITY DEFINER an toàn; đường Hasura không đổi hành vi.
ALTER FUNCTION incidents_block_duplicate() SECURITY DEFINER;

COMMENT ON FUNCTION incidents_block_duplicate()
  IS 'Chặn tin kêu cứu trùng (SĐT + bán kính + thời gian, incident_dedup_config); lỗi 23505 incidents_no_duplicate, DETAIL incident_id=…';
