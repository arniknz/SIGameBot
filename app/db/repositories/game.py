from __future__ import annotations

import datetime
import uuid

import game.models
import sqlalchemy
import sqlalchemy.ext.asyncio
import game.constants


class GameRepository:
    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession) -> None:
        self._session = session

    async def get_active_by_chat(
        self,
        chat_id: int,
    ) -> game.models.GameModel | None:
        statement = sqlalchemy.select(game.models.GameModel).where(
            game.models.GameModel.chat_id == chat_id,
            game.models.GameModel.status.in_(
                [
                    game.constants.GameStatus.WAITING,
                    game.constants.GameStatus.ACTIVE,
                ]
            ),
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def create(
        self,
        chat_id: int,
        host_id: int,
    ) -> game.models.GameModel:
        new_game = game.models.GameModel(chat_id=chat_id, host_id=host_id)
        self._session.add(new_game)
        await self._session.flush()
        return new_game

    async def get_hosted_by(
        self,
        user_id: int,
    ) -> list[game.models.GameModel]:
        statement = sqlalchemy.select(game.models.GameModel).where(
            game.models.GameModel.host_id == user_id,
            game.models.GameModel.status.in_(
                [
                    game.constants.GameStatus.WAITING,
                    game.constants.GameStatus.ACTIVE,
                ]
            ),
        )
        return list((await self._session.execute(statement)).scalars().all())

    async def is_host_anywhere(
        self,
        telegram_id: int,
    ) -> bool:
        statement = (
            sqlalchemy.select(sqlalchemy.func.count())
            .select_from(game.models.GameModel)
            .join(
                game.models.UserModel,
                game.models.GameModel.host_id == game.models.UserModel.id,
            )
            .where(
                game.models.UserModel.telegram_id == telegram_id,
                game.models.GameModel.status.in_(
                    [
                        game.constants.GameStatus.WAITING,
                        game.constants.GameStatus.ACTIVE,
                    ]
                ),
            )
        )
        return (await self._session.execute(statement)).scalar_one() > 0

    async def create_state(
        self,
        game_id: uuid.UUID,
        status: str,
    ) -> game.models.GameStateModel:
        game_state = game.models.GameStateModel(game_id=game_id, status=status)
        self._session.add(game_state)
        await self._session.flush()
        return game_state

    async def get_state(
        self,
        game_id: uuid.UUID,
    ) -> game.models.GameStateModel | None:
        statement = sqlalchemy.select(game.models.GameStateModel).where(
            game.models.GameStateModel.game_id == game_id,
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def claim_expired_timer(
        self,
    ) -> tuple[game.models.GameStateModel, int] | None:
        now = datetime.datetime.now(datetime.UTC)
        statement = (
            sqlalchemy.select(
                game.models.GameStateModel, game.models.GameModel.chat_id
            )
            .join(
                game.models.GameModel,
                game.models.GameStateModel.game_id == game.models.GameModel.id,
            )
            .where(
                game.models.GameStateModel.timer_ends_at.isnot(None),
                game.models.GameStateModel.timer_ends_at <= now,
                game.models.GameModel.status
                == game.constants.GameStatus.ACTIVE,
            )
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            return None
        game_state, chat_id = row
        game_state.timer_ends_at = None
        return game_state, chat_id

    async def scoreboard(
        self,
        game_id: uuid.UUID,
    ) -> list[tuple[str, int]]:
        statement = (
            sqlalchemy.select(
                game.models.UserModel.username,
                game.models.ParticipantModel.score,
            )
            .join(
                game.models.ParticipantModel,
                game.models.ParticipantModel.user_id
                == game.models.UserModel.id,
            )
            .where(
                game.models.ParticipantModel.game_id == game_id,
                game.models.ParticipantModel.role
                == game.constants.ParticipantRole.PLAYER,
            )
            .order_by(game.models.ParticipantModel.score.desc())
        )
        rows = (await self._session.execute(statement)).all()
        return [(username or "Unknown", score) for username, score in rows]

    async def current_player_username(
        self,
        active_game: game.models.GameModel,
    ) -> str:
        if not active_game.current_player_id:
            return "Unknown"
        statement = (
            sqlalchemy.select(game.models.UserModel.username)
            .join(
                game.models.ParticipantModel,
                game.models.ParticipantModel.user_id
                == game.models.UserModel.id,
            )
            .where(
                game.models.ParticipantModel.id == active_game.current_player_id
            )
        )
        row = (await self._session.execute(statement)).one_or_none()
        return row[0] if row else "Unknown"
