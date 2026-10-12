#!/bin/sh
set -eu

case "$PG_ADMIN_USER" in *[!a-zA-Z0-9_]*|'') exit 64;; esac
case "$APP_DB_USER" in *[!a-zA-Z0-9_]*|'') exit 64;; esac
case "$APP_DB_NAME" in *[!a-zA-Z0-9_]*|'') exit 64;; esac
[ "${#PG_ADMIN_USER}" -le 63 ] || exit 64
[ "${#APP_DB_USER}" -le 63 ] || exit 64
[ "${#APP_DB_NAME}" -le 63 ] || exit 64
[ "$PG_ADMIN_USER" != "$APP_DB_USER" ] || exit 64
[ "$PG_ADMIN_PASSWORD" != "$APP_DB_PASSWORD" ] || exit 64
[ "${#PG_ADMIN_PASSWORD}" -ge 24 ] || exit 64
[ "${#APP_DB_PASSWORD}" -ge 24 ] || exit 64

export PGUSER="$PG_ADMIN_USER" PGPASSWORD="$PG_ADMIN_PASSWORD"

psql --set=ON_ERROR_STOP=1 --dbname postgres \
  --set=app_user="$APP_DB_USER" \
  --set=app_password="$APP_DB_PASSWORD" \
  --set=app_database="$APP_DB_NAME" <<'SQL'
SELECT format('CREATE ROLE %I', :'app_user')
  WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'app_user') \gexec
SELECT format(
  'ALTER ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS',
  :'app_user', :'app_password'
) \gexec
SELECT format('CREATE DATABASE %I OWNER %I', :'app_database', :'app_user')
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'app_database') \gexec
SELECT format('ALTER DATABASE %I OWNER TO %I', :'app_database', :'app_user') \gexec
SQL

psql --set=ON_ERROR_STOP=1 --dbname "$APP_DB_NAME" --set=app_user="$APP_DB_USER" <<'SQL'
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO :"app_user";
SQL
