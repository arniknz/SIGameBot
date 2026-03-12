from __future__ import annotations

import datetime
import uuid

import game.constants
import game.models
import sqlalchemy
import sqlalchemy.ext.asyncio
import sqlalchemy.orm


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

    async def get_hosted_with_player_counts(
        self,
        user_id: int,
    ) -> list[tuple[game.models.GameModel, int]]:
        count_subq = (
            sqlalchemy.select(
                game.models.ParticipantModel.game_id,
                sqlalchemy.func.count(game.models.ParticipantModel.id).label(
                    "cnt"
                ),
            )
            .where(
                game.models.ParticipantModel.is_active.is_(True),
                game.models.ParticipantModel.role
                == game.constants.ParticipantRole.PLAYER,
            )
            .group_by(game.models.ParticipantModel.game_id)
            .subquery()
        )
        statement = (
            sqlalchemy.select(
                game.models.GameModel,
                sqlalchemy.func.coalesce(count_subq.c.cnt, 0),
            )
            .outerjoin(
                count_subq,
                game.models.GameModel.id == count_subq.c.game_id,
            )
            .where(
                game.models.GameModel.host_id == user_id,
                game.models.GameModel.status.in_(
                    [
                        game.constants.GameStatus.WAITING,
                        game.constants.GameStatus.ACTIVE,
                    ]
                ),
            )
            .order_by(game.models.GameModel.created_at.desc())
        )
        rows = (await self._session.execute(statement)).all()
        return [
            (game_model, int(player_count)) for game_model, player_count in rows
        ]

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
        status: game.constants.GamePhase,
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

    async def get_state_for_update(
        self,
        game_id: uuid.UUID,
    ) -> game.models.GameStateModel | None:
        statement = (
            sqlalchemy.select(game.models.GameStateModel)
            .where(
                game.models.GameStateModel.game_id == game_id,
            )
            .with_for_update()
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def claim_expired_timers(
        self,
    ) -> list[tuple[game.models.GameStateModel, int]]:
        now = datetime.datetime.now(datetime.UTC)
        statement = (
            sqlalchemy.select(game.models.GameStateModel)
            .join(
                game.models.GameModel,
                game.models.GameStateModel.game_id == game.models.GameModel.id,
            )
            .options(
                sqlalchemy.orm.contains_eager(game.models.GameStateModel.game)
            )
            .where(
                game.models.GameStateModel.timer_ends_at.isnot(None),
                game.models.GameStateModel.timer_ends_at <= now,
                game.models.GameModel.status
                == game.constants.GameStatus.ACTIVE,
            )
            .with_for_update(skip_locked=True)
        )
        rows = (await self._session.execute(statement)).scalars().all()
        results: list[tuple[game.models.GameStateModel, int]] = []
        for game_state in rows:
            game_state.timer_ends_at = None
            results.append((game_state, game_state.game.chat_id))
        return results

    async def recover_stale_games(
        self,
    ) -> list[tuple[game.models.GameStateModel, int]]:
        threshold = datetime.datetime.now(datetime.UTC) - datetime.timedelta(
            seconds=120
        )
        statement = (
            sqlalchemy.select(game.models.GameStateModel)
            .join(
                game.models.GameModel,
                game.models.GameStateModel.game_id == game.models.GameModel.id,
            )
            .options(
                sqlalchemy.orm.contains_eager(game.models.GameStateModel.game)
            )
            .where(
                game.models.GameModel.status
                == game.constants.GameStatus.ACTIVE,
                game.models.GameStateModel.status.in_(
                    [
                        game.constants.GamePhase.CHOOSING_QUESTION,
                        game.constants.GamePhase.WAITING_BUZZER,
                        game.constants.GamePhase.WAITING_ANSWER,
                    ]
                ),
                game.models.GameStateModel.timer_ends_at.is_(None),
                game.models.GameStateModel.updated_at <= threshold,
            )
            .with_for_update(skip_locked=True)
        )
        rows = (await self._session.execute(statement)).scalars().all()
        return [(game_state, game_state.game.chat_id) for game_state in rows]

    async def scoreboard(
        self,
        game_id: uuid.UUID,
        *,
        active_only: bool = True,
    ) -> list[tuple[str, int]]:
        conditions = [
            game.models.ParticipantModel.game_id == game_id,
            game.models.ParticipantModel.role
            == game.constants.ParticipantRole.PLAYER,
        ]
        if active_only:
            conditions.append(
                game.models.ParticipantModel.is_active.is_(True),
            )
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
            .where(*conditions)
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
                game.models.ParticipantModel.id
                == active_game.current_player_id,
                game.models.ParticipantModel.is_active.is_(True),
            )
        )
        row = (await self._session.execute(statement)).one_or_none()
        return row[0] if row else "Unknown"
