"""
Alembic environment script.

Key customisations
------------------
* The SQLAlchemy URL is loaded from app.core.config (which reads .env) so
  credentials are never hard-coded here.
* app.db.models is imported to register all ORM models with Base.metadata,
  enabling --autogenerate to diff the schema correctly.
"""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make the backend package importable when running `alembic` from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings  # noqa: E402
from app.db import models  # noqa: F401, E402 — registers models with metadata
from app.db.database import Base  # noqa: E402

# Alembic Config object
alembic_cfg = context.config

# Override the URL placeholder in alembic.ini with the real URL from .env
alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Set up Python logging from the alembic.ini [loggers] section
if alembic_cfg.config_file_name is not None:
    fileConfig(alembic_cfg.config_file_name)

# The metadata that Alembic compares against the live database schema
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations without a live database connection.
    Useful for generating raw SQL scripts.
    """
    url = alembic_cfg.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations with a live database connection (default).
    """
    connectable = engine_from_config(
        alembic_cfg.get_section(alembic_cfg.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
