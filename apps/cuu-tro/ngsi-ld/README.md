# Mô hình NGSI-LD trạm đo (bản sao số, #85)

Mỗi trạm trong bảng `cuu_tro.sensors` là một thực thể NGSI-LD trên Scorpio Broker của lõi. Consumer `cuu-tro-ban-sao-so` (`cuu_tro_workflow/ban_sao_so.py`, ánh xạ thuần `cuu_tro_workflow/ngsi_ld.py`) cập nhật thực thể mỗi khi có bản tin cảm biến mới trên stream `CUU_TRO_CAM_BIEN`. Kiến trúc và lý do chọn: `docs/architecture.md` mục 7.4a.

`@context` của ứng dụng: [`context.jsonld`](context.jsonld). Tệp này là nguồn duy nhất cho cả ghi (consumer gửi kèm nội tuyến) và đọc (gateway đặt header `Link` tới bản do `cuu-tro-api` phục vụ ở `/ngsi-ld/context.jsonld`). Không tải gì từ Internet; core context NGSI-LD có sẵn trong Scorpio. Các IRI `dxos:<tên>` trỏ về các mục bên dưới của trang này.

## Kiểu thực thể

| `type` | `sensors.kind` | Thuộc tính đo | Đơn vị (`unitCode` UN/CEFACT) |
|---|---|---|---|
| <a id="WaterLevelStation"></a>`WaterLevelStation` | `muc_nuoc` | `waterLevel` | cm (`CMT`) |
| <a id="RainGauge"></a>`RainGauge` | `luong_mua` | `precipitation` | mm (`MMT`) |
| <a id="WindStation"></a>`WindStation` | `gio` | `windSpeed` | m/s (`MTS`) |

`id` = `sensors.ngsi_ld_id` (seed: `urn:ngsi-ld:WaterLevelStation:<mã trạm>`, `urn:ngsi-ld:RainGauge:<mã trạm>`); trống thì `urn:ngsi-ld:<type>:<mã trạm>`.

## Thuộc tính

| Tên | Loại | Ý nghĩa |
|---|---|---|
| `name` | Property (chuỗi) | Tên trạm (`sensors.name`), IRI `https://schema.org/name` |
| <a id="stationCode"></a>`stationCode` | Property (chuỗi) | Mã trạm (`sensors.code`), cũng là đoạn `<ma_tram>` của topic MQTT |
| `location` | GeoProperty (GeoJSON Point) | Tọa độ trạm `[kinh độ, vĩ độ]` (WGS 84) |
| <a id="waterLevel"></a>`waterLevel` | Property (số), `unitCode`, `observedAt` | Mực nước đo được lần mới nhất; `observedAt` = thời điểm thiết bị đo (UTC) |
| <a id="precipitation"></a>`precipitation` | Property (số), `unitCode`, `observedAt` | Lượng mưa đo được lần mới nhất |
| <a id="windSpeed"></a>`windSpeed` | Property (số), `unitCode`, `observedAt` | Tốc độ gió đo được lần mới nhất |
| <a id="alertLevel"></a>`alertLevel` | Property (chuỗi), `observedAt` | `binh_thuong` · `canh_bao` (≥ ngưỡng cảnh báo) · `nguy_hiem` (≥ ngưỡng nguy hiểm), tính theo ngưỡng tại lúc ghi |
| <a id="warningThreshold"></a>`warningThreshold` | Property (số), `unitCode` | Ngưỡng cảnh báo hiện tại (`sensors.warning_threshold`); không có nếu trạm không đặt |
| <a id="dangerThreshold"></a>`dangerThreshold` | Property (số), `unitCode` | Ngưỡng nguy hiểm hiện tại (`sensors.danger_threshold`); không có nếu trạm không đặt |

Tên thuộc tính đặt theo phong cách Smart Data Models (camelCase, `unitCode` UN/CEFACT, `observedAt`), nhưng IRI là của dự án: không phụ thuộc mạng ngoài và không ngầm nhận là đúng một mô hình SDM cụ thể.

Ví dụ (dạng chuẩn hóa, tên ngắn theo context):

```json
{
  "id": "urn:ngsi-ld:WaterLevelStation:QN-CL-01",
  "type": "WaterLevelStation",
  "name": {"type": "Property", "value": "Mực nước sông Thu Bồn tại Câu Lâu, Duy Xuyên (giả lập)"},
  "stationCode": {"type": "Property", "value": "QN-CL-01"},
  "location": {"type": "GeoProperty", "value": {"type": "Point", "coordinates": [108.278, 15.866]}},
  "waterLevel": {"type": "Property", "value": 412.5, "unitCode": "CMT", "observedAt": "2026-10-24T01:52:02.069Z"},
  "alertLevel": {"type": "Property", "value": "nguy_hiem", "observedAt": "2026-10-24T01:52:02.069Z"},
  "warningThreshold": {"type": "Property", "value": 300.0, "unitCode": "CMT"},
  "dangerThreshold": {"type": "Property", "value": 400.0, "unitCode": "CMT"}
}
```

## Ghi (chỉ backend, mạng nội bộ)

- Consumer bền `ban-sao-so` (`apps/cuu-tro/nats/streams.json`) đọc mọi bản tin `cuu-tro.cam-bien.>`, kiểm như consumer `ghi-csdl` (`cam_bien.phan_tich`), đọc trạm bằng role `cuu_tro_app` (migration 0009: thêm quyền đọc `location`, `ngsi_ld_id`).
- `GET /ngsi-ld/v1/entities/<id>` lấy `observedAt` đang có; bản tin cũ hơn thì bỏ qua (ack). Không thì `POST /ngsi-ld/v1/entityOperations/upsert` (thay cả thực thể). Giao lại, gửi bù, chạy lại stream từ đầu đều cho cùng kết quả.
- Scorpio không trả lời, 5xx, 429 → JetStream giao lại sau 2, 4, 8 … 60 giây (tối đa 20 lần); 4xx khác, trạm không có hoặc đang tắt, bản tin sai → bỏ và ghi log.
- Scorpio chỉ giữ trạng thái mới nhất. Chuỗi đo theo thời gian nằm ở `sensor_readings` (đọc qua `/graphql`).

## Đọc qua API Gateway

Mọi vai trò đã đăng nhập (Bearer JWT Keycloak) đọc được; ghi, `jsonldContexts`, `subscriptions`, `temporal` qua gateway bị chặn (403). Gateway tự đặt header `Link`, nên không cần gửi context:

```bash
TOKEN=...   # access token Keycloak (vd dieuphoi01)
GW=http://localhost:9080
# Mọi trạm mực nước, dạng gọn
curl -s -H "Authorization: Bearer $TOKEN" "$GW/ngsi-ld/v1/entities?type=WaterLevelStation&options=keyValues"
# GeoJSON cho MapLibre (mỗi trạm một Feature; properties có waterLevel, alertLevel, ngưỡng)
curl -s -H "Authorization: Bearer $TOKEN" -H 'Accept: application/geo+json' \
  "$GW/ngsi-ld/v1/entities?type=WaterLevelStation&options=keyValues"
# Chỉ trạm đang ở mức nguy hiểm
curl -s -G -H "Authorization: Bearer $TOKEN" "$GW/ngsi-ld/v1/entities" \
  --data-urlencode 'type=WaterLevelStation' --data-urlencode 'q=alertLevel=="nguy_hiem"' --data-urlencode 'options=keyValues'
# Trạm trong bán kính 5 km quanh một điểm
curl -s -G -H "Authorization: Bearer $TOKEN" "$GW/ngsi-ld/v1/entities" \
  --data-urlencode 'type=WaterLevelStation' --data-urlencode 'georel=near;maxDistance==5000' \
  --data-urlencode 'geometry=Point' --data-urlencode 'coordinates=[108.11,15.86]' --data-urlencode 'options=keyValues'
# Một trạm, dạng đầy đủ (có observedAt, unitCode)
curl -s -H "Authorization: Bearer $TOKEN" "$GW/ngsi-ld/v1/entities/urn:ngsi-ld:WaterLevelStation:QN-CL-01"
```

Kiểm thử: `scripts/smoke-ngsi-ld.sh` (trong `make smoke`), `tests/test_cuu_tro_ban_sao_so.py`.
