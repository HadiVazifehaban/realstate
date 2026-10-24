"""Alembic environment, wired to SQLModel metadata and app settings.

Runs migrations with a *sync* psycopg3 connection (the same driver the app uses
asynchronously), and ensures the PostGIS extension exists before creating tables
that rely on geometry columns / GiST indexes.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool, text

# Make the project importable when Alembic is invoked from the CLI.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.models import *  # noqa: E402,F401,F403  (registers all tables)
from sqlmodel import SQLModel  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the runtime database URL (async driver is valid for sync usage too).
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = SQLModel.metadata


def _include_object(object_, name, type_, reflected, compare_to):  # noqa: ANN001
    """Restrict autogenerate to AVG-owned tables.

    PostGIS installs dozens of ``tiger``/``topology`` support tables which must
    never be dropped by our migrations, so we whitelist our own metadata tables
    (and their indexes/constraints) and ignore everything else.
    """
    known = set(target_metadata.tables)
    if type_ == "table":
        return name in known

    # Indexes / constraints / columns: only include when their parent table is ours.
    table = getattr(object_, "table", None)
    table_name = getattr(table, "name", None)
    if table_name is not None:
        return table_name in known
    return True


def run_migrations_offline() -> None:
    """Render SQL to stdout without a DB connection (``alembic upgrade --sql``)."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # PostGIS must exist before geometry columns are created.
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=_include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
