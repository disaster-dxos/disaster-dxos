-- SPDX-License-Identifier: Apache-2.0
-- Dữ liệu giả của module mẫu (#110): kho thiết bị của một tổ dân phố giả định. Chạy lại được.
INSERT INTO devices (id, code, name, kind, condition, location) VALUES
  ('d0000000-0000-4000-8000-000000000001', 'MPD-01', 'Máy phát điện 5 kVA', 'may_phat_dien', 'tot', 'Nhà văn hóa tổ 3 (giả định)'),
  ('d0000000-0000-4000-8000-000000000002', 'MB-01', 'Máy bơm nước chạy xăng', 'may_bom', 'tot', 'Nhà văn hóa tổ 3 (giả định)'),
  ('d0000000-0000-4000-8000-000000000003', 'LOA-01', 'Loa kéo kèm micro', 'loa', 'can_sua', 'Nhà tổ trưởng (giả định)'),
  ('d0000000-0000-4000-8000-000000000004', 'MC-01', 'Máy chiếu', 'may_chieu', 'hong', 'Nhà văn hóa tổ 3 (giả định)')
ON CONFLICT (id) DO NOTHING;
