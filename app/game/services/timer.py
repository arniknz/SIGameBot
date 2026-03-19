from __future__ import annotations

import datetime
import logging

import db.repositories.game
import db.repositories.participant
import db.repositories.question
import db.repositories.shop
import db.repositories.user
import game.constants
import game.models
import game.schemas
import game.utils
import sqlalchemy.ext.asyncio

logger = logging.getLogger(__name__)


class TimerService:
    def __init__(
        self,
        session_factory: sqlalchemy.ext.asyncio.async_sessionmaker,
        question_selection_timeout: int = 30,
        max_failed_selections: int = 3,
        lobby_timeout: int = 3600,
    ) -> None:
        self._session_factory = session_factory
        self._question_selection_timeout = question_selection_timeout
        self._max_failed_selections = max_failed_selections
        self._lobby_timeout = lobby_timeout
        self._recovery_counter = 0

    async def check_timers(
        self,
    ) -> list[game.schemas.ServiceResponse]:
        responses: list[game.schemas.ServiceResponse] = []

        async with self._session_factory() as session, session.begin():
            game_repo = db.repositories.game.GameRepository(session)

            claimed_list = await game_repo.claim_expired_timers()
            for game_state, chat_id in claimed_list:
                active_game = game_state.game
                try:
                    timer_responses = await self._dispatch_timeout(
                        session, active_game, game_state, chat_id
                    )
                    responses.extend(timer_responses)
                except Exception:
                    logger.exception(
                        "Error processing timer for game %s",
                        active_game.id,
                    )

        self._recovery_counter += 1
        if self._recovery_counter >= 30:
            self._recovery_counter = 0
            recovery_responses = await self._recover_stale_games()
            responses.extend(recovery_responses)

        lobby_responses = await self._cancel_expired_lobbies()
        responses.extend(lobby_responses)

        return responses

    async def _dispatch_timeout(
        self,
        session: sqlalchemy.ext.asyncio.AsyncSession,
        active_game: game.models.GameModel,
        game_state: game.models.GameStateModel,
        chat_id: int,
    ) -> list[game.schemas.ServiceResponse]:
        if game_state.status == game.constants.GamePhase.CHOOSING_QUESTION:
            return await self._handle_choosing_timeout(
                session, active_game, game_state, chat_id
            )

        if game_state.status == game.constants.GamePhase.WAITING_BUZZER:
            return await self._handle_buzzer_timeout(
                session, active_game, game_state, chat_id
            )

        if game_state.status == game.constants.GamePhase.WAITING_ANSWER:
            return await self._handle_answer_timeout(
                session, active_game, game_state, chat_id
            )

        logger.warning(
            "Expired timer in unexpected phase %s for game %s",
            game_state.status,
            active_game.id,
        )
        return []

    async def _handle_choosing_timeout(
        self,
        session: sqlalchemy.ext.asyncio.AsyncSession,
        active_game: game.models.GameModel,
        game_state: game.models.GameStateModel,
        chat_id: int,
    ) -> list[game.schemas.ServiceResponse]:
        participant_repo = db.repositories.participant.ParticipantRepository(
            session
        )
        game_repo = db.repositories.game.GameRepository(session)
        question_repo = db.repositories.question.QuestionRepository(session)

        old_player_name = await game_repo.current_player_username(active_game)

        game_state.failed_selections_count += 1

        if game_state.failed_selections_count >= self._max_failed_selections:
            logger.warning(
                "Game %s auto-ending: %d consecutive failed selections",
                active_game.id,
                game_state.failed_selections_count,
            )
            responses: list[game.schemas.ServiceResponse] = [
                game.utils.service_result(
                    chat_id,
                    game.constants.ViewName.GAME_ENDED_AFK,
                    failed_count=game_state.failed_selections_count,
                ),
            ]
            responses.extend(
                await self._finish_game(session, active_game, chat_id)
            )
            return responses

        next_player = await participant_repo.pick_random(
            active_game.id,
            exclude_id=active_game.current_player_id,
        )
        if next_player is not None:
            active_game.current_player_id = next_player.id

        new_player_name = await game_repo.current_player_username(active_game)

        pending_board = await question_repo.get_pending_board(active_game.id)
        if not pending_board:
            return await self._finish_game(session, active_game, chat_id)

        now = datetime.datetime.now(datetime.UTC)
        game_state.timer_ends_at = now + datetime.timedelta(
            seconds=self._question_selection_timeout,
        )

        logger.info(
            "Choosing timeout in game %s: %s -> %s (failures: %d/%d)",
            active_game.id,
            old_player_name,
            new_player_name,
            game_state.failed_selections_count,
            self._max_failed_selections,
        )

        return [
            game.utils.service_result(
                chat_id,
                game.constants.ViewName.CHOOSING_TIMEOUT,
                old_player=old_player_name,
            ),
            game.utils.service_result(
                chat_id,
                game.constants.ViewName.BOARD,
                intro="",
                current_player=new_player_name,
                rows=pending_board,
                selection_timeout=(self._question_selection_timeout),
            ),
        ]

    async def _handle_buzzer_timeout(
        self,
        session: sqlalchemy.ext.asyncio.AsyncSession,
        active_game: game.models.GameModel,
        game_state: game.models.GameStateModel,
        chat_id: int,
    ) -> list[game.schemas.ServiceResponse]:
        question_repo = db.repositories.question.QuestionRepository(session)

        if game_state.current_question_id is None:
            return []
        detail = await question_repo.get_question_in_game_detail(
            game_state.current_question_id,
        )
        if detail is None:
            return []

        (
            question_in_game,
            _topic_title,
            _question_text,
            correct_answer,
            _cost,
            _answer_embedding,
        ) = detail

        question_in_game.status = game.constants.QuestionInGameStatus.ANSWERED
        question_in_game.answered_at = datetime.datetime.now(datetime.UTC)
        game_state.cost_override = None

        responses: list[game.schemas.ServiceResponse] = [
            game.utils.service_result(
                chat_id,
                game.constants.ViewName.BUZZER_TIMEOUT,
                correct_answer=correct_answer,
            ),
        ]

        round_responses = await self._next_round_or_finish(
            session, active_game, game_state, chat_id
        )
        responses.extend(round_responses)
        return responses

    async def _handle_answer_timeout(
        self,
        session: sqlalchemy.ext.asyncio.AsyncSession,
        active_game: game.models.GameModel,
        game_state: game.models.GameStateModel,
        chat_id: int,
    ) -> list[game.schemas.ServiceResponse]:
        question_repo = db.repositories.question.QuestionRepository(session)
        participant_repo = db.repositories.participant.ParticipantRepository(
            session
        )

        if game_state.current_question_id is None:
            return []
        detail = await question_repo.get_question_in_game_detail(
            game_state.current_question_id,
        )
        if detail is None:
            return []

        (
            question_in_game,
            _topic_title,
            _question_text,
            correct_answer,
            original_cost,
            _answer_embedding,
        ) = detail

        effective_cost = game_state.cost_override or original_cost

        buzzer_holder_name = "Неизвестный"
        if game_state.buzzer_pressed_by:
            buzzer_player = await participant_repo.get_active_player_by_id(
                active_game.id,
                game_state.buzzer_pressed_by,
            )
            if buzzer_player is not None:
                if game_state.all_in_active:
                    buzzer_player.score = 0
                    buzzer_player.all_in_used = True
                else:
                    buzzer_player.score -= effective_cost
                user_repo = db.repositories.user.UserRepository(session)
                buzzer_user = await user_repo.get_by_id(buzzer_player.user_id)
                buzzer_holder_name = (
                    buzzer_user.username if buzzer_user else "Неизвестный"
                )

        question_in_game.status = game.constants.QuestionInGameStatus.ANSWERED
        question_in_game.answered_at = datetime.datetime.now(datetime.UTC)
        game_state.cost_override = None
        game_state.all_in_active = False

        responses: list[game.schemas.ServiceResponse] = [
            game.utils.service_result(
                chat_id,
                game.constants.ViewName.ANSWER_TIMEOUT,
                username=buzzer_holder_name,
                cost=effective_cost,
                correct_answer=correct_answer,
            ),
        ]
        responses.extend(
            await self._next_round_or_finish(
                session, active_game, game_state, chat_id
            )
        )
        return responses

    async def _next_round_or_finish(
        self,
        session: sqlalchemy.ext.asyncio.AsyncSession,
        active_game: game.models.GameModel,
        game_state: game.models.GameStateModel,
        chat_id: int,
    ) -> list[game.schemas.ServiceResponse]:
        question_repo = db.repositories.question.QuestionRepository(session)
        game_repo = db.repositories.game.GameRepository(session)

        pending_board = await question_repo.get_pending_board(active_game.id)
        if not pending_board:
            return await self._finish_game(session, active_game, chat_id)

        now = datetime.datetime.now(datetime.UTC)
        game_state.status = game.constants.GamePhase.CHOOSING_QUESTION
        game_state.current_question_id = None
        game_state.buzzer_pressed_by = None
        game_state.buzzer_pressed_at = None
        game_state.cost_override = None
        game_state.all_in_active = False
        game_state.timer_ends_at = now + datetime.timedelta(
            seconds=self._question_selection_timeout,
        )

        current_player_name = await game_repo.current_player_username(
            active_game
        )
        return [
            game.utils.service_result(
                chat_id,
                game.constants.ViewName.BOARD,
                intro="",
                current_player=current_player_name,
                rows=pending_board,
                selection_timeout=(self._question_selection_timeout),
            )
        ]

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
            "⛔ Игра остановлена хостом.\n\n🏆 Итоговый счёт:"
            if stopped
            else "🏁 Игра окончена!\n\n🏆 Итоговый счёт:"
        )
        return [
            game.utils.service_result(
                chat_id,
                game.constants.ViewName.SCOREBOARD,
                title=title,
                scores=scoreboard_data,
                with_controls=False,
            )
        ]

    async def _cancel_expired_lobbies(
        self,
    ) -> list[game.schemas.ServiceResponse]:
        if self._lobby_timeout <= 0:
            return []
        responses: list[game.schemas.ServiceResponse] = []
        async with self._session_factory() as session, session.begin():
            game_repo = db.repositories.game.GameRepository(session)
            expired = await game_repo.claim_expired_lobbies(self._lobby_timeout)
            for active_game, game_state in expired:
                active_game.status = game.constants.GameStatus.FINISHED
                active_game.finished_at = datetime.datetime.now(datetime.UTC)
                game_state.status = game.constants.GamePhase.FINISHED
                game_state.timer_ends_at = None

                edit_msg_id = game_state.lobby_message_id

                logger.info(
                    "Lobby for game %s in chat %s cancelled (timeout %ds)",
                    active_game.id,
                    active_game.chat_id,
                    self._lobby_timeout,
                )

                responses.append(
                    game.utils.service_result(
                        active_game.chat_id,
                        game.constants.ViewName.LOBBY_CANCELLED,
                        edit_message_id=edit_msg_id,
                    )
                )
        return responses

    async def _recover_stale_games(
        self,
    ) -> list[game.schemas.ServiceResponse]:
        responses: list[game.schemas.ServiceResponse] = []
        async with self._session_factory() as session, session.begin():
            game_repo = db.repositories.game.GameRepository(session)
            question_repo = db.repositories.question.QuestionRepository(session)

            stale = await game_repo.recover_stale_games()
            for game_state, chat_id in stale:
                active_game = game_state.game
                logger.warning(
                    "Recovering stale game %s from phase %s",
                    active_game.id,
                    game_state.status,
                )

                if game_state.current_question_id is not None:
                    detail = await question_repo.get_question_in_game_detail(
                        game_state.current_question_id,
                    )
                    if detail is not None:
                        question_in_game = detail[0]
                        if (
                            question_in_game.status
                            != game.constants.QuestionInGameStatus.ANSWERED
                        ):
                            question_in_game.status = (
                                game.constants.QuestionInGameStatus.ANSWERED
                            )
                            question_in_game.answered_at = (
                                datetime.datetime.now(datetime.UTC)
                            )

                now = datetime.datetime.now(datetime.UTC)
                game_state.status = game.constants.GamePhase.CHOOSING_QUESTION
                game_state.current_question_id = None
                game_state.buzzer_pressed_by = None
                game_state.buzzer_pressed_at = None
                game_state.cost_override = None
                game_state.all_in_active = False
                game_state.timer_ends_at = now + datetime.timedelta(
                    seconds=self._question_selection_timeout,
                )

                pending_board = await question_repo.get_pending_board(
                    active_game.id
                )
                if not pending_board:
                    finish_responses = await self._finish_game(
                        session, active_game, chat_id
                    )
                    responses.extend(finish_responses)
                    continue

                current_player_name = await game_repo.current_player_username(
                    active_game
                )
                responses.append(
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.BOARD,
                        intro="🔄 Игра восстановлена! Продолжаем.",
                        current_player=current_player_name,
                        rows=pending_board,
                    )
                )

        return responses
