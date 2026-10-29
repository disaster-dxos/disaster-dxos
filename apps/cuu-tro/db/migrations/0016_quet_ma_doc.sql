-- SPDX-License-Identifier: Apache-2.0
-- Quét mã độc ảnh hiện trường (#111): cuu-tro-api quét nội dung bằng clamd của lõi (ClamAV, profile sec) trước
-- khi ghi S3 và CSDL. Tệp nhiễm bị từ chối nên KHÔNG có dòng nào ở đây; dòng có scan_status:
--   sach       clamd báo sạch; scanned_at = lúc quét, scan_engine = "ClamAV <phiên bản>/<số bộ chữ ký daily>"
--   chua_quet  máy quét không có hoặc lỗi lúc tải lên (mặc định vẫn nhận ảnh: tin cứu nạn không mất vì máy quét)
--   nhiem      giữ cho quét lại về sau (bộ chữ ký mới phát hiện tệp cũ); hiện chưa có đường ghi
ALTER TABLE incident_media
  ADD COLUMN scanned_at  timestamptz,
  ADD COLUMN scan_engine text CHECK (length(scan_engine) <= 100),
  ADD CONSTRAINT incident_media_scan_consistent
    CHECK ((scan_status = 'chua_quet') = (scanned_at IS NULL));

COMMENT ON COLUMN incident_media.scan_status IS 'chua_quet | sach | nhiem (ClamAV, #111)';
COMMENT ON COLUMN incident_media.scanned_at IS 'Lúc clamd quét (NULL = chưa quét)';
COMMENT ON COLUMN incident_media.scan_engine IS 'Phiên bản ClamAV / số bộ chữ ký daily lúc quét';

-- cuu_tro_app ghi kết quả quét trong cùng câu INSERT (sau khi quét xong): quyền SELECT, INSERT cả bảng đã có từ
-- 0005, gồm cả hai cột mới. Vẫn không có UPDATE/DELETE: kết quả quét không sửa được sau khi lưu.
