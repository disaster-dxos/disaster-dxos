-- SPDX-License-Identifier: Apache-2.0
-- Bản sao số trạm đo trên Scorpio NGSI-LD (#85): consumer cuu-tro-ban-sao-so (role cuu_tro_app) đọc
-- thêm tọa độ và id thực thể NGSI-LD của trạm để dựng thực thể (cuu_tro_workflow/ban_sao_so.py).
-- Chỉ đọc; consumer không ghi gì vào CSDL (ghi chuỗi đo vẫn là việc của consumer ghi-csdl, 0004).
GRANT SELECT (location, ngsi_ld_id) ON sensors TO cuu_tro_app;
