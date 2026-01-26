from __future__ import annotations

import asyncio
from logging.config import fileConfig
from typing import Any

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from src.app.models.base import Base
from src.app.models.etl_pipeline import EtlPipeline  # noqa: F401
from src.app.models.etl_pipeline_task import EtlPipelineTask  # noqa: F401
from src.app.models.etl_run import EtlRun  # noqa: F401
from src.app.models.etl_state import EtlState  # noqa: F401
from src.config import get_settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

SETTINGS = get_settings()


def include_object(object_: Any, name: str, type_: str, reflected: bool, compare_to: Any) -> bool:
    if type_ == "table":
        schema = getattr(object_, "schema", None)
        return schema == "etl"
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=SETTINGS.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table_schema="etl",
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        version_table_schema="etl",
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = SETTINGS.database_url

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
