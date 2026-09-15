import os
from logging.config import fileConfig

from acex.database import Connection
from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support

target_metadata = SQLModel.metadata


def resolve_url() -> str:
    """Database URL for CLI runs, in order of precedence:

    1. `alembic -x url=postgresql://...` on the command line.
    2. The same DB_* environment variables the app itself reads (see
       `acex.__main__.create_app`), so the CLI hits the same database as the
       running backend without anyone editing alembic.ini. The default is
       localhost, which is what you want on a dev machine; docker-compose sets
       DB_HOST=postgres so it resolves to the service there.
    3. alembic.ini's `sqlalchemy.url`, as a last resort.

    App-initiated migrations never reach this function: they pass a live engine
    via `config.attributes["connection"]` (see `DatabaseManager.upgrade()`).
    """
    if url := context.get_x_argument(as_dictionary=True).get("url"):
        return url

    try:
        return Connection(
            backend="postgresql",
            dbname=os.getenv("DB_NAME", "ace"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
        ).url
    except ValueError:
        return config.get_main_option("sqlalchemy.url")


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = resolve_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    If the caller passed a live engine/connection in via
    `config.attributes["connection"]` (see DatabaseManager.upgrade()), reuse
    it so migrations run through the application's own DB connection instead
    of a URL parsed from alembic.ini. Falls back to alembic.ini for CLI use.

    """
    connectable = config.attributes.get("connection")

    if connectable is None:
        connectable = engine_from_config(
            {**config.get_section(config.config_ini_section, {}), "sqlalchemy.url": resolve_url()},
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
