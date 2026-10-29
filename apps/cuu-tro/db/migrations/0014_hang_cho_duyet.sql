-- SPDX-License-Identifier: Apache-2.0
-- Hàng chờ duyệt tin do AI bóc tách (#104, Human-in-the-loop, nối tiếp #102).
-- POST /workflow/ai/boc-tach với "vao_hang_cho": true lưu văn bản gốc + TOÀN BỘ đề xuất của AI (do API tạo,
-- client không tự khai) thành một dòng 'cho_duyet'. Điều phối viên duyệt (có thể sửa) thì API tạo tin kêu cứu
-- thật qua cùng Poka-yoke của POST /workflow/keu-cuu (#66) và đánh dấu dòng 'da_duyet' TRONG CÙNG transaction;
-- hủy thì 'da_huy', không tạo tin. Dòng là vết kiểm toán: đề xuất của AI, nội dung tin cuối cùng, các trường
-- người sửa (giá trị AI → giá trị người duyệt), người duyệt, thời điểm.
--
-- Dữ liệu cá nhân: raw_text, ai_result, final_body có SĐT/tên người báo. Chỉ vai dieu-phoi đọc qua Hasura;
-- role dịch vụ cuu_tro_app GHI được nhưng KHÔNG đọc các cột này (như reporter_phone của incidents, 0008):
-- API đọc đề xuất của AI qua Hasura bằng JWT của chính người duyệt.

CREATE TABLE ai_intake_reviews (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  raw_text          text NOT NULL CHECK (length(btrim(raw_text)) BETWEEN 1 AND 2000),
  text_source       text NOT NULL CHECK (text_source IN ('sms', 'zalo', 'dien_thoai', 'mang_xa_hoi', 'van_ban')),
  -- Phản hồi của /ai/boc-tach lúc đưa vào hàng chờ: de_xuat, tin_keu_cuu, poka_yoke, ai, canh_bao
  ai_result         jsonb NOT NULL CHECK (jsonb_typeof(ai_result) = 'object' AND ai_result ? 'de_xuat'
                                          AND ai_result ? 'tin_keu_cuu'),
  ai_provider       text NOT NULL CHECK (ai_provider IN ('gia-lap', 'ollama', 'openai-compatible')),
  ai_model          text CHECK (length(ai_model) <= 100),
  ai_fallback       boolean NOT NULL,
  ai_duration_ms    integer NOT NULL CHECK (ai_duration_ms >= 0),
  -- Tách ra cột để xếp/lọc hàng chờ (tin khẩn trước, tin thiếu tọa độ/trùng) mà không đọc jsonb
  ai_urgency        text NOT NULL CHECK (ai_urgency IN ('khan_cap', 'cao', 'trung_binh', 'thap')),
  ai_valid          boolean NOT NULL,
  submitted_by      text NOT NULL CHECK (btrim(submitted_by) <> ''),
  submitted_by_name text CHECK (length(submitted_by_name) <= 100),
  submitted_role    text NOT NULL CHECK (submitted_role IN ('dieu-phoi', 'tinh-nguyen')),
  created_at        timestamptz NOT NULL DEFAULT now(),
  status            text NOT NULL DEFAULT 'cho_duyet' CHECK (status IN ('cho_duyet', 'da_duyet', 'da_huy')),
  -- Khi duyệt: body đã gửi tạo tin (đã chuẩn hóa) và {trường: {"ai": giá trị AI, "nguoi": giá trị duyệt}}
  final_body        jsonb CHECK (jsonb_typeof(final_body) = 'object'),
  edited_fields     jsonb CHECK (jsonb_typeof(edited_fields) = 'object'),
  reviewed_by       text,
  reviewed_by_name  text CHECK (length(reviewed_by_name) <= 100),
  reviewed_at       timestamptz,
  -- Tin kêu cứu đã tạo. Không ON DELETE: tin có vết duyệt không xóa được (không vai trò nào có DELETE)
  incident_id       uuid UNIQUE REFERENCES incidents (id),
  cancel_reason     text CHECK (length(cancel_reason) <= 500),
  CONSTRAINT ai_intake_reviews_decision CHECK (
    (status = 'cho_duyet' AND reviewed_at IS NULL AND reviewed_by IS NULL AND incident_id IS NULL
       AND final_body IS NULL AND edited_fields IS NULL AND cancel_reason IS NULL)
    OR (status = 'da_duyet' AND reviewed_at IS NOT NULL AND reviewed_by IS NOT NULL AND incident_id IS NOT NULL
       AND final_body IS NOT NULL AND edited_fields IS NOT NULL AND cancel_reason IS NULL)
    OR (status = 'da_huy' AND reviewed_at IS NOT NULL AND reviewed_by IS NOT NULL AND incident_id IS NULL
       AND final_body IS NULL AND edited_fields IS NULL)
  )
);
CREATE INDEX ai_intake_reviews_pending_idx ON ai_intake_reviews (created_at) WHERE status = 'cho_duyet';
CREATE INDEX ai_intake_reviews_reviewed_idx ON ai_intake_reviews (reviewed_at DESC) WHERE status <> 'cho_duyet';
CREATE INDEX ai_intake_reviews_submitted_by_idx ON ai_intake_reviews (submitted_by, created_at DESC);

COMMENT ON TABLE ai_intake_reviews IS 'Hàng chờ duyệt tin kêu cứu do AI bóc tách + vết duyệt (#104, HITL)';
COMMENT ON COLUMN ai_intake_reviews.ai_result IS 'Đề xuất của AI lúc vào hàng chờ (phản hồi /ai/boc-tach), không sửa được';
COMMENT ON COLUMN ai_intake_reviews.edited_fields IS 'Trường người duyệt đổi so với đề xuất: {trường: {ai, nguoi}}; {} = duyệt nguyên đề xuất';
COMMENT ON COLUMN ai_intake_reviews.final_body IS 'Tin kêu cứu đã tạo (body /keu-cuu đã chuẩn hóa)';

-- Vết không sửa được: đề xuất của AI và người gửi giữ nguyên; dòng đã duyệt/hủy không đổi nữa (kể cả role
-- chủ bảng). Chuyển trạng thái chỉ một lần, từ cho_duyet; CHECK ai_intake_reviews_decision giữ các cột khớp.
CREATE FUNCTION ai_intake_reviews_immutable() RETURNS trigger
LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
BEGIN
  IF OLD.status <> 'cho_duyet' THEN
    RAISE EXCEPTION 'Tin trong hàng chờ % đã xử lý (%), không sửa được', OLD.id, OLD.status
      USING ERRCODE = 'restrict_violation';
  END IF;
  IF (NEW.id, NEW.raw_text, NEW.text_source, NEW.ai_result, NEW.ai_provider, NEW.ai_model, NEW.ai_fallback,
      NEW.ai_duration_ms, NEW.ai_urgency, NEW.ai_valid, NEW.submitted_by, NEW.submitted_by_name,
      NEW.submitted_role, NEW.created_at)
     IS DISTINCT FROM
     (OLD.id, OLD.raw_text, OLD.text_source, OLD.ai_result, OLD.ai_provider, OLD.ai_model, OLD.ai_fallback,
      OLD.ai_duration_ms, OLD.ai_urgency, OLD.ai_valid, OLD.submitted_by, OLD.submitted_by_name,
      OLD.submitted_role, OLD.created_at) THEN
    RAISE EXCEPTION 'Đề xuất của AI và người gửi trong hàng chờ % không sửa được', OLD.id
      USING ERRCODE = 'restrict_violation';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER ai_intake_reviews_immutable BEFORE UPDATE ON ai_intake_reviews
  FOR EACH ROW EXECUTE FUNCTION ai_intake_reviews_immutable();

-- Quyền tối thiểu của cuu-tro-api (role dịch vụ cuu_tro_app):
--  - thêm dòng khi bóc tách (mọi cột do API điền từ kết quả AI + JWT người gửi);
--  - đọc cột không phải dữ liệu người dân để trả mã, khóa dòng khi duyệt (SELECT … FOR UPDATE), báo "đã xử
--    lý bởi ai" và gán created_by của tin = người đưa tin vào hàng chờ (sub Keycloak của cán bộ/tình nguyện
--    viên: tình nguyện viên chuyển tin thấy được tin đã tạo, như tin tự gửi);
--  - cập nhật cột quyết định. Không đọc raw_text/ai_result/final_body/edited_fields, không DELETE.
GRANT INSERT (raw_text, text_source, ai_result, ai_provider, ai_model, ai_fallback, ai_duration_ms, ai_urgency,
              ai_valid, submitted_by, submitted_by_name, submitted_role)
  ON ai_intake_reviews TO cuu_tro_app;
GRANT SELECT (id, status, created_at, submitted_by, reviewed_at, reviewed_by_name, incident_id)
  ON ai_intake_reviews TO cuu_tro_app;
GRANT UPDATE (status, final_body, edited_fields, reviewed_by, reviewed_by_name, reviewed_at, incident_id,
              cancel_reason)
  ON ai_intake_reviews TO cuu_tro_app;
