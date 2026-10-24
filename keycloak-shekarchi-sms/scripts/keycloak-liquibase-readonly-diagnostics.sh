#!/usr/bin/env bash
# Read-only incident diagnostics for avg_keycloak / avg_keycloak_db.
# This script never starts, stops, restarts, or modifies containers or databases.
set -euo pipefail

kc=avg_keycloak
pg=avg_keycloak_db

echo '== Keycloak container =='
docker inspect "$kc" --format 'Status={{.State.Status}} RestartCount={{.RestartCount}} ExitCode={{.State.ExitCode}} Image={{.Config.Image}} ImageID={{.Image}}'
docker inspect "$kc" --format 'Mounts={{range .Mounts}}{{.Type}}:{{.Name}}:{{.Destination}} {{end}}'
docker inspect "$kc" --format 'Networks={{json .NetworkSettings.Networks}}'
# Parse (but never print) the full JDBC URL; emit only its host and database.
docker inspect "$kc" --format '{{range .Config.Env}}{{println .}}{{end}}' | awk '
  /^KC_DB=/ { print "Keycloak DB type=" substr($0, 7) }
  /^KC_DB_URL=/ {
    url=$0; sub(/^KC_DB_URL=/, "", url)
    sub(/^jdbc:postgresql:\/\//, "", url)
    sub(/\?.*$/, "", url)
    sub(/^.*@/, "", url)
    print "Keycloak JDBC target=" url
  }
  /^KC_DB_URL_HOST=/ { print "Keycloak DB host=" substr($0, 16) }
  /^KC_DB_URL_DATABASE=/ { print "Keycloak DB database=" substr($0, 21) }
'

echo '== PostgreSQL container =='
docker inspect "$pg" --format 'Status={{.State.Status}} Health={{if .State.Health}}{{.State.Health.Status}}{{else}}N/A{{end}} Image={{.Config.Image}} ImageID={{.Image}}'
docker inspect "$pg" --format 'Mounts={{range .Mounts}}{{.Type}}:{{.Name}}:{{.Destination}} {{end}}'

# Read only the standard database/user settings. Never print or fetch a password.
db_name="$(docker exec "$pg" sh -c 'printf %s "${POSTGRES_DB:-}"')"
db_user="$(docker exec "$pg" sh -c 'printf %s "${POSTGRES_USER:-}"')"
if [[ -z "$db_name" || -z "$db_user" ]]; then
  echo 'Database name/user were not available through standard PostgreSQL container variables.'
  echo 'No environment dump was performed. Supply the database/user to the operator using the secure host procedure.'
  exit 2
fi
if [[ ! "$db_name" =~ ^[A-Za-z0-9_.$-]+$ || ! "$db_user" =~ ^[A-Za-z0-9_.$-]+$ ]]; then
  echo 'Database name/user contain unsupported characters; refusing to construct a psql command.'
  exit 2
fi
echo "Database name=$db_name user=$db_user (credentials redacted)"

echo '== PostgreSQL and Liquibase metadata (read-only transaction) =='
docker exec -i "$pg" psql -X -v ON_ERROR_STOP=1 -U "$db_user" -d "$db_name" <<'SQL'
BEGIN READ ONLY;
SELECT current_setting('server_version') AS postgres_version,
       current_database() AS database_name,
       current_user AS connected_user,
       current_schema() AS current_schema;

SELECT schemaname, tablename
FROM pg_tables
WHERE lower(tablename) IN ('databasechangelog', 'databasechangeloglock', 'offline_user_session', 'offline_client_session')
ORDER BY schemaname, tablename;

SELECT schemaname, tablename, indexname, indexdef
FROM pg_indexes
WHERE lower(indexname) LIKE '%offline%'
ORDER BY schemaname, tablename, indexname;

SELECT n.nspname AS schema_name, t.relname AS table_name,
       i.relname AS index_name, pg_get_indexdef(i.oid) AS definition
FROM pg_class i
JOIN pg_index x ON x.indexrelid = i.oid
JOIN pg_class t ON t.oid = x.indrelid
JOIN pg_namespace n ON n.oid = i.relnamespace
WHERE lower(i.relname) = 'idx_offline_uss_createdon';

SELECT table_schema, table_name
FROM information_schema.tables
WHERE lower(table_name) IN ('databasechangelog', 'databasechangeloglock')
ORDER BY table_schema, table_name;

SELECT EXISTS (
  SELECT 1 FROM information_schema.tables
  WHERE table_schema = 'public' AND lower(table_name) = 'databasechangelog'
) AS has_public_changelog \gset
\if :has_public_changelog
SELECT id, author, filename, dateexecuted, orderexecuted, exectype
FROM public.databasechangelog
WHERE id LIKE '%28265%'
   OR filename LIKE '%25.0.0%'
ORDER BY orderexecuted DESC;
SELECT count(*) AS changelog_rows, max(orderexecuted) AS max_orderexecuted
FROM public.databasechangelog;
SELECT id, author, filename, md5sum, dateexecuted, orderexecuted, exectype
FROM public.databasechangelog
WHERE id LIKE '%28265%'
ORDER BY orderexecuted;
\else
\echo 'No public.databasechangelog; use the schema inventory above to query the discovered schema.'
\endif

SELECT EXISTS (
  SELECT 1 FROM information_schema.tables
  WHERE table_schema = 'public' AND lower(table_name) = 'databasechangeloglock'
) AS has_public_changeloglock \gset
\if :has_public_changeloglock
SELECT * FROM public.databasechangeloglock;
\else
\echo 'No public.databasechangeloglock; use the schema inventory above to query the discovered schema.'
\endif

SELECT EXISTS (
  SELECT 1 FROM information_schema.tables
  WHERE table_schema = 'public' AND lower(table_name) = 'migration_model'
) AS has_migration_model \gset
\if :has_migration_model
SELECT id, version, update_time
FROM public.migration_model
ORDER BY update_time DESC
LIMIT 5;
\else
\echo 'No public.migration_model table found.'
\endif
ROLLBACK;
SQL

echo 'Diagnostics completed. No writes or container lifecycle actions were performed.'
