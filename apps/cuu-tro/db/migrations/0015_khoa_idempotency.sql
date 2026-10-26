-- SPDX-License-Identifier: Apache-2.0
-- Khóa idempotency cho các đường ghi mà app hiện trường gửi lại từ hàng đợi offline (#106, D-011).
-- Mạng chập chờn: app gửi tin kêu cứu, máy chủ đã tạo tin nhưng phản hồi mất giữa đường, app gửi lại. Không có
-- khóa thì lần gửi lại tạo ảnh trùng, hoặc bị chốt chặn trùng của tin kêu cứu trả 409 mà app không biết tin
-- của chính mình đã vào. Client gửi header `Idempotency-Key` (mỗi bản ghi trong hàng đợi một khóa, giữ nguyên
-- khi gửi lại); API (cuu_tro_workflow/idempotency.py) giữ khóa trong CÙNG transaction với bản ghi nghiệp vụ:
--   - lần đầu: INSERT khóa (status_code NULL) trước → làm việc → điền status_code + response → COMMIT;
--   - gửi lại sau khi đã xong: trả lại đúng status_code + response cũ, không làm lại;
--   - hai yêu cầu cùng khóa chạy đồng thời: yêu cầu sau chờ khóa chính (PRIMARY KEY) tới khi yêu cầu trước
--     COMMIT rồi trả lại kết quả của nó; yêu cầu trước lỗi (rollback) thì khóa cũng mất, yêu cầu sau tự làm.
-- Chỉ lưu phản hồi thành công (2xx). Phản hồi lưu không có dữ liệu cá nhân (API bỏ SĐT, tên, văn bản tin).
-- Khóa theo người dùng (sub Keycloak): hai người không đụng khóa của nhau. Hết hạn sau 72 giờ (API xóa khi gặp).

CREATE TABLE idempotency_keys (
  owner_sub      text NOT NULL CHECK (btrim(owner_sub) <> ''),
  key            text NOT NULL CHECK (key ~ '^[A-Za-z0-9_-]{8,128}$'),
  -- "POST /keu-cuu", "POST /tai-len/su-co/{id}/anh", "POST /ai/boc-tach": cùng khóa khác đường dẫn → từ chối
  endpoint       text NOT NULL CHECK (length(endpoint) BETWEEN 1 AND 200),
  -- SHA-256 của endpoint + nội dung yêu cầu: cùng khóa mà nội dung khác (client dùng lại khóa sai) → từ chối
  request_sha256 bytea NOT NULL CHECK (length(request_sha256) = 32),
  status_code    smallint CHECK (status_code BETWEEN 200 AND 299),
  response       jsonb CHECK (jsonb_typeof(response) = 'object'),
  created_at     timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (owner_sub, key),
  -- Đang xử lý (chỉ thấy được trong transaction giữ khóa) hoặc đã xong, đủ cả hai cột
  CHECK ((status_code IS NULL) = (response IS NULL))
);
CREATE INDEX idempotency_keys_created_idx ON idempotency_keys (created_at);

COMMENT ON TABLE idempotency_keys IS 'Khóa Idempotency-Key của API ứng dụng (#106): gửi lại cùng khóa trả kết quả cũ, không tạo trùng';
COMMENT ON COLUMN idempotency_keys.response IS 'Phản hồi 2xx đã trả (không có dữ liệu cá nhân)';

-- Chỉ cuu-tro-api dùng (role dịch vụ cuu_tro_app). DELETE để dọn khóa hết hạn. Hasura không track bảng này.
GRANT SELECT, INSERT, DELETE ON idempotency_keys TO cuu_tro_app;
GRANT UPDATE (status_code, response) ON idempotency_keys TO cuu_tro_app;
