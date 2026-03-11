from __future__ import annotations

import logging

import config
import sqlalchemy
import sqlalchemy.ext.asyncio

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, cfg: config.Config):
        self._engine = sqlalchemy.ext.asyncio.create_async_engine(
            cfg.db_url,
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=1800,
            connect_args={"ssl": False},
        )
        self._session_factory = sqlalchemy.ext.asyncio.async_sessionmaker(
            self._engine,
            expire_on_commit=False,
        )

    @property
    def session_factory(self) -> sqlalchemy.ext.asyncio.async_sessionmaker:
        return self._session_factory

    async def connect(self) -> None:
        logger.info("Connecting to database")
        async with self._engine.begin() as conn:
            await conn.execute(sqlalchemy.text("SELECT 1"))
        logger.info("Database connection established")

    async def disconnect(self) -> None:
        logger.info("Closing database connections")
        await self._engine.dispose()
        logger.info("Database connections closed")
