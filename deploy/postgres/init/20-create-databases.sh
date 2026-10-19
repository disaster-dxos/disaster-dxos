#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Chạy một lần khi volume PostgreSQL còn trống (docker-entrypoint-initdb.d).
# Tạo CSDL riêng cho Keycloak và bật PostGIS cho CSDL nghiệp vụ.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v kc_db="$KEYCLOAK_DB" -v kc_user="$KEYCLOAK_DB_USER" -v kc_pass="$KEYCLOAK_DB_PASSWORD" <<'SQL'
CREATE ROLE :"kc_user" LOGIN PASSWORD :'kc_pass';
CREATE DATABASE :"kc_db" OWNER :"kc_user";
CREATE EXTENSION IF NOT EXISTS postgis;
SQL
echo "init: đã tạo CSDL ${KEYCLOAK_DB} và bật PostGIS trong ${POSTGRES_DB}"
