"""Alembic environment — configures DB connections for online and offline migrations."""

import os
import sys
from logging.config import fileConfig
from urllib.parse import quote_plus

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# Load .env from the project root so migrations work without the full app settings.
# Only POSTGRES_* variables are needed here — no API keys required.
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(_project_root, ".env"))

# Make the backend app importable (needed for target_metadata / autogenerate)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import Base  # noqa: E402
from app.models import user  # noqa: F401 — registers User with Base.metadata for autogenerate
from app.models import chat  # noqa: F401 — registers ChatThread, ChatMessage with Base.metadata
from app.models import document  # noqa: F401 — registers Document with Base.metadata
from app.models import refresh_token  # noqa: F401 — registers RefreshToken with Base.metadata
from app.models import data_source  # noqa: F401 — registers DataSource with Base.metadata
from app.models import data_file  # noqa: F401 — registers DataFile, DataFileSchema with Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Tables managed entirely with raw SQL (e.g. pgvector types the ORM can't describe).
# Excluding them prevents autogenerate from emitting spurious drop/recreate statements.
_AUTOGENERATE_EXCLUDE_TABLES = {"document_chunks"}


def include_object(object, name, type_, reflected, compare_to):  # noqa: A002
    if type_ == "table" and name in _AUTOGENERATE_EXCLUDE_TABLES:
        return False
    return True


def get_url() -> str:
    pg_user = quote_plus(os.environ["POSTGRES_USER"])
    pg_password = quote_plus(os.environ["POSTGRES_PASSWORD"])
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ["POSTGRES_DB"]
    return f"postgresql+psycopg2://{pg_user}:{pg_password}@{host}:{port}/{db}"


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        url=get_url(),
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
