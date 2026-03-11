from __future__ import annotations

import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))

import alembic.context
import sqlalchemy.ext.asyncio
import sqlalchemy.pool

import config
import game.models
from game.models.base import Base

cfg = config.Config.from_env()
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    alembic.context.configure(
        url=cfg.db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with alembic.context.begin_transaction():
        alembic.context.run_migrations()


def do_run_migrations(connection):
    alembic.context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )
    with alembic.context.begin_transaction():
        alembic.context.run_migrations()


async def run_migrations_online() -> None:
    connectable = sqlalchemy.ext.asyncio.create_async_engine(
        cfg.db_url, poolclass=sqlalchemy.pool.NullPool
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if alembic.context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
