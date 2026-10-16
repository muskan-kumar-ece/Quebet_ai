import asyncio
from logging.config import fileConfig
from alembic import context
from sqlalchemy import Column, MetaData, PrimaryKeyConstraint, String, Table, pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config, create_async_engine
import alembic.ddl.impl as alembic_impl
from app.core.config import settings
from app.models.db.base import Base

# Ensure alembic_version table can store descriptive revision IDs longer than 32 characters
def _custom_version_table_impl(
    self,
    *,
    version_table: str,
    version_table_schema=None,
    version_table_pk: bool = True,
    **kw,
) -> Table:
    vt = Table(
        version_table,
        MetaData(),
        Column("version_num", String(128), nullable=False),
        schema=version_table_schema,
    )
    if version_table_pk:
        vt.append_constraint(
            PrimaryKeyConstraint(
                "version_num", name=f"{version_table}_pkc"
            )
        )
    return vt

alembic_impl.DefaultImpl.version_table_impl = _custom_version_table_impl

# Alembic Config object
config = context.config

# Interpret config file for logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Overwrite sqlalchemy.url with application settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connect_args = {}
    if "postgresql" in settings.DATABASE_URL:
        connect_args["prepared_statement_cache_size"] = 0
        connect_args["statement_cache_size"] = 0

    connectable = create_async_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
