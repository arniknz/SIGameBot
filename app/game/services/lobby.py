from __future__ import annotations

import datetime
import logging

import db.repositories.game
import db.repositories.participant
import db.repositories.user
import game.models
import game.schemas
import sqlalchemy.ext.asyncio
import game.constants

logger = logging.getLogger(__name__)


def _result(
    chat_id: int, view: str, **payload: object
) -> game.schemas.ServiceResponse:
    return game.schemas.ServiceResponse(
        chat_id=chat_id,
        view=view,
        payload=dict(payload),
    )


class LobbyService:
    def __init__(
        self, session_factory: sqlalchemy.ext.asyncio.async_sessionmaker
    ) -> None:
        self._session_factory = session_factory

    async def handle_start(
        self,
        chat_id: int,
        telegram_id: int,
        username: str,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            game_repo = db.repositories.game.GameRepository(session)
            user_repo = db.repositories.user.UserRepository(session)
            participant_repo = db.repositories.participant.ParticipantRepository(
                session
            )

            active_game = await game_repo.get_active_by_chat(chat_id)
            if active_game is not None:
                return [_result(chat_id, "game_already_running")]

            user = await user_repo.get_or_create(telegram_id, username)
            new_game = await game_repo.create(chat_id, host_id=user.id)
            await participant_repo.add(
                new_game.id, user.id, game.constants.ParticipantRole.PLAYER
            )
            await game_repo.create_state(
                new_game.id, game.constants.GamePhase.LOBBY
            )

            logger.info(
                "Game %s created in chat %s by %s",
                new_game.id,
                chat_id,
                username,
            )

            return [_result(chat_id, "game_created", username=username)]

    async def handle_join(
        self,
        chat_id: int,
        telegram_id: int,
        username: str,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            game_repo = db.repositories.game.GameRepository(session)
            user_repo = db.repositories.user.UserRepository(session)
            participant_repo = db.repositories.participant.ParticipantRepository(
                session
            )

            active_game = await game_repo.get_active_by_chat(chat_id)
            if active_game is None:
                return [_result(chat_id, "no_active_game")]

            if active_game.status != game.constants.GameStatus.WAITING:
                return [_result(chat_id, "game_already_started")]

            user = await user_repo.get_or_create(telegram_id, username)
            existing = await participant_repo.get_by_telegram_id(
                active_game.id, telegram_id
            )
            if existing is not None:
                if existing.is_active:
                    return [_result(chat_id, "already_in_game", username=username)]
                existing.is_active = True
                existing.role = game.constants.ParticipantRole.PLAYER
                logger.info("%s rejoined game %s", username, active_game.id)
                return [_result(chat_id, "player_rejoined", username=username)]

            await participant_repo.add(
                active_game.id,
                user.id,
                game.constants.ParticipantRole.PLAYER,
            )
            player_names = await participant_repo.get_player_usernames(
                active_game.id
            )

            logger.info("%s joined game %s", username, active_game.id)

            return [
                _result(
                    chat_id,
                    "player_joined",
                    username=username,
                    player_names=player_names,
                )
            ]

    async def handle_spectate(
        self,
        chat_id: int,
        telegram_id: int,
        username: str,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            game_repo = db.repositories.game.GameRepository(session)
            user_repo = db.repositories.user.UserRepository(session)
            participant_repo = db.repositories.participant.ParticipantRepository(
                session
            )

            active_game = await game_repo.get_active_by_chat(chat_id)
            if active_game is None:
                return [_result(chat_id, "no_active_game")]

            user = await user_repo.get_or_create(telegram_id, username)
            existing = await participant_repo.get_by_telegram_id(
                active_game.id, telegram_id
            )
            if existing is not None:
                if (
                    existing.role == game.constants.ParticipantRole.SPECTATOR
                    and existing.is_active
                ):
                    return [
                        _result(chat_id, "already_spectating", username=username)
                    ]
                existing.role = game.constants.ParticipantRole.SPECTATOR
                existing.is_active = True
                return [_result(chat_id, "now_spectating", username=username)]

            await participant_repo.add(
                active_game.id,
                user.id,
                game.constants.ParticipantRole.SPECTATOR,
            )

            logger.info("%s spectating game %s", username, active_game.id)

            return [_result(chat_id, "now_spectating", username=username)]

    async def handle_leave(
        self,
        chat_id: int,
        telegram_id: int,
        username: str,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            game_repo = db.repositories.game.GameRepository(session)
            participant_repo = db.repositories.participant.ParticipantRepository(
                session
            )

            active_game = await game_repo.get_active_by_chat(chat_id)
            if active_game is None:
                return [_result(chat_id, "no_active_game_here")]

            participant = await participant_repo.get_by_telegram_id(
                active_game.id,
                telegram_id,
            )
            if participant is None or not participant.is_active:
                return [_result(chat_id, "not_in_game", username=username)]

            user_repo = db.repositories.user.UserRepository(session)
            user = await user_repo.get_by_telegram_id(telegram_id)

            if active_game.status == game.constants.GameStatus.ACTIVE:
                participant.is_active = False
                responses: list[game.schemas.ServiceResponse] = [
                    _result(chat_id, "left_game", username=username),
                ]
                remaining_players = await participant_repo.get_active_players(
                    active_game.id
                )
                if len(remaining_players) < 2:
                    finish_responses = await self._finish_game(
                        session,
                        active_game,
                        chat_id,
                        stopped=True,
                    )
                    responses.extend(finish_responses)
                elif active_game.current_player_id == participant.id:
                    next_player = await participant_repo.pick_random(
                        active_game.id
                    )
                    if next_player is not None:
                        active_game.current_player_id = next_player.id
                return responses

            if user and user.id == active_game.host_id:
                participant.is_active = False
                remaining_players = await participant_repo.get_active_players(
                    active_game.id,
                )
                if remaining_players:
                    new_host = remaining_players[0]
                    active_game.host_id = new_host.user_id
                    new_host_user = await user_repo.get_by_id(new_host.user_id)
                    new_host_name = (
                        new_host_user.username if new_host_user else "Unknown"
                    )
                    logger.info(
                        "Host transferred to %s in game %s",
                        new_host_name,
                        active_game.id,
                    )
                    return [
                        _result(
                            chat_id,
                            "host_transferred",
                            old_host=username,
                            new_host=new_host_name,
                        ),
                    ]
                active_game.status = game.constants.GameStatus.FINISHED
                active_game.finished_at = datetime.datetime.now(datetime.UTC)
                return [
                    _result(chat_id, "plain", text="No players remain - game ended."),
                ]

            participant.is_active = False
            logger.info("%s left game %s", username, active_game.id)
            return [_result(chat_id, "left_game", username=username)]

    async def handle_stop(
        self,
        chat_id: int,
        telegram_id: int,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            game_repo = db.repositories.game.GameRepository(session)
            user_repo = db.repositories.user.UserRepository(session)

            active_game = await game_repo.get_active_by_chat(chat_id)
            if active_game is None:
                return [_result(chat_id, "no_active_game_here")]

            user = await user_repo.get_by_telegram_id(telegram_id)
            if user is None or user.id != active_game.host_id:
                return [_result(chat_id, "only_host")]

            return await self._finish_game(
                session, active_game, chat_id, stopped=True
            )

    async def _finish_game(
        self,
        session: sqlalchemy.ext.asyncio.AsyncSession,
        active_game: game.models.GameModel,
        chat_id: int,
        *,
        stopped: bool = False,
    ) -> list[game.schemas.ServiceResponse]:
        active_game.status = game.constants.GameStatus.FINISHED
        active_game.finished_at = datetime.datetime.now(datetime.UTC)

        game_repo = db.repositories.game.GameRepository(session)
        game_state = await game_repo.get_state(active_game.id)
        if game_state:
            game_state.status = game.constants.GamePhase.FINISHED

        scoreboard_data = await game_repo.scoreboard(active_game.id)

        logger.info("Game %s finished (stopped=%s)", active_game.id, stopped)

        return [
            _result(
                chat_id,
                "scoreboard",
                title="Game stopped by host.\n\nFinal scores:"
                if stopped
                else "🏁 Game over!\n\nFinal scores:",
                scores=scoreboard_data,
                with_controls=False,
            )
        ]
