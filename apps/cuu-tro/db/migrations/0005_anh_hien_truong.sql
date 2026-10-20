-- SPDX-License-Identifier: Apache-2.0
-- Ảnh hiện trường gắn với tin kêu cứu (#27). Nội dung ảnh nằm trên SeaweedFS (bucket cuu-tro-media,
-- khai báo ở apps/cuu-tro/s3/buckets), bảng này chỉ giữ siêu dữ liệu.
-- Chỉ API cuu-tro-api (role DB cuu_tro_app) thêm dòng, SAU KHI đã kiểm magic bytes, kích thước và
-- ghi object lên S3. Không vai trò người dùng nào thêm/sửa/xóa qua GraphQL (metadata Hasura chỉ cho đọc),
-- để không ai tạo được dòng trỏ tới object tùy ý.

CREATE TABLE incident_media (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_id  uuid NOT NULL REFERENCES incidents (id) ON DELETE RESTRICT,
  -- Khóa object trong bucket: su-co/<incident_id>/<id>.<đuôi>. Không chứa tên tệp của người dùng
  object_key   text NOT NULL UNIQUE CHECK (object_key ~ '^su-co/[0-9a-f-]{36}/[0-9a-f-]{36}\.(jpg|png|webp)$'),
  -- Loại thật xác định từ magic bytes, không lấy từ Content-Type của client
  content_type text NOT NULL CHECK (content_type IN ('image/jpeg', 'image/png', 'image/webp')),
  size_bytes   bigint NOT NULL CHECK (size_bytes > 0),
  sha256       text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
  -- sub của người dùng Keycloak (= x-hasura-user-id) và vai trò dùng khi tải lên
  uploaded_by  text NOT NULL CHECK (btrim(uploaded_by) <> ''),
  uploader_role text NOT NULL CHECK (uploader_role IN ('dieu-phoi', 'cuu-ho', 'tinh-nguyen')),
  uploaded_at  timestamptz NOT NULL DEFAULT now(),
  -- Chừa chỗ cho quét mã độc ClamAV ở biên (profile sec, việc sau): hiện mọi ảnh là chua_quet
  scan_status  text NOT NULL DEFAULT 'chua_quet' CHECK (scan_status IN ('chua_quet', 'sach', 'nhiem'))
);
CREATE INDEX incident_media_incident_idx ON incident_media (incident_id, uploaded_at);
CREATE INDEX incident_media_uploaded_by_idx ON incident_media (uploaded_by);

COMMENT ON TABLE incident_media IS 'Siêu dữ liệu ảnh hiện trường của tin kêu cứu; nội dung ở SeaweedFS (S3)';
COMMENT ON COLUMN incident_media.object_key IS 'Khóa object trong bucket media của ứng dụng';
COMMENT ON COLUMN incident_media.scan_status IS 'chua_quet | sach | nhiem (ClamAV, việc sau)';

-- Quyền tối thiểu cho cuu-tro-api (role dịch vụ cuu_tro_app, như 0003/0004): thêm dòng và đọc lại
-- dòng vừa thêm (RETURNING). Không UPDATE/DELETE: ảnh đã ghi nhận là bằng chứng hiện trường.
GRANT SELECT, INSERT ON incident_media TO cuu_tro_app;
