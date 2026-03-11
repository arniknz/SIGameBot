from __future__ import annotations

import datetime
import logging

import db.repositories.game
import db.repositories.participant
import db.repositories.question
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


class TimerService:
    def __init__(
        self,
        session_factory: sqlalchemy.ext.asyncio.async_sessionmaker,
    ) -> None:
        self._session_factory = session_factory

    async def check_timers(self) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            game_repo = db.repositories.game.GameRepository(session)

            claimed = await game_repo.claim_expired_timer()
            if claimed is None:
                return []

            game_state, chat_id = claimed
            active_game = game_state.game

            if game_state.status == game.constants.GamePhase.WAITING_BUZZER:
                return await self._handle_buzzer_timeout(
                    session,
                    active_game,
                    game_state,
                    chat_id,
                )

            if game_state.status == game.constants.GamePhase.WAITING_ANSWER:
                return await self._handle_answer_timeout(
                    session,
                    active_game,
                    game_state,
                    chat_id,
                )

            logger.warning(
                "Expired timer in unexpected phase %s for game %s",
                game_state.status,
                active_game.id,
            )
            return []

    async def _handle_buzzer_timeout(
        self,
        session: sqlalchemy.ext.asyncio.AsyncSession,
        active_game: game.models.GameModel,
        game_state: game.models.GameStateModel,
        chat_id: int,
    ) -> list[game.schemas.ServiceResponse]:
        question_repo = db.repositories.question.QuestionRepository(session)

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
        ) = detail

        question_in_game.status = game.constants.QuestionInGameStatus.ANSWERED
        question_in_game.answered_at = datetime.datetime.now(datetime.UTC)

        responses: list[game.schemas.ServiceResponse] = [
            _result(
                chat_id,
                "buzzer_timeout",
                correct_answer=correct_answer,
            ),
        ]

        round_responses = await self._next_round_or_finish(
            session,
            active_game,
            game_state,
            chat_id,
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

        detail = await question_repo.get_question_in_game_detail(
            game_state.current_question_id,
        )
        if detail is None:
            return []

        question_in_game, _topic_title, _question_text, correct_answer, cost = (
            detail
        )

        buzzer_holder_name = "Unknown"
        if game_state.buzzer_pressed_by:
            buzzer_player = await participant_repo.get_active_player_by_id(
                active_game.id,
                game_state.buzzer_pressed_by,
            )
            if buzzer_player is not None:
                buzzer_player.score -= cost
                user_repo = db.repositories.user.UserRepository(session)
                buzzer_user = await user_repo.get_by_id(buzzer_player.user_id)
                buzzer_holder_name = (
                    buzzer_user.username if buzzer_user else "Unknown"
                )

        question_in_game.status = game.constants.QuestionInGameStatus.ANSWERED
        question_in_game.answered_at = datetime.datetime.now(datetime.UTC)

        responses: list[game.schemas.ServiceResponse] = [
            _result(
                chat_id,
                "answer_timeout",
                username=buzzer_holder_name,
                cost=cost,
                correct_answer=correct_answer,
            ),
        ]

        round_responses = await self._next_round_or_finish(
            session,
            active_game,
            game_state,
            chat_id,
        )
        responses.extend(round_responses)
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

        game_state.status = game.constants.GamePhase.CHOOSING_QUESTION
        game_state.current_question_id = None
        game_state.buzzer_pressed_by = None
        game_state.buzzer_pressed_at = None

        current_player_name = await game_repo.current_player_username(
            active_game
        )
        return [
            _result(
                chat_id,
                "board",
                intro="",
                current_player=current_player_name,
                rows=pending_board,
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
