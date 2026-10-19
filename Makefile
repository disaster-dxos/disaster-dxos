# SPDX-License-Identifier: Apache-2.0
.PHONY: up up-next up-bi down logs ps seed license check lint smoke

# Dùng .env nếu có, nếu không thì .env.example (để CI/máy sạch vẫn kiểm được compose)
ENV_FILE := $(if $(wildcard .env),.env,.env.example)

up:            ## Chạy lõi headless (profile core)
	docker compose --profile core up -d --build

up-next:       ## Lõi + dịch vụ tuần 2 (Hasura, SeaweedFS, Temporal, NATS, OpenBao)
	docker compose --profile core-next up -d --build

up-bi:         ## Grafana (tuần 4)
	docker compose --profile bi up -d --build

smoke:         ## Kiểm thử JWT qua APISIX (cần make up trước)
	bash scripts/smoke-jwt.sh

down:
	docker compose --profile '*' down

logs:
	docker compose logs -f --tail=100

ps:
	docker compose ps

seed:          ## Bơm dữ liệu mẫu — điền lệnh khi có script (npm run seed / python seed_data.py)
	@echo "TODO: Sprint 2 — xem db/seed/README.md"

license:       ## Thêm header SPDX cho file mới
	bash scripts/add-license-header.sh

lint:          ## shellcheck + yamllint (cần cài sẵn 2 công cụ; CI chạy như nhau)
	bash scripts/lint.sh all

check:         ## Kiểm tra trước khi nộp: license + compose hợp lệ
	bash scripts/check-license.sh
	docker compose --env-file $(ENV_FILE) --profile '*' config --quiet && echo "OK: docker-compose.yml hợp lệ (mọi profile, $(ENV_FILE))"
