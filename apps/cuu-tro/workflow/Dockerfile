# SPDX-License-Identifier: Apache-2.0
# Image chung cho cuu-tro-worker và cuu-tro-api (#29); lệnh chạy đặt trong apps/cuu-tro/compose.yaml.
# Phụ thuộc cài từ requirements.txt (sinh từ uv.lock, có hash): pip từ chối gói không khớp hash.
FROM python:3.12.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --require-hashes --only-binary=:all: -r requirements.txt

COPY cuu_tro_workflow/ cuu_tro_workflow/
# Bọc lệnh bằng env-from-files.sh (mount từ core/openbao) cần bash: có sẵn trong image slim
RUN useradd --system --uid 10001 --no-create-home app
USER 10001
