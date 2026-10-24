# SPDX-License-Identifier: Apache-2.0
.PHONY: up up-bi gia-lap gia-lap-vuot-nguong gia-lap-tran-lu down logs ps migrate seed test-db test-py license check lint smoke bao-init bao-unseal bao-status

# Dùng .env nếu có, nếu không thì .env.example (để CI/máy sạch vẫn kiểm được compose)
ENV_FILE := $(if $(wildcard .env),.env,.env.example)

up:            ## Chạy lõi headless (profile core) + backend ứng dụng apps/$$DXOS_APP (profile app, #29): OpenBao trước, init/unseal, rồi các dịch vụ còn lại
	docker compose --profile core up -d openbao
	bash scripts/openbao-init.sh
	docker compose --profile core --profile app up -d --build

bao-init:      ## Khởi tạo OpenBao + nạp bí mật, policy, AppRole (idempotent, cần OpenBao đang chạy)
	bash scripts/openbao-init.sh

bao-unseal:    ## Mở khóa OpenBao bằng key trong .data/openbao (khi tắt OPENBAO_DEV_AUTO_UNSEAL)
	bash scripts/openbao-init.sh unseal

bao-status:    ## Trạng thái seal của OpenBao
	docker compose exec openbao bao status

up-bi:         ## Grafana (tuần 4)
	docker compose --profile bi up -d --build

smoke:         ## Kiểm thử OpenBao, JWT, route gateway + WAF, Hasura/SeaweedFS/Temporal/NATS, ràng buộc DB, phân quyền GraphQL, workflow phân công, luồng cảm biến MQTT, ảnh hiện trường, sổ cái minh bạch, web điều phối qua gateway, thông báo realtime Centrifugo, bản đồ tin kêu cứu realtime (GraphQL subscription), màn phân công 2 vai, API kêu cứu Poka-yoke, bản sao số trạm đo NGSI-LD trên Scorpio + trận lũ mẫu (cần make up trước)
	bash scripts/smoke-openbao.sh
	bash scripts/smoke-jwt.sh
	bash scripts/smoke-gateway.sh
	bash scripts/smoke-core.sh
	docker compose --profile core run --rm --no-deps migrate test
	docker compose --profile core run --rm --no-deps migrate seed
	bash scripts/smoke-hasura.sh
	bash scripts/smoke-workflow.sh
	bash scripts/smoke-cam-bien.sh
	bash scripts/smoke-anh.sh
	bash scripts/smoke-ledger.sh
	bash scripts/smoke-web.sh
	bash scripts/smoke-realtime.sh
	bash scripts/smoke-ban-do.sh
	bash scripts/smoke-phan-cong.sh
	bash scripts/smoke-keu-cuu.sh
	bash scripts/smoke-ngsi-ld.sh

gia-lap:       ## Giả lập trạm cảm biến: gửi một bản tin MQTT bình thường cho mỗi trạm mẫu (#30, cần make up trước)
	docker compose --profile core --profile app run --rm --no-deps cuu-tro-gia-lap python -m cuu_tro_workflow.gia_lap --mot-lan

gia-lap-vuot-nguong: ## Giả lập nước lên vượt ngưỡng nguy hiểm (một lần) → sự kiện cảnh báo trên NATS
	docker compose --profile core --profile app run --rm --no-deps cuu-tro-gia-lap python -m cuu_tro_workflow.gia_lap --mot-lan --kich-ban vuot-nguong

gia-lap-tran-lu: ## Phát lại trận lũ mẫu 48 giờ của 9 trạm miền Trung (#84) vào chuỗi đo + bản sao số NGSI-LD (vài giây)
	docker compose --profile core --profile app run --rm --no-deps cuu-tro-gia-lap python -m cuu_tro_workflow.gia_lap --kich-ban tran-lu --phat-lai

down:
	docker compose --profile '*' down

logs:
	docker compose logs -f --tail=100

ps:
	docker compose ps

migrate:       ## Áp migration SQL của apps/$$DXOS_APP/db/migrations (make up tự chạy; chạy lại không lỗi)
	docker compose --profile core run --rm --no-deps migrate migrate

seed:          ## Nạp dữ liệu giả apps/$$DXOS_APP/db/seed (chạy lại được, cần make up trước)
	docker compose --profile core run --rm --no-deps migrate seed

test-db:       ## Kiểm thử ràng buộc schema ứng dụng (apps/$$DXOS_APP/db/tests, ROLLBACK sau khi chạy)
	docker compose --profile core run --rm --no-deps migrate test

test-py:       ## pytest backend apps/$$DXOS_APP/workflow (cần uv: https://docs.astral.sh/uv/)
	cd apps/$${DXOS_APP:-cuu-tro}/workflow && uv run --frozen pytest -q

license:       ## Thêm header SPDX cho file mới
	bash scripts/add-license-header.sh

lint:          ## shellcheck + yamllint (cần cài sẵn 2 công cụ; CI chạy như nhau)
	bash scripts/lint.sh all

check:         ## Kiểm tra trước khi nộp: license + compose hợp lệ
	bash scripts/check-license.sh
	docker compose --env-file $(ENV_FILE) --profile '*' config --quiet && echo "OK: docker-compose.yml hợp lệ (mọi profile, $(ENV_FILE))"
