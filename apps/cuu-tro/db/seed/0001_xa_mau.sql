-- SPDX-License-Identifier: Apache-2.0
-- Dữ liệu GIẢ cho máy dev và trình diễn (#25): "xã An Lạc" giả định ven sông ở miền Trung,
-- tọa độ quanh 15,85° B – 108,10° Đ. Tên, SĐT (dạng 09xxxxxxx0) đều bịa, không phải dữ liệu thật.
-- Chạy lại được: id cố định + ON CONFLICT DO NOTHING (phiếu nhập không cộng tồn kho lần hai).
-- Chạy: make seed

-- Tin mẫu giữ nguyên trạng thái seed: không tự khởi chạy workflow phân công (trigger 0007, #67)
SET LOCAL cuu_tro.tu_phan_cong = off;

INSERT INTO rescue_teams (id, name, member_count, location, location_updated_at, status, contact_name, contact_phone) VALUES
  ('a0000000-0000-4000-8000-000000000001', 'Đội xung kích thôn 1', 8,
   ST_MakePoint(108.1012, 15.8521)::geography, now(), 'san_sang', 'Trần Văn Mẫu', '0900000010'),
  ('a0000000-0000-4000-8000-000000000002', 'Đội ca nô Biên phòng (giả định)', 6,
   ST_MakePoint(108.1180, 15.8433)::geography, now(), 'san_sang', 'Lê Thị Thử', '0900000020'),
  ('a0000000-0000-4000-8000-000000000003', 'Đội thanh niên tình nguyện', 12,
   ST_MakePoint(108.0890, 15.8610)::geography, now(), 'dang_lam_nhiem_vu', 'Phạm Văn Giả', '0900000030'),
  ('a0000000-0000-4000-8000-000000000004', 'Đội y tế lưu động', 4,
   NULL, NULL, 'nghi', 'Ngô Thị Ví Dụ', '0900000040')
ON CONFLICT (id) DO NOTHING;

INSERT INTO incidents (id, description, location, address_text, people_count, urgency, status,
                       reporter_phone, reporter_name, source, assigned_team_id) VALUES
  ('b0000000-0000-4000-8000-000000000001', 'Nước ngập tới mái, 2 người già và 1 trẻ nhỏ trên gác',
   ST_MakePoint(108.1035, 15.8502)::geography, 'Thôn 1, xã An Lạc (giả định)', 3, 'khan_cap', 'tiep_nhan',
   '0911111110', 'Người báo A', 'dien_thoai', NULL),
  ('b0000000-0000-4000-8000-000000000002', 'Cả nhà 5 người mắc kẹt, cần ca nô',
   ST_MakePoint(108.1150, 15.8455)::geography, 'Thôn 2, xã An Lạc (giả định)', 5, 'cao', 'phan_cong',
   '0922222220', 'Người báo B', 'telegram', 'a0000000-0000-4000-8000-000000000002'),
  ('b0000000-0000-4000-8000-000000000003', 'Hết lương thực 2 ngày, nước chưa rút',
   ST_MakePoint(108.0920, 15.8590)::geography, 'Thôn 3, xã An Lạc (giả định)', 4, 'trung_binh', 'dang_cuu',
   '0933333330', NULL, 'app', 'a0000000-0000-4000-8000-000000000003'),
  ('b0000000-0000-4000-8000-000000000004', 'Người bị thương ở chân, cần sơ cứu',
   ST_MakePoint(108.0985, 15.8550)::geography, 'Gần trường tiểu học (giả định)', 1, 'cao', 'tiep_nhan',
   '0944444440', 'Người báo D', 'web', NULL),
  ('b0000000-0000-4000-8000-000000000005', 'Đã đưa 2 người lên điểm trú ẩn',
   ST_MakePoint(108.1070, 15.8480)::geography, 'Thôn 1, xã An Lạc (giả định)', 2, 'thap', 'da_cuu',
   '0955555550', NULL, 'dien_thoai', 'a0000000-0000-4000-8000-000000000001')
ON CONFLICT (id) DO NOTHING;

INSERT INTO shelters (id, name, location, address_text, capacity, current_occupancy, contact_phone) VALUES
  ('c0000000-0000-4000-8000-000000000001', 'Trường THCS An Lạc (giả định)',
   ST_MakePoint(108.0960, 15.8575)::geography, 'Trung tâm xã', 300, 120, '0966666660'),
  ('c0000000-0000-4000-8000-000000000002', 'Nhà văn hóa thôn 2 (giả định)',
   ST_MakePoint(108.1105, 15.8470)::geography, 'Thôn 2', 80, 35, '0977777770'),
  ('c0000000-0000-4000-8000-000000000003', 'Trụ sở UBND xã (giả định)',
   ST_MakePoint(108.0995, 15.8540)::geography, 'Trung tâm xã', 150, 0, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO supplies (id, item_name, unit, quantity, storage_name, shelter_id, location) VALUES
  ('d0000000-0000-4000-8000-000000000001', 'Gạo', 'kg', 0, 'Kho UBND xã',
   'c0000000-0000-4000-8000-000000000003', ST_MakePoint(108.0995, 15.8540)::geography),
  ('d0000000-0000-4000-8000-000000000002', 'Nước uống đóng chai', 'thùng', 0, 'Kho UBND xã',
   'c0000000-0000-4000-8000-000000000003', ST_MakePoint(108.0995, 15.8540)::geography),
  ('d0000000-0000-4000-8000-000000000003', 'Áo phao', 'chiếc', 0, 'Điểm THCS An Lạc',
   'c0000000-0000-4000-8000-000000000001', ST_MakePoint(108.0960, 15.8575)::geography),
  ('d0000000-0000-4000-8000-000000000004', 'Mì tôm', 'thùng', 0, 'Điểm THCS An Lạc',
   'c0000000-0000-4000-8000-000000000001', ST_MakePoint(108.0960, 15.8575)::geography)
ON CONFLICT (id) DO NOTHING;

-- Tồn kho hình thành từ phiếu nhập/xuất (trigger cộng/trừ supplies.quantity)
INSERT INTO supply_movements (id, supply_id, direction, quantity, note, shelter_id) VALUES
  ('e0000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000001', 'nhap', 1500, 'Tiếp nhận từ huyện (giả định)', NULL),
  ('e0000000-0000-4000-8000-000000000002', 'd0000000-0000-4000-8000-000000000001', 'xuat', 300, 'Cấp cho điểm THCS', 'c0000000-0000-4000-8000-000000000001'),
  ('e0000000-0000-4000-8000-000000000003', 'd0000000-0000-4000-8000-000000000002', 'nhap', 200, 'Ủng hộ của doanh nghiệp (giả định)', NULL),
  ('e0000000-0000-4000-8000-000000000004', 'd0000000-0000-4000-8000-000000000003', 'nhap', 60, 'Mượn của đồn biên phòng (giả định)', NULL),
  ('e0000000-0000-4000-8000-000000000005', 'd0000000-0000-4000-8000-000000000004', 'nhap', 100, 'Ủng hộ của hội chữ thập đỏ (giả định)', NULL)
ON CONFLICT (id) DO NOTHING;

-- Bút toán tiền cứu trợ (#89), số liệu giả định; worker tự niêm phong lên sổ cái sau khi nạp seed
INSERT INTO relief_fund_entries (id, direction, amount, category, purpose, shelter_id) VALUES
  ('e1000000-0000-4000-8000-000000000001', 'thu', 50000000, 'ung_ho', 'Ủng hộ của doanh nghiệp (giả định)', NULL),
  ('e1000000-0000-4000-8000-000000000002', 'thu', 20000000, 'ngan_sach', 'Tạm ứng ngân sách xã (giả định)', NULL),
  ('e1000000-0000-4000-8000-000000000003', 'chi', 12000000, 'mua_hang', 'Mua nước uống, mì gói (giả định)', NULL),
  ('e1000000-0000-4000-8000-000000000004', 'chi', 3000000, 'van_chuyen', 'Thuê ca nô chở hàng (giả định)',
   'c0000000-0000-4000-8000-000000000001')
ON CONFLICT (id) DO NOTHING;

INSERT INTO sensors (id, code, name, kind, unit, location, warning_threshold, danger_threshold,
                     last_value, last_observed_at, ngsi_ld_id) VALUES
  ('f0000000-0000-4000-8000-000000000001', 'AL-MN-01', 'Mực nước cầu An Lạc (giả định)', 'muc_nuoc', 'cm',
   ST_MakePoint(108.1040, 15.8495)::geography, 350, 450, 380, now(), 'urn:ngsi-ld:WaterLevelStation:AL-MN-01'),
  ('f0000000-0000-4000-8000-000000000002', 'AL-MN-02', 'Mực nước bến đò thôn 2 (giả định)', 'muc_nuoc', 'cm',
   ST_MakePoint(108.1160, 15.8440)::geography, 300, 400, 210, now(), 'urn:ngsi-ld:WaterLevelStation:AL-MN-02'),
  ('f0000000-0000-4000-8000-000000000003', 'AL-LM-01', 'Lượng mưa UBND xã (giả định)', 'luong_mua', 'mm',
   ST_MakePoint(108.0995, 15.8540)::geography, 100, 200, NULL, NULL, 'urn:ngsi-ld:RainGauge:AL-LM-01'),
  -- Trạm của trận lũ mẫu (#84): địa danh và tọa độ (gần đúng) ở Quảng Nam, Đà Nẵng là thật; ngưỡng là
  -- giả định, không phải cấp báo động chính thức. Khớp cuu_tro_workflow/du_lieu/tran_lu_mau.json (pytest kiểm).
  ('f0000000-0000-4000-8000-000000000004', 'QN-AN-01', 'Mực nước sông Vu Gia tại Ái Nghĩa, Đại Lộc (giả lập)', 'muc_nuoc', 'cm',
   ST_MakePoint(108.1150, 15.8860)::geography, 900, 1000, NULL, NULL, 'urn:ngsi-ld:WaterLevelStation:QN-AN-01'),
  ('f0000000-0000-4000-8000-000000000005', 'QN-GT-01', 'Mực nước sông Thu Bồn tại Giao Thủy, Đại Lộc (giả lập)', 'muc_nuoc', 'cm',
   ST_MakePoint(108.1260, 15.8330)::geography, 750, 850, NULL, NULL, 'urn:ngsi-ld:WaterLevelStation:QN-GT-01'),
  ('f0000000-0000-4000-8000-000000000006', 'QN-CL-01', 'Mực nước sông Thu Bồn tại Câu Lâu, Duy Xuyên (giả lập)', 'muc_nuoc', 'cm',
   ST_MakePoint(108.2780, 15.8660)::geography, 300, 400, NULL, NULL, 'urn:ngsi-ld:WaterLevelStation:QN-CL-01'),
  ('f0000000-0000-4000-8000-000000000007', 'QN-HA-01', 'Mực nước sông Hoài tại Hội An (giả lập)', 'muc_nuoc', 'cm',
   ST_MakePoint(108.3330, 15.8770)::geography, 150, 200, NULL, NULL, 'urn:ngsi-ld:WaterLevelStation:QN-HA-01'),
  ('f0000000-0000-4000-8000-000000000008', 'DN-CLE-01', 'Mực nước sông Cẩm Lệ tại cầu Cẩm Lệ, Đà Nẵng (giả lập)', 'muc_nuoc', 'cm',
   ST_MakePoint(108.2050, 16.0160)::geography, 180, 250, NULL, NULL, 'urn:ngsi-ld:WaterLevelStation:DN-CLE-01'),
  ('f0000000-0000-4000-8000-000000000009', 'QN-LM-01', 'Lượng mưa 1 giờ tại Đại Lộc (giả lập)', 'luong_mua', 'mm',
   ST_MakePoint(108.0860, 15.8780)::geography, 30, 60, NULL, NULL, 'urn:ngsi-ld:RainGauge:QN-LM-01')
ON CONFLICT (id) DO NOTHING;

-- Thành viên đội (#26): user mẫu cuuho01 thuộc "Đội ca nô Biên phòng". user_id là "sub" Keycloak,
-- cố định trong apps/cuu-tro/keycloak/realm.json để seed khớp ngay trên volume trống. Realm đã
-- import từ trước (volume Keycloak cũ) có sub ngẫu nhiên: điều phối gán lại đội qua GraphQL
-- (insert_team_members_one … on_conflict), scripts/smoke-hasura.sh làm đúng như vậy.
INSERT INTO team_members (user_id, team_id, username) VALUES
  ('9b000000-0000-4000-8000-000000000002', 'a0000000-0000-4000-8000-000000000002', 'cuuho01')
ON CONFLICT (user_id) DO NOTHING;
