from __future__ import annotations

import uuid

import game.models
import sqlalchemy
import sqlalchemy.ext.asyncio
import game.constants


class ParticipantRepository:
    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        game_id: uuid.UUID,
        user_id: int,
        role: str = game.constants.ParticipantRole.PLAYER,
    ) -> game.models.ParticipantModel:
        participant = game.models.ParticipantModel(
            game_id=game_id,
            user_id=user_id,
            role=role,
        )
        self._session.add(participant)
        await self._session.flush()
        return participant

    async def get_by_telegram_id(
        self,
        game_id: uuid.UUID,
        telegram_id: int,
    ) -> game.models.ParticipantModel | None:
        statement = (
            sqlalchemy.select(game.models.ParticipantModel)
            .join(
                game.models.UserModel,
                game.models.ParticipantModel.user_id
                == game.models.UserModel.id,
            )
            .where(
                game.models.ParticipantModel.game_id == game_id,
                game.models.UserModel.telegram_id == telegram_id,
            )
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def get_active_players(
        self,
        game_id: uuid.UUID,
    ) -> list[game.models.ParticipantModel]:
        statement = sqlalchemy.select(game.models.ParticipantModel).where(
            game.models.ParticipantModel.game_id == game_id,
            game.models.ParticipantModel.role
            == game.constants.ParticipantRole.PLAYER,
            game.models.ParticipantModel.is_active.is_(True),
        )
        return list((await self._session.execute(statement)).scalars().all())

    async def get_player_usernames(
        self,
        game_id: uuid.UUID,
    ) -> list[str]:
        statement = (
            sqlalchemy.select(game.models.UserModel.username)
            .join(
                game.models.ParticipantModel,
                game.models.ParticipantModel.user_id
                == game.models.UserModel.id,
            )
            .where(
                game.models.ParticipantModel.game_id == game_id,
                game.models.ParticipantModel.role
                == game.constants.ParticipantRole.PLAYER,
                game.models.ParticipantModel.is_active.is_(True),
            )
        )
        rows = (await self._session.execute(statement)).all()
        return [username or "Unknown" for (username,) in rows]

    async def pick_random(
        self,
        game_id: uuid.UUID,
    ) -> game.models.ParticipantModel | None:
        statement = (
            sqlalchemy.select(game.models.ParticipantModel)
            .where(
                game.models.ParticipantModel.game_id == game_id,
                game.models.ParticipantModel.role
                == game.constants.ParticipantRole.PLAYER,
                game.models.ParticipantModel.is_active.is_(True),
            )
            .order_by(sqlalchemy.func.random())
            .limit(1)
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def get_active_player_by_id(
        self,
        game_id: uuid.UUID,
        participant_id: uuid.UUID,
    ) -> game.models.ParticipantModel | None:
        statement = sqlalchemy.select(game.models.ParticipantModel).where(
            game.models.ParticipantModel.game_id == game_id,
            game.models.ParticipantModel.id == participant_id,
            game.models.ParticipantModel.role
            == game.constants.ParticipantRole.PLAYER,
            game.models.ParticipantModel.is_active.is_(True),
        )
        return (await self._session.execute(statement)).scalar_one_or_none()
