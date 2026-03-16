from __future__ import annotations

import datetime
import logging
import uuid

import db.repositories.game
import db.repositories.participant
import db.repositories.question
import db.repositories.shop
import db.repositories.user
import game.constants
import game.models
import game.schemas
import sqlalchemy.ext.asyncio

logger = logging.getLogger(__name__)


def _result(
    chat_id: int,
    view: game.constants.ViewName,
    *,
    is_alert: bool = False,
    edit_message_id: int | None = None,
    lobby_game_id: str | None = None,
    **payload: object,
) -> game.schemas.ServiceResponse:
    return game.schemas.ServiceResponse(
        chat_id=chat_id,
        view=view,
        payload=dict(payload),
        is_alert=is_alert,
        edit_message_id=edit_message_id,
        lobby_game_id=lobby_game_id,
    )


class LobbyService:
    def __init__(
        self,
        session_factory: sqlalchemy.ext.asyncio.async_sessionmaker,
        question_selection_timeout: int = 30,
    ) -> None:
        self._session_factory = session_factory
        self._question_selection_timeout = question_selection_timeout

    async def store_lobby_message_id(
        self,
        game_id_str: str,
        message_id: int,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            game_repo = db.repositories.game.GameRepository(session)
            await game_repo.set_lobby_message_id(
                uuid.UUID(game_id_str), message_id
            )

    async def _lobby_response(
        self,
        session: sqlalchemy.ext.asyncio.AsyncSession,
        active_game: game.models.GameModel,
        chat_id: int,
        bot_username: str = "",
        *,
        edit_message_id: int | None = None,
        lobby_game_id: str | None = None,
    ) -> game.schemas.ServiceResponse:
        participant_repo = (
            db.repositories.participant.ParticipantRepository(session)
        )
        roster = await participant_repo.get_roster(
            active_game.id, active_game.host_id
        )
        return _result(
            chat_id,
            game.constants.ViewName.LOBBY,
            edit_message_id=edit_message_id,
            lobby_game_id=lobby_game_id,
            roster=roster,
            bot_username=bot_username,
        )

    async def _resolve_lobby_message_id(
        self,
        session: sqlalchemy.ext.asyncio.AsyncSession,
        active_game: game.models.GameModel,
        lobby_message_id: int,
    ) -> int:
        game_repo = db.repositories.game.GameRepository(session)
        game_state = await game_repo.get_state(active_game.id)
        if game_state is None:
            return lobby_message_id

        if lobby_message_id and not game_state.lobby_message_id:
            game_state.lobby_message_id = lobby_message_id

        return lobby_message_id or game_state.lobby_message_id or 0

    async def handle_start(
        self,
        chat_id: int,
        telegram_id: int,
        username: str,
        bot_username: str = "",
    ) -> list[game.schemas.ServiceResponse]:
        async with (
            self._session_factory() as session,
            session.begin(),
        ):
            game_repo = db.repositories.game.GameRepository(session)
            user_repo = db.repositories.user.UserRepository(session)
            participant_repo = (
                db.repositories.participant.ParticipantRepository(session)
            )

            active_game = await game_repo.get_active_by_chat(chat_id)
            if active_game is not None:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.GAME_ALREADY_RUNNING,
                    )
                ]

            user = await user_repo.get_or_create(telegram_id, username)
            new_game = await game_repo.create(chat_id, host_id=user.id)
            await participant_repo.add(
                new_game.id,
                user.id,
                game.constants.ParticipantRole.PLAYER,
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

            lobby = await self._lobby_response(
                session,
                new_game,
                chat_id,
                bot_username,
                lobby_game_id=str(new_game.id),
            )
            return [lobby]

    async def handle_join(
        self,
        chat_id: int,
        telegram_id: int,
        username: str,
        bot_username: str = "",
        *,
        lobby_message_id: int = 0,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            game_repo = db.repositories.game.GameRepository(session)
            user_repo = db.repositories.user.UserRepository(session)
            participant_repo = (
                db.repositories.participant.ParticipantRepository(session)
            )

            active_game = await game_repo.get_active_by_chat(chat_id)
            if active_game is None:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.NO_ACTIVE_GAME,
                    )
                ]

            if active_game.status != game.constants.GameStatus.WAITING:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.GAME_ALREADY_STARTED,
                    )
                ]

            user = await user_repo.get_or_create(telegram_id, username)
            existing = await participant_repo.get_by_telegram_id(
                active_game.id, telegram_id
            )

            alert_text: str
            if existing is not None:
                if (
                    existing.is_active
                    and existing.role == game.constants.ParticipantRole.PLAYER
                ):
                    return [
                        _result(
                            chat_id,
                            game.constants.ViewName.ALREADY_IN_GAME,
                            username=username,
                        )
                    ]
                existing.is_active = True
                existing.role = game.constants.ParticipantRole.PLAYER
                existing.score = 0
                alert_text = f"🔄 С возвращением, {username}!"
                logger.info(
                    "%s rejoined game %s (score reset)",
                    username,
                    active_game.id,
                )
            else:
                await participant_repo.add(
                    active_game.id,
                    user.id,
                    game.constants.ParticipantRole.PLAYER,
                )
                alert_text = "✅ Вы вошли в игру как игрок!"
                logger.info("%s joined game %s", username, active_game.id)

            edit_id = await self._resolve_lobby_message_id(
                session, active_game, lobby_message_id
            )
            lobby = await self._lobby_response(
                session,
                active_game,
                chat_id,
                bot_username,
                edit_message_id=edit_id or None,
                lobby_game_id=str(active_game.id) if not edit_id else None,
            )
            return [
                lobby,
                _result(
                    chat_id,
                    game.constants.ViewName.PLAYER_JOINED,
                    username=username,
                    player_names=[],
                    alert_text=alert_text,
                ),
            ]

    async def handle_spectate(
        self,
        chat_id: int,
        telegram_id: int,
        username: str,
        bot_username: str = "",
        *,
        lobby_message_id: int = 0,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            game_repo = db.repositories.game.GameRepository(session)
            user_repo = db.repositories.user.UserRepository(session)
            participant_repo = (
                db.repositories.participant.ParticipantRepository(session)
            )

            active_game = await game_repo.get_active_by_chat(chat_id)
            if active_game is None:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.NO_ACTIVE_GAME,
                    )
                ]

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
                        _result(
                            chat_id,
                            game.constants.ViewName.ALREADY_SPECTATING,
                            username=username,
                        )
                    ]
                existing.role = game.constants.ParticipantRole.SPECTATOR
                existing.is_active = True
            else:
                await participant_repo.add(
                    active_game.id,
                    user.id,
                    game.constants.ParticipantRole.SPECTATOR,
                )

            logger.info("%s spectating game %s", username, active_game.id)

            edit_id = await self._resolve_lobby_message_id(
                session, active_game, lobby_message_id
            )
            lobby = await self._lobby_response(
                session,
                active_game,
                chat_id,
                bot_username,
                edit_message_id=edit_id or None,
                lobby_game_id=str(active_game.id) if not edit_id else None,
            )
            return [
                lobby,
                _result(
                    chat_id,
                    game.constants.ViewName.NOW_SPECTATING,
                    username=username,
                    alert_text="👀 Вы теперь зритель",
                ),
            ]

    async def handle_leave(
        self,
        chat_id: int,
        telegram_id: int,
        username: str,
        bot_username: str = "",
        *,
        lobby_message_id: int = 0,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            game_repo = db.repositories.game.GameRepository(session)
            participant_repo = (
                db.repositories.participant.ParticipantRepository(session)
            )

            active_game = await game_repo.get_active_by_chat(chat_id)
            if active_game is None:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.NO_ACTIVE_GAME_HERE,
                    )
                ]

            participant = await participant_repo.get_by_telegram_id(
                active_game.id,
                telegram_id,
            )
            if participant is None or not participant.is_active:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.NOT_IN_GAME,
                        username=username,
                    )
                ]

            user_repo = db.repositories.user.UserRepository(session)
            user = await user_repo.get_by_telegram_id(telegram_id)

            if active_game.status == game.constants.GameStatus.ACTIVE:
                return await self._leave_active_game(
                    session,
                    game_repo,
                    participant_repo,
                    user_repo,
                    active_game,
                    participant,
                    user,
                    chat_id,
                    username,
                )

            participant.is_active = False
            logger.info("%s left game %s", username, active_game.id)

            if user and user.id == active_game.host_id:
                remaining = await participant_repo.get_active_players(
                    active_game.id,
                )
                if remaining:
                    new_host = remaining[0]
                    active_game.host_id = new_host.user_id
                    new_host_user = await user_repo.get_by_id(new_host.user_id)
                    new_host_name = (
                        new_host_user.username if new_host_user else "Неизвестный"
                    )
                    logger.info(
                        "Host transferred to %s in game %s",
                        new_host_name,
                        active_game.id,
                    )
                else:
                    active_game.status = game.constants.GameStatus.FINISHED
                    active_game.finished_at = datetime.datetime.now(
                        datetime.UTC
                    )
                    game_state = await game_repo.get_state(active_game.id)
                    if game_state:
                        game_state.status = game.constants.GamePhase.FINISHED
                        game_state.timer_ends_at = None

                    edit_id = await self._resolve_lobby_message_id(
                        session, active_game, lobby_message_id
                    )
                    return [
                        _result(
                            chat_id,
                            game.constants.ViewName.GAME_ENDED_NO_PLAYERS,
                            edit_message_id=edit_id or None,
                            alert_text=(
                                "\U0001f6aa Игра завершена \u2014 "
                                "игроков не осталось"
                            ),
                        )
                    ]

            edit_id = await self._resolve_lobby_message_id(
                session, active_game, lobby_message_id
            )
            lobby = await self._lobby_response(
                session,
                active_game,
                chat_id,
                bot_username,
                edit_message_id=edit_id or None,
                lobby_game_id=str(active_game.id) if not edit_id else None,
            )
            return [
                lobby,
                _result(
                    chat_id,
                    game.constants.ViewName.LEFT_GAME,
                    username=username,
                    alert_text="🚪 Вы вышли из игры",
                ),
            ]

    async def _leave_active_game(
        self,
        session: sqlalchemy.ext.asyncio.AsyncSession,
        game_repo: db.repositories.game.GameRepository,
        participant_repo: db.repositories.participant.ParticipantRepository,
        user_repo: db.repositories.user.UserRepository,
        active_game: game.models.GameModel,
        participant: game.models.ParticipantModel,
        user: game.models.UserModel | None,
        chat_id: int,
        username: str,
    ) -> list[game.schemas.ServiceResponse]:
        participant.is_active = False

        game_state = await game_repo.get_state_for_update(active_game.id)

        if (
            game_state is not None
            and game_state.buzzer_pressed_by == participant.id
        ):
            game_state.buzzer_pressed_by = None
            game_state.buzzer_pressed_at = None
            if game_state.status == game.constants.GamePhase.WAITING_ANSWER:
                game_state.timer_ends_at = None

        responses: list[game.schemas.ServiceResponse] = [
            _result(
                chat_id,
                game.constants.ViewName.LEFT_GAME,
                username=username,
            ),
        ]

        remaining = await participant_repo.get_active_players(active_game.id)
        if len(remaining) < 2:
            finish_responses = await self._finish_game(
                session,
                active_game,
                chat_id,
                stopped=True,
            )
            responses.extend(finish_responses)
            return responses

        if active_game.current_player_id == participant.id:
            mid_turn = await self._handle_mid_turn_leave(
                session,
                game_repo,
                participant_repo,
                active_game,
                game_state,
                chat_id,
                username,
            )
            responses.extend(mid_turn)

        if user and user.id == active_game.host_id and remaining:
            new_host = remaining[0]
            active_game.host_id = new_host.user_id
            new_host_user = await user_repo.get_by_id(new_host.user_id)
            new_host_name = (
                new_host_user.username if new_host_user else "Неизвестный"
            )
            responses.append(
                _result(
                    chat_id,
                    game.constants.ViewName.HOST_TRANSFERRED,
                    old_host=username,
                    new_host=new_host_name,
                )
            )

        return responses

    async def _handle_mid_turn_leave(
        self,
        session: sqlalchemy.ext.asyncio.AsyncSession,
        game_repo: db.repositories.game.GameRepository,
        participant_repo: db.repositories.participant.ParticipantRepository,
        active_game: game.models.GameModel,
        game_state: game.models.GameStateModel | None,
        chat_id: int,
        username: str,
    ) -> list[game.schemas.ServiceResponse]:
        next_player = await participant_repo.pick_random(active_game.id)
        if next_player is not None:
            active_game.current_player_id = next_player.id

        if game_state is None or game_state.status not in (
            game.constants.GamePhase.WAITING_BUZZER,
            game.constants.GamePhase.WAITING_ANSWER,
        ):
            return []

        question_repo = db.repositories.question.QuestionRepository(session)
        await self._burn_current_question(question_repo, game_state)

        now = datetime.datetime.now(datetime.UTC)
        game_state.status = game.constants.GamePhase.CHOOSING_QUESTION
        game_state.current_question_id = None
        game_state.buzzer_pressed_by = None
        game_state.buzzer_pressed_at = None
        game_state.timer_ends_at = now + datetime.timedelta(
            seconds=self._question_selection_timeout,
        )

        pending_board = await question_repo.get_pending_board(active_game.id)
        if not pending_board:
            return await self._finish_game(session, active_game, chat_id)

        next_name = await game_repo.current_player_username(active_game)
        return [
            _result(
                chat_id,
                game.constants.ViewName.BOARD,
                intro=f"🔄 {username} вышел(а) во время хода.",
                current_player=next_name,
                rows=pending_board,
            )
        ]

    @staticmethod
    async def _burn_current_question(
        question_repo: db.repositories.question.QuestionRepository,
        game_state: game.models.GameStateModel,
    ) -> None:
        if game_state.current_question_id is None:
            return
        detail = await question_repo.get_question_in_game_detail(
            game_state.current_question_id,
        )
        if detail is None:
            return
        question_in_game = detail[0]
        if (
            question_in_game.status
            != game.constants.QuestionInGameStatus.ANSWERED
        ):
            question_in_game.status = (
                game.constants.QuestionInGameStatus.ANSWERED
            )
            question_in_game.answered_at = datetime.datetime.now(datetime.UTC)

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
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.NO_ACTIVE_GAME_HERE,
                    )
                ]

            user = await user_repo.get_by_telegram_id(telegram_id)
            if user is None or user.id != active_game.host_id:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.ONLY_HOST,
                    )
                ]

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
            game_state.timer_ends_at = None

        shop_repo = db.repositories.shop.ShopRepository(session)
        await shop_repo.apply_game_scores_to_balances(active_game.id)

        scoreboard_data = await game_repo.scoreboard(
            active_game.id, active_only=False
        )

        logger.info(
            "Game %s finished (stopped=%s)",
            active_game.id,
            stopped,
        )

        title = (
            "⛔ Game stopped by host.\n\n🏆 Final scores:"
            if stopped
            else "🏁 Game over!\n\n🏆 Final scores:"
        )
        return [
            _result(
                chat_id,
                game.constants.ViewName.SCOREBOARD,
                title=title,
                scores=scoreboard_data,
                with_controls=False,
            )
        ]
