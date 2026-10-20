# SPDX-License-Identifier: Apache-2.0
.PHONY: up up-bi down logs ps migrate seed test-db license check lint smoke bao-init bao-unseal bao-status

# Dùng .env nếu có, nếu không thì .env.example (để CI/máy sạch vẫn kiểm được compose)
ENV_FILE := $(if $(wildcard .env),.env,.env.example)

up:            ## Chạy lõi headless (profile core): OpenBao trước, init/unseal, rồi các dịch vụ còn lại (#11)
	docker compose --profile core up -d openbao
	bash scripts/openbao-init.sh
	docker compose --profile core up -d --build

bao-init:      ## Khởi tạo OpenBao + nạp bí mật, policy, AppRole (idempotent, cần OpenBao đang chạy)
	bash scripts/openbao-init.sh

bao-unseal:    ## Mở khóa OpenBao bằng key trong .data/openbao (khi tắt OPENBAO_DEV_AUTO_UNSEAL)
	bash scripts/openbao-init.sh unseal

bao-status:    ## Trạng thái seal của OpenBao
	docker compose exec openbao bao status

up-bi:         ## Grafana (tuần 4)
	docker compose --profile bi up -d --build

smoke:         ## Kiểm thử OpenBao, JWT, route gateway + WAF, Hasura/SeaweedFS/Temporal/NATS, ràng buộc DB ứng dụng (cần make up trước)
	bash scripts/smoke-openbao.sh
	bash scripts/smoke-jwt.sh
	bash scripts/smoke-gateway.sh
	bash scripts/smoke-core.sh
	docker compose --profile core run --rm --no-deps migrate test

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

license:       ## Thêm header SPDX cho file mới
	bash scripts/add-license-header.sh

lint:          ## shellcheck + yamllint (cần cài sẵn 2 công cụ; CI chạy như nhau)
	bash scripts/lint.sh all

check:         ## Kiểm tra trước khi nộp: license + compose hợp lệ
	bash scripts/check-license.sh
	docker compose --env-file $(ENV_FILE) --profile '*' config --quiet && echo "OK: docker-compose.yml hợp lệ (mọi profile, $(ENV_FILE))"
