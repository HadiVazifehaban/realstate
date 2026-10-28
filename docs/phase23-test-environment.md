# Phase 2.3 disposable PostgreSQL test environment

This environment is deliberately opt-in. Do not run the Compose commands until
the operator has approved creating the isolated container, named volume, and
internal network.

## Before startup

Create a random test-only password without printing or storing it in the repo,
then create `/tmp/phase23-test.env` with mode `0600`. It must contain:

```dotenv
PHASE23_TEST_DB_PASSWORD=<unique-random-test-password>
DATABASE_URL=postgresql+asyncpg://phase23_test:<URL-encoded-password>@test-db:5432/phase23_test
PHASE23_TEST_DATABASE_URL=postgresql+asyncpg://phase23_test:<URL-encoded-password>@test-db:5432/phase23_test
```

Use the same password in the Compose variable and URL, URL-encoding reserved
characters. This file is passed explicitly; the application `.env` is not used.

## Start and verify

```sh
cd /home/app/real
chmod 600 /tmp/phase23-test.env
docker compose -p shekarchi-phase23-test -f docker-compose.test.yml \
  --env-file /tmp/phase23-test.env up -d --wait
```

The test DB is reachable only by Compose service DNS on its internal network;
there is no published host port, no operational network attachment, and its
named volume is `phase23_test_pgdata`.

The backend test dependencies must be available in the runner attached to that
network. If using a one-off container, build it from the repository Dockerfile
and attach only `phase23_test_net`; do not attach the runner to the operational
Compose network.

Inside the test container, verify identity without displaying credentials:

```sh
docker compose -p shekarchi-phase23-test -f docker-compose.test.yml \
  --env-file /tmp/phase23-test.env exec -T test-db \
  psql -U phase23_test -d phase23_test -Atc \
  'SELECT current_database(), inet_server_port()'
```

Expected identity is `phase23_test` and PostgreSQL's internal port `5432`.
Tests from a host process cannot resolve `test-db` unless run in that network;
therefore run the PostgreSQL integration test in a one-off test runner attached
only to `phase23_test_net`, supplying the same environment file explicitly.
Do not publish port 5432 to make host connectivity work.

## Remove

After the test process has exited and its audit output is saved:

```sh
docker compose -p shekarchi-phase23-test -f docker-compose.test.yml \
  --env-file /tmp/phase23-test.env down --volumes --remove-orphans
rm -f /tmp/phase23-test.env
```

`down --volumes` deletes the disposable named data volume. Confirm the exact
Compose project and volume names before running it; never substitute the
operational Compose file or project name.

## Test guard

`tests/test_phase2_ingestion.py` only accepts the explicit test URL when the
operator sets `PHASE23_TEST_DB_ISOLATED=CONFIRMED_BY_OPERATOR` in the process
environment, and host, port, database, and username exactly match the isolated
service. Do not put this marker in the env-file: it is a separate affirmative
operator action after identity verification. Without the marker, the suite uses
its local SQLite fallback. The PostgreSQL concurrency integration case remains
skipped until the marker and explicit URL are supplied.