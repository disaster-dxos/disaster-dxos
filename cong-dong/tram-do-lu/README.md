<!-- SPDX-License-Identifier: Apache-2.0 -->
# Bộ mô phỏng trạm đo lũ + mô hình NGSI-LD trạm đo

*Flood gauge simulator + NGSI-LD gauge station data model, published for the community (#112). English summary at the end.*

Thư mục này dùng được **độc lập** với Disaster DX-OS: chép nguyên thư mục là chạy, chỉ cần Python 3.9 trở lên, không cài thêm gì. Bạn có thể dùng nó để:

- thử dashboard, bản đồ, luồng cảnh báo của mình bằng một trận lũ "giống thật" mà không cần thiết bị;
- đẩy dữ liệu vào broker MQTT bất kỳ (Mosquitto, EMQX, NATS…) hoặc thẳng vào NGSI-LD context broker (Scorpio, Orion-LD, Stellio);
- dùng lại mô hình NGSI-LD trạm đo mực nước, đo mưa, đo gió (JSON-LD `@context`, JSON Schema, ví dụ).

> **Dữ liệu giả lập.** Tên địa danh và tọa độ (gần đúng) của 9 trạm ở Quảng Nam, Đà Nẵng là thật; mực nước nền, ngưỡng và mọi giá trị đo là **giả định**, không phải số liệu quan trắc, không dùng cho vận hành.

| Tệp | Nội dung |
|---|---|
| [`mo_phong.py`](mo_phong.py) | Bộ mô phỏng: 3 kịch bản, đầu ra NDJSON, MQTT (QoS 1), thực thể NGSI-LD, upsert vào broker |
| [`du-lieu/tran-lu-mau.json`](du-lieu/tran-lu-mau.json) | Trận lũ mẫu 49 giờ (giờ 0 → 48) × 9 trạm: 7 trạm mực nước, 2 trạm đo mưa |
| [`ngsi-ld/context.jsonld`](ngsi-ld/context.jsonld) | `@context` JSON-LD của mô hình |
| [`ngsi-ld/schema/tram-do.schema.json`](ngsi-ld/schema/tram-do.schema.json) | JSON Schema (draft 2020-12) của thực thể trạm đo (dạng chuẩn hóa) |
| [`ngsi-ld/schema/ban-tin-mqtt.schema.json`](ngsi-ld/schema/ban-tin-mqtt.schema.json) | JSON Schema của bản tin MQTT thiết bị gửi |
| [`ngsi-ld/vi-du/`](ngsi-ld/vi-du/) | Thực thể mẫu `WaterLevelStation`, `RainGauge`, `WindStation`, gửi thẳng vào broker được |

## 1. Chạy nhanh

```bash
cd cong-dong/tram-do-lu
# Cả trận lũ (49 giờ × 9 trạm = 441 bản tin), thời điểm lùi mỗi bước 1 giờ, bản cuối là bây giờ
python3 mo_phong.py --kich-ban tran-lu --phat-lai > tran-lu.ndjson
# Đỉnh lũ ở Câu Lâu (giờ 22), dạng thực thể NGSI-LD
python3 mo_phong.py --kich-ban tran-lu --buoc-dau 22 --mot-lan --ngsi-ld --tram QN-CL-01
# Mỗi 10 giây một bản tin mỗi trạm, nước lên dần quá ngưỡng nguy hiểm sau 6 chu kỳ
python3 mo_phong.py --kich-ban vuot-nguong --lien-tuc
```

Mỗi dòng NDJSON: `{"topic": "cuu-tro/cam-bien/QN-CL-01/muc-nuoc", "ma_tram": "QN-CL-01", "gia_tri": 450.0, "don_vi": "cm", "thoi_diem": "2026-10-24T01:00:00.000+00:00"}`.

### Kịch bản

| `--kich-ban` | Giá trị |
|---|---|
| `binh-thuong` (mặc định) | Dao động ±2 % quanh mực nền, không quá 95 % ngưỡng cảnh báo |
| `vuot-nguong` | Từ mực nền lên tuyến tính tới 105 % ngưỡng nguy hiểm trong `--so-buoc` chu kỳ (mặc định 6) rồi giữ. `--mot-lan` gửi ngay giá trị đỉnh |
| `tran-lu` | Trận lũ mẫu: mỗi chu kỳ là giờ kế tiếp của chuỗi (dâng → đỉnh → rút), hết chuỗi thì giữ giá trị cuối. `--buoc-dau N` bắt đầu từ giờ N. `--phat-lai` gửi ngay cả chuỗi |

Trận lũ mẫu có hình dạng lũ do mưa lớn trên lưu vực Vu Gia – Thu Bồn: mưa đạt đỉnh trước (giờ 12–13), trạm thượng nguồn (Ái Nghĩa, Giao Thủy, giờ 19–20) lên đỉnh trước trạm hạ lưu (Câu Lâu giờ 22, Hội An giờ 24).

### Tham số khác

| Tham số | Ý nghĩa |
|---|---|
| `--mot-lan` · `--lien-tuc` · `--phat-lai` | Một bản tin mỗi trạm rồi thoát · gửi định kỳ (mặc định) · cả chuỗi `tran-lu` |
| `--tram MA [MA …]` | Chỉ các trạm này (mã trong `du-lieu/tran-lu-mau.json`) |
| `--chu-ky GIAY` | Khoảng cách hai chu kỳ ở chế độ liên tục (mặc định 10) |
| `--so-lan N` | Dừng sau N chu kỳ (0 = không dừng) |
| `--seed N` | Cố định nhiễu của `binh-thuong`: cùng seed cho cùng chuỗi |
| `--tien-to X` | Tiền tố topic (mặc định `cuu-tro`) |

## 2. Gửi vào broker MQTT

```bash
# Mosquitto trên máy (không xác thực)
python3 mo_phong.py --mqtt localhost:1883 --kich-ban tran-lu --lien-tuc --chu-ky 2
# Có xác thực: mật khẩu chỉ qua biến môi trường, không qua tham số
MQTT_PASSWORD='...' python3 mo_phong.py --mqtt broker.example:1883 --mqtt-user thiet-bi --kich-ban vuot-nguong
# Xem ở phía nhận
mosquitto_sub -h localhost -t 'cuu-tro/cam-bien/#' -v
```

Bộ mô phỏng dùng MQTT 3.1.1, QoS 1 (chờ PUBACK từng bản tin), clean session, không TLS. Cần TLS thì đặt broker sau một proxy TLS hoặc dùng client MQTT đầy đủ (ví dụ paho-mqtt) với cùng topic và payload.

### Topic và payload

```
<tiền tố>/cam-bien/<mã trạm>/<đại lượng>        ví dụ cuu-tro/cam-bien/QN-CL-01/muc-nuoc
```

| Đại lượng | `don_vi` | Loại trạm (`kind`) |
|---|---|---|
| `muc-nuoc` | `cm` | `muc_nuoc` |
| `luong-mua` | `mm` | `luong_mua` |
| `gio` | `m/s` | `gio` |

Payload là JSON UTF-8 (≤ 4096 byte), schema: [`ban-tin-mqtt.schema.json`](ngsi-ld/schema/ban-tin-mqtt.schema.json).

| Trường | Kiểu | Quy định |
|---|---|---|
| `ma_tram` | chuỗi | `^[A-Z0-9][A-Z0-9_-]{1,31}$`, trùng `<mã trạm>` của topic (không có `.` hay `/`, nên dùng được làm subject NATS) |
| `gia_tri` | số | Trong [-1000, 100000]; không nhận `true`/`false`, NaN, chuỗi |
| `don_vi` | chuỗi | Phải khớp đại lượng của topic |
| `thoi_diem` | chuỗi ISO 8601 | **Bắt buộc có múi giờ** (`Z` hoặc `+07:00`); là lúc thiết bị đo, không phải lúc gửi |

Disaster DX-OS bỏ (không giao lại) bản tin sai các quy định trên, bản tin ở tương lai quá 5 phút và bản tin cũ hơn 7 ngày; bản tin gửi bù (cũ hơn lần đo cuối) vẫn vào chuỗi đo nhưng không ghi đè trạng thái mới nhất.

## 3. Mô hình NGSI-LD trạm đo

Mỗi trạm là một thực thể; Disaster DX-OS cập nhật thực thể mỗi khi có bản tin mới (bản sao số). Một thực thể chỉ giữ **trạng thái mới nhất**; chuỗi theo thời gian nằm ở CSDL (hoặc NGSI-LD temporal API nếu broker của bạn bật).

| `type` | Thuộc tính đo | `unitCode` (UN/CEFACT) | `id` |
|---|---|---|---|
| `WaterLevelStation` | `waterLevel` | `CMT` (cm) | `urn:ngsi-ld:WaterLevelStation:<mã trạm>` |
| `RainGauge` | `precipitation` | `MMT` (mm) | `urn:ngsi-ld:RainGauge:<mã trạm>` |
| `WindStation` | `windSpeed` | `MTS` (m/s) | `urn:ngsi-ld:WindStation:<mã trạm>` |

| Thuộc tính | Loại | Ý nghĩa |
|---|---|---|
| `name` | Property (chuỗi) | Tên trạm (`https://schema.org/name`) |
| `stationCode` | Property (chuỗi) | Mã trạm, trùng `<mã trạm>` của topic MQTT |
| `location` | GeoProperty (Point) | `[kinh độ, vĩ độ]`, WGS 84 |
| `waterLevel` · `precipitation` · `windSpeed` | Property (số) + `unitCode` + `observedAt` | Lần đo mới nhất; `observedAt` = `thoi_diem` của bản tin, UTC |
| `alertLevel` | Property (chuỗi) + `observedAt` | `binh_thuong` · `canh_bao` (≥ `warningThreshold`) · `nguy_hiem` (≥ `dangerThreshold`) |
| `warningThreshold`, `dangerThreshold` | Property (số) + `unitCode` | Ngưỡng của trạm tại lúc ghi; không có nếu trạm không đặt ngưỡng |

Tên thuộc tính theo phong cách [Smart Data Models](https://smartdatamodels.org/) (camelCase, `unitCode`, `observedAt`) nhưng IRI là của dự án (`dxos:`), nên không ngầm nhận là đúng một mô hình SDM cụ thể. Context gồm đúng các term trên; core context NGSI-LD do broker tự có. Mô tả từng IRI: [`apps/cuu-tro/ngsi-ld/README.md`](../../apps/cuu-tro/ngsi-ld/README.md).

Ví dụ rút gọn (đầy đủ trong [`ngsi-ld/vi-du/water-level-station.jsonld`](ngsi-ld/vi-du/water-level-station.jsonld)):

```json
{
  "id": "urn:ngsi-ld:WaterLevelStation:QN-CL-01",
  "type": "WaterLevelStation",
  "name": {"type": "Property", "value": "Mực nước sông Thu Bồn tại Câu Lâu, Duy Xuyên (giả lập)"},
  "stationCode": {"type": "Property", "value": "QN-CL-01"},
  "location": {"type": "GeoProperty", "value": {"type": "Point", "coordinates": [108.278, 15.866]}},
  "waterLevel": {"type": "Property", "value": 450.0, "unitCode": "CMT", "observedAt": "2026-10-24T01:00:00.000Z"},
  "alertLevel": {"type": "Property", "value": "nguy_hiem", "observedAt": "2026-10-24T01:00:00.000Z"},
  "warningThreshold": {"type": "Property", "value": 300.0, "unitCode": "CMT"},
  "dangerThreshold": {"type": "Property", "value": 400.0, "unitCode": "CMT"},
  "@context": [{"dxos": "…", "WaterLevelStation": "dxos:WaterLevelStation", "…": "…"}]
}
```

Các tệp ví dụ có `@context` nội tuyến (không cần broker tải context từ Internet).

## 4. Đưa vào NGSI-LD context broker

```bash
# Gửi một thực thể mẫu (Scorpio, Orion-LD, Stellio đều nhận dạng này)
curl -i -X POST http://localhost:9090/ngsi-ld/v1/entityOperations/upsert \
  -H 'Content-Type: application/ld+json' \
  --data "[$(cat ngsi-ld/vi-du/water-level-station.jsonld)]"
# Bộ mô phỏng tự upsert 9 trạm sau mỗi chu kỳ (token nếu broker đặt sau gateway: biến NGSI_LD_TOKEN)
python3 mo_phong.py --ngsi-ld-url http://localhost:9090 --kich-ban tran-lu --lien-tuc --chu-ky 5
```

Đọc lại (ghi chú: broker cần biết context để trả tên ngắn; gửi header `Link` tới nơi bạn đặt `context.jsonld`, hoặc đọc dạng IRI đầy đủ):

```bash
CTX='<https://example.org/context.jsonld>; rel="http://www.w3.org/ns/json-ld#context"; type="application/ld+json"'
B=http://localhost:9090/ngsi-ld/v1
curl -s -H "Link: $CTX" "$B/entities?type=WaterLevelStation&options=keyValues"
curl -s -G -H "Link: $CTX" "$B/entities" --data-urlencode 'type=WaterLevelStation' \
  --data-urlencode 'q=alertLevel=="nguy_hiem"' --data-urlencode 'options=keyValues'
curl -s -G -H "Link: $CTX" -H 'Accept: application/geo+json' "$B/entities" --data-urlencode 'type=WaterLevelStation' \
  --data-urlencode 'georel=near;maxDistance==5000' --data-urlencode 'geometry=Point' \
  --data-urlencode 'coordinates=[108.11,15.86]' --data-urlencode 'options=keyValues'
```

Kiểm một thực thể theo schema (ví dụ bằng [`check-jsonschema`](https://github.com/python-jsonschema/check-jsonschema), Apache-2.0):

```bash
pipx run check-jsonschema==0.29.4 --schemafile ngsi-ld/schema/tram-do.schema.json ngsi-ld/vi-du/*.jsonld
```

## 5. Dùng với Disaster DX-OS

Trong Disaster DX-OS, MQTT của lõi là NATS (cổng `127.0.0.1:${NATS_MQTT_PORT}`), user thiết bị `cuu-tro-thiet-bi` chỉ được gửi vào `cuu-tro/…`; mật khẩu do OpenBao cấp, chỉ có trong container giả lập. Cách gọn nhất là chạy `mo_phong.py` trong container đó:

```bash
make up
docker compose --profile core --profile app run --rm --no-deps -T \
  -v "$PWD/cong-dong/tram-do-lu:/opt/cong-dong:ro" cuu-tro-gia-lap \
  python /opt/cong-dong/mo_phong.py --mqtt nats:1883 --kich-ban tran-lu --phat-lai
```

Bản tin đi qua JetStream → bảng `sensor_readings` (đọc qua `/graphql`) và thực thể trên Scorpio (đọc qua `/ngsi-ld/v1/*` của API Gateway, cần JWT), lên lớp trạm đo của bản đồ điều phối và cảnh báo vượt ngưỡng. Luồng chi tiết: `docs/architecture.md` mục 7.4, 7.4a; bộ giả lập trong lõi: `apps/cuu-tro/workflow/cuu_tro_workflow/gia_lap.py` (cùng kịch bản, dùng paho-mqtt).

Thêm trạm của bạn: thêm phần tử vào `du-lieu/tran-lu-mau.json` (`ma`, `ten`, `kind`, `kinh_do`, `vi_do`, `muc_nen`, `nguong_canh_bao`, `nguong_nguy_hiem`, `chuoi` theo giờ). Trong Disaster DX-OS trạm phải có trong bảng `cuu_tro.sensors` thì bản tin mới được nhận.

## 6. Đồng bộ với mã nguồn

Bản công bố này không được lệch khỏi backend: `apps/cuu-tro/workflow/tests/test_cuu_tro_cong_dong.py` so dữ liệu, `@context`, giá trị từng kịch bản (cùng seed), topic, payload, thực thể NGSI-LD và các tệp ví dụ với `gia_lap.py`, `cam_bien.py`, `ngsi_ld.py`; kiểm MQTT tối giản với broker giả và upsert với HTTP server giả. `scripts/smoke-ngsi-ld.sh` (mục 4b) chạy `mo_phong.py` vào NATS thật của lõi và so 9 thực thể trên Scorpio với thực thể `mo_phong` dựng. Sửa mô hình thì sửa cả hai nơi, chạy lại pytest.

Giấy phép: mã Apache-2.0; dữ liệu và schema Apache-2.0 (tệp `.license` đi kèm).

---

## English summary

A self-contained flood gauge simulator and an NGSI-LD data model for gauge stations, usable without the rest of Disaster DX-OS. Requires only Python 3.9+ (standard library: a minimal MQTT 3.1.1 QoS 1 client and HTTP).

- `mo_phong.py`: three scenarios (`binh-thuong` normal, `vuot-nguong` rising above danger, `tran-lu` a 49-hour sample flood for 9 stations in Quang Nam / Da Nang). Outputs NDJSON (default), MQTT (`--mqtt host:port`, password via `MQTT_PASSWORD`), NGSI-LD entities (`--ngsi-ld`), or upserts to a context broker (`--ngsi-ld-url`, token via `NGSI_LD_TOKEN`).
- MQTT topic `<prefix>/cam-bien/<station>/<quantity>` with quantity `muc-nuoc` (water level, cm), `luong-mua` (rainfall, mm), `gio` (wind, m/s); JSON payload `{ma_tram, gia_tri, don_vi, thoi_diem}` where `thoi_diem` is ISO 8601 with an explicit offset.
- NGSI-LD types `WaterLevelStation` / `RainGauge` / `WindStation` with `waterLevel` / `precipitation` / `windSpeed` (UN/CEFACT `CMT`, `MMT`, `MTS`, `observedAt`), `alertLevel`, `warningThreshold`, `dangerThreshold`, `stationCode`, `name`, `location`. JSON-LD context, JSON Schemas and inline-context examples are in `ngsi-ld/`.
- **All measurements and thresholds are simulated**; only place names and approximate coordinates are real. Do not use for operations.
