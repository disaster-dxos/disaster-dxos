#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Tạo/đồng bộ role PostgreSQL riêng cho từng dịch vụ lõi (#11). Chạy mỗi lần `make up` trong
# container một lần postgres-roles, SAU khi postgres healthy; chạy lại bao nhiêu lần cũng được.
#   keycloak  CSDL ${KEYCLOAK_DB} (do init/20-create-databases.sh tạo lần đầu)
#   hasura    CSDL ${POSTGRES_DB}: sở hữu schema hdb_catalog (metadata), được tạo schema ứng dụng
#   temporal  sở hữu CSDL temporal, temporal_visibility (tạo ở đây; auto-setup chỉ tạo schema)
#   <schema>_app  role dịch vụ của ứng dụng Tầng 2 đang chọn (DXOS_APP cuu-tro → cuu_tro_app, #29).
#             Tạo ra KHÔNG có quyền gì trên schema ứng dụng: migration của ứng dụng tự GRANT đúng
#             bảng/cột backend của nó cần (vd apps/cuu-tro/db/migrations/0003). Lõi không biết bảng nào.
# Mật khẩu lấy từ OpenBao (bao-agent-postgres → env-from-files.sh), ALTER ROLE mỗi lần chạy nên
# đổi mật khẩu trong OpenBao rồi `make up` là PostgreSQL khớp theo. Không dịch vụ nào dùng superuser.
set -euo pipefail

export PGHOST=${PGHOST:-postgres} PGUSER=$POSTGRES_USER PGPASSWORD=$POSTGRES_PASSWORD
psql_db() { psql -v ON_ERROR_STOP=1 -q -X --dbname "$1" "${@:2}"; }

# sync_role <tên role> <mật khẩu> <thuộc tính>
sync_role() {
  psql_db postgres -v u="$1" -v p="$2" -v attrs="$3" <<'SQL'
SELECT format('CREATE ROLE %I', :'u') WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'u')
\gexec
SELECT format('ALTER ROLE %I WITH LOGIN NOSUPERUSER NOCREATEROLE %s PASSWORD %L', :'u', :'attrs', :'p')
\gexec
SQL
  echo "postgres-roles: role $1 đã đồng bộ"
}

sync_role "$KEYCLOAK_DB_USER" "$KEYCLOAK_DB_PASSWORD" NOCREATEDB
sync_role "$HASURA_DB_USER" "$HASURA_DB_PASSWORD" NOCREATEDB
sync_role "$TEMPORAL_DB_USER" "$TEMPORAL_DB_PASSWORD" NOCREATEDB
APP_DB_USER=${APP_DB_USER:-${DXOS_APP//-/_}_app}
sync_role "$APP_DB_USER" "$APP_DB_PASSWORD" "NOCREATEDB CONNECTION LIMIT ${APP_DB_CONNECTION_LIMIT:-10}"

# Hasura: quyền tối thiểu theo tài liệu Hasura ("Postgres permissions"), thêm quyền tạo schema
# để migration của ứng dụng (apps/<app>/) chạy bằng chính role hasura.
psql_db "$POSTGRES_DB" -v u="$HASURA_DB_USER" -v db="$POSTGRES_DB" <<'SQL'
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS hdb_catalog;
SELECT format('ALTER SCHEMA hdb_catalog OWNER TO %I', :'u')
\gexec
-- Bảng/hàm Hasura tạo trước khi có role riêng (chạy bằng superuser) chuyển cho role hasura
SELECT format('ALTER TABLE hdb_catalog.%I OWNER TO %I', tablename, :'u')
  FROM pg_tables WHERE schemaname = 'hdb_catalog' AND tableowner <> :'u'
\gexec
SELECT format('ALTER FUNCTION hdb_catalog.%I(%s) OWNER TO %I', p.proname, pg_get_function_identity_arguments(p.oid), :'u')
  FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
 WHERE n.nspname = 'hdb_catalog' AND pg_get_userbyid(p.proowner) <> :'u'
\gexec
SELECT format('GRANT CONNECT, CREATE, TEMPORARY ON DATABASE %I TO %I', :'db', :'u')
\gexec
SELECT format('GRANT USAGE, CREATE ON SCHEMA public TO %I', :'u')
\gexec
SELECT format('GRANT SELECT ON ALL TABLES IN SCHEMA information_schema, pg_catalog TO %I', :'u')
\gexec
SELECT format('GRANT SELECT ON public.spatial_ref_sys TO %I', :'u')
\gexec
SQL
echo "postgres-roles: quyền của $HASURA_DB_USER trên $POSTGRES_DB đã đồng bộ"

# Temporal: tạo sẵn 2 CSDL thuộc role temporal (auto-setup chạy với SKIP_DB_CREATE=true), nên
# role temporal không cần CREATEDB. CSDL có sẵn mà thuộc role khác thì chuyển chủ sở hữu CSDL.
for db in temporal temporal_visibility; do
  psql_db postgres -v db="$db" -v u="$TEMPORAL_DB_USER" <<'SQL'
SELECT format('CREATE DATABASE %I OWNER %I', :'db', :'u')
 WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'db')
\gexec
SELECT format('ALTER DATABASE %I OWNER TO %I', :'db', :'u')
\gexec
SQL
done
echo "postgres-roles: CSDL temporal, temporal_visibility thuộc $TEMPORAL_DB_USER"
echo "postgres-roles: xong"
