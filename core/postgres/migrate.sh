#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Chạy migration (và seed) SQL của ứng dụng Tầng 2 đang chọn (#25). Lõi không biết bảng nào của
# ứng dụng: chỉ biết quy ước thư mục apps/${DXOS_APP}/db/ (mount vào ${APP_DB_DIR}):
#   migrations/NNNN_<tên>.sql   chạy theo thứ tự tên, mỗi file đúng một lần, mỗi file một transaction
#   seed/NNNN_<tên>.sql         dữ liệu giả, chạy lại được (idempotent), chỉ khi gọi "seed"
#   tests/NNNN_<tên>.sql        kiểm thử ràng buộc, chạy trong transaction rồi ROLLBACK ("test")
# Quy ước tên: schema = DXOS_APP đổi "-" thành "_" (cuu-tro → cuu_tro), chủ sở hữu là role NOLOGIN
# <schema>_owner (không đăng nhập được, không CREATEDB/CREATEROLE, chỉ sở hữu schema của mình).
# Script đăng nhập bằng superuser chỉ để tạo role/schema rồi SET ROLE <schema>_owner trước mỗi file,
# nên mọi đối tượng thuộc role ứng dụng. Role API (hasura) chỉ được SELECT/INSERT/UPDATE/DELETE,
# không có quyền DDL. Lịch sử áp dụng nằm ở dxos_meta.app_migrations (ngoài schema ứng dụng),
# có checksum: sửa một migration đã chạy thì báo lỗi, phải thêm file migration mới.
# Dùng: migrate.sh [migrate|seed|test]   (docker compose run --rm migrate seed)
set -euo pipefail

MODE=${1:-migrate}
DIR=${APP_DB_DIR:-/opt/dxos/app-db}
APP=${DXOS_APP:?Thiếu DXOS_APP}
SCHEMA=${APP//-/_}
OWNER=${SCHEMA}_owner
API_ROLE=${HASURA_DB_USER:-hasura}

export PGHOST=${PGHOST:-postgres} PGUSER=$POSTGRES_USER PGPASSWORD=$POSTGRES_PASSWORD PGDATABASE=$POSTGRES_DB
# Ẩn NOTICE "already exists, skipping" khi chạy lại
export PGOPTIONS="${PGOPTIONS:-} -c client_min_messages=warning"
psql_q() { psql -v ON_ERROR_STOP=1 -q -X "$@"; }

if [ ! -d "$DIR/migrations" ]; then
  echo "migrate: apps/$APP/db/migrations không có, bỏ qua"
  exit 0
fi

# 1. Role chủ sở hữu, schema riêng, bảng lịch sử (chạy lại không lỗi)
psql_q -v s="$SCHEMA" -v o="$OWNER" -v api="$API_ROLE" <<'SQL'
SELECT format('CREATE ROLE %I NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE', :'o')
 WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'o')
\gexec
SELECT format('CREATE SCHEMA IF NOT EXISTS %I AUTHORIZATION %I', :'s', :'o')
\gexec
SELECT format('ALTER SCHEMA %I OWNER TO %I', :'s', :'o')
\gexec
SELECT format('REVOKE ALL ON SCHEMA %I FROM PUBLIC', :'s')
\gexec
CREATE SCHEMA IF NOT EXISTS dxos_meta;
REVOKE ALL ON SCHEMA dxos_meta FROM PUBLIC;
CREATE TABLE IF NOT EXISTS dxos_meta.app_migrations (
  app        text        NOT NULL,
  version    text        NOT NULL,
  checksum   text        NOT NULL,
  applied_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (app, version)
);
SQL

# run_file <file> [ghi lịch sử version checksum]: một transaction, quyền của role ứng dụng
run_file() {
  local f=$1 version=${2:-} sum=${3:-}
  {
    printf 'SET ROLE %s;\nSET search_path = %s, public;\n' "\"$OWNER\"" "\"$SCHEMA\""
    printf '\\i %s\n' "$f"
    if [ -n "$version" ]; then
      printf "RESET ROLE;\nINSERT INTO dxos_meta.app_migrations (app, version, checksum) VALUES (:'app', :'version', :'sum');\n"
    fi
  } | psql_q -1 -v app_schema="$SCHEMA" -v app="$APP" -v version="$version" -v sum="$sum" -f -
}

case "$MODE" in
  migrate)
    applied=0
    for f in "$DIR"/migrations/[0-9]*.sql; do
      [ -e "$f" ] || continue
      version=$(basename "$f" .sql)
      sum=$(sha256sum "$f" | cut -d' ' -f1)
      case "$version" in
        *[!0-9A-Za-z_-]*) echo "migrate: LỖI tên file $version chỉ được dùng chữ, số, _ và -" >&2; exit 1 ;;
      esac
      # psql -c không thay biến :'x', nên truyền câu lệnh qua stdin
      old=$(printf "SELECT checksum FROM dxos_meta.app_migrations WHERE app = :'app' AND version = :'v';\n" \
        | psql_q -tA -v app="$APP" -v v="$version" -f -)
      if [ -n "$old" ]; then
        if [ "$old" != "$sum" ]; then
          echo "migrate: LỖI $version đã chạy nhưng nội dung đã đổi (checksum khác). Không sửa migration cũ, thêm file mới." >&2
          exit 1
        fi
        continue
      fi
      run_file "$f" "$version" "$sum"
      echo "migrate: đã áp dụng $version"
      applied=$((applied + 1))
    done
    echo "migrate: $APP → schema $SCHEMA, $applied migration mới"
    ;;
  seed)
    for f in "$DIR"/seed/[0-9]*.sql; do
      [ -e "$f" ] || continue
      run_file "$f"
      echo "seed: đã nạp $(basename "$f")"
    done
    ;;
  test)
    for f in "$DIR"/tests/[0-9]*.sql; do
      [ -e "$f" ] || continue
      {
        printf 'BEGIN;\nSET ROLE %s;\nSET search_path = %s, public;\n\\i %s\nROLLBACK;\n' "\"$OWNER\"" "\"$SCHEMA\"" "$f"
      } | psql -v ON_ERROR_STOP=1 -q -X -f -
    done
    exit 0
    ;;
  *)
    echo "Dùng: migrate.sh [migrate|seed|test]" >&2
    exit 2
    ;;
esac

# 2. Quyền tối thiểu cho role API trên schema ứng dụng: chỉ DML, không DDL, không TRUNCATE.
#    Chạy sau mỗi lần migrate/seed để bảng mới cũng được cấp. Việc chọn bảng/cột nào lộ ra
#    GraphQL theo vai trò là của Hasura metadata (#26).
psql_q -v s="$SCHEMA" -v o="$OWNER" -v api="$API_ROLE" <<'SQL'
SELECT format('GRANT USAGE ON SCHEMA %I TO %I', :'s', :'api')
\gexec
SELECT format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA %I TO %I', :'s', :'api')
\gexec
SELECT format('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA %I TO %I', :'s', :'api')
\gexec
SELECT format('GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA %I TO %I', :'s', :'api')
\gexec
SQL
echo "migrate: role $API_ROLE có quyền DML trên schema $SCHEMA"
