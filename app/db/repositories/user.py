from __future__ import annotations

import game.models
import sqlalchemy
import sqlalchemy.dialects.postgresql
import sqlalchemy.ext.asyncio


class UserRepository:
    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession) -> None:
        self._session = session

    async def get_or_create(
        self,
        telegram_id: int,
        username: str,
    ) -> game.models.UserModel:
        statement = (
            sqlalchemy.dialects.postgresql.insert(game.models.UserModel)
            .values(telegram_id=telegram_id, username=username)
            .on_conflict_do_update(
                index_elements=["telegram_id"],
                set_={"username": username},
            )
            .returning(game.models.UserModel)
        )
        result = await self._session.execute(statement)
        return result.scalar_one()

    async def get_by_telegram_id(
        self,
        telegram_id: int,
    ) -> game.models.UserModel | None:
        statement = sqlalchemy.select(game.models.UserModel).where(
            game.models.UserModel.telegram_id == telegram_id,
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def get_by_id(
        self,
        user_id: int,
    ) -> game.models.UserModel | None:
        statement = sqlalchemy.select(game.models.UserModel).where(
            game.models.UserModel.id == user_id,
        )
        return (await self._session.execute(statement)).scalar_one_or_none()
