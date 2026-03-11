from __future__ import annotations

import datetime
import logging
import uuid

import db.repositories.game
import db.repositories.participant
import db.repositories.question
import db.repositories.user
import game.models
import game.schemas
import sqlalchemy
import sqlalchemy.ext.asyncio
import game.constants
4
logger = logging.getLogger(__name__)


def _result(
    chat_id: int, view: str, **payload: object
) -> game.schemas.ServiceResponse:
    return game.schemas.ServiceResponse(
        chat_id=chat_id,
        view=view,
        payload=dict(payload),
    )


class GameplayService:
    def __init__(
        self,
        session_factory: sqlalchemy.ext.asyncio.async_sessionmaker,
        buzzer_timeout: int,
        answer_timeout: int,
    ) -> None:
        self._session_factory = session_factory
        self._buzzer_timeout = buzzer_timeout
        self._answer_timeout = answer_timeout

    async def handle_start_game(
        self,
        chat_id: int,
        telegram_id: int,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            game_repo = db.repositories.game.GameRepository(session)
            user_repo = db.repositories.user.UserRepository(session)
            participant_repo = db.repositories.participant.ParticipantRepository(
                session
            )
            question_repo = db.repositories.question.QuestionRepository(session)

            active_game = await game_repo.get_active_by_chat(chat_id)
            if active_game is None:
                return [_result(chat_id, "no_active_game")]

            if active_game.status != game.constants.GameStatus.WAITING:
                return [_result(chat_id, "game_in_progress")]

            user = await user_repo.get_by_telegram_id(telegram_id)
            if user is None or user.id != active_game.host_id:
                return [_result(chat_id, "only_host")]

            active_players = await participant_repo.get_active_players(
                active_game.id
            )
            if len(active_players) < 2:
                return [_result(chat_id, "need_two_players")]

            all_question_ids = await question_repo.all_question_ids()
            if not all_question_ids:
                return [_result(chat_id, "no_questions")]

            await question_repo.bulk_create_questions_in_game(
                active_game.id,
                all_question_ids,
            )

            first_player = await participant_repo.pick_random(active_game.id)
            active_game.status = game.constants.GameStatus.ACTIVE
            active_game.current_player_id = first_player.id

            game_state = await game_repo.get_state(active_game.id)
            game_state.status = game.constants.GamePhase.CHOOSING_QUESTION

            first_player_name = await game_repo.current_player_username(
                active_game
            )
            pending_board = await question_repo.get_pending_board(active_game.id)

            logger.info(
                "Game %s started in chat %s, first player: %s",
                active_game.id,
                chat_id,
                first_player_name,
            )

            return [
                _result(
                    chat_id,
                    "board",
                    intro="🎯 Game started!",
                    current_player=first_player_name,
                    rows=pending_board,
                )
            ]

    async def handle_buzzer(
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
            if (
                active_game is None
                or active_game.status != game.constants.GameStatus.ACTIVE
            ):
                return []

            participant = await participant_repo.get_by_telegram_id(
                active_game.id,
                telegram_id,
            )
            if (
                participant is None
                or not participant.is_active
                or participant.role != game.constants.ParticipantRole.PLAYER
            ):
                return []

            statement = (
                sqlalchemy.select(game.models.GameStateModel)
                .where(game.models.GameStateModel.game_id == active_game.id)
                .with_for_update()
            )
            game_state = (await session.execute(statement)).scalar_one_or_none()
            if (
                game_state is None
                or game_state.status
                != game.constants.GamePhase.WAITING_BUZZER
            ):
                return []

            if game_state.buzzer_pressed_by is not None:
                return []

            now = datetime.datetime.now(datetime.UTC)
            game_state.buzzer_pressed_by = participant.id
            game_state.buzzer_pressed_at = now
            game_state.status = game.constants.GamePhase.WAITING_ANSWER
            game_state.timer_ends_at = now + datetime.timedelta(
                seconds=self._answer_timeout,
            )

            logger.info(
                "%s pressed buzzer in game %s",
                username,
                active_game.id,
            )

            return [
                _result(
                    chat_id,
                    "buzzer_pressed",
                    username=username,
                    answer_timeout=self._answer_timeout,
                )
            ]

    async def handle_question_selected(
        self,
        chat_id: int,
        telegram_id: int,
        question_in_game_id_str: str,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            game_repo = db.repositories.game.GameRepository(session)
            participant_repo = db.repositories.participant.ParticipantRepository(
                session
            )
            question_repo = db.repositories.question.QuestionRepository(session)

            active_game = await game_repo.get_active_by_chat(chat_id)
            if (
                active_game is None
                or active_game.status != game.constants.GameStatus.ACTIVE
            ):
                return []

            game_state = await game_repo.get_state(active_game.id)
            if (
                game_state is None
                or game_state.status
                != game.constants.GamePhase.CHOOSING_QUESTION
            ):
                return []

            participant = await participant_repo.get_by_telegram_id(
                active_game.id,
                telegram_id,
            )
            if (
                participant is None
                or participant.id != active_game.current_player_id
            ):
                return [_result(chat_id, "not_your_turn")]

            validation = await self._validate_question_selection(
                question_repo,
                active_game,
                question_in_game_id_str,
            )
            if isinstance(validation, str):
                return [_result(chat_id, "plain", text=validation)]
            detail = validation
            (
                question_in_game,
                topic_title,
                question_text,
                _answer,
                cost,
            ) = detail

            now = datetime.datetime.now(datetime.UTC)
            question_in_game.status = game.constants.QuestionInGameStatus.ASKED
            question_in_game.asked_by = participant.id
            question_in_game.asked_at = now

            game_state.status = game.constants.GamePhase.WAITING_BUZZER
            game_state.current_question_id = question_in_game.id
            game_state.buzzer_pressed_by = None
            game_state.buzzer_pressed_at = None
            game_state.timer_ends_at = now + datetime.timedelta(
                seconds=self._buzzer_timeout,
            )

            logger.info(
                "Question selected: [%s] %s (%d pts) in game %s",
                topic_title,
                question_text[:50],
                cost,
                active_game.id,
            )

            return [
                _result(
                    chat_id,
                    "question_asked",
                    topic=topic_title,
                    cost=cost,
                    text=question_text,
                    buzzer_timeout=self._buzzer_timeout,
                )
            ]

    @staticmethod
    async def _validate_question_selection(
        question_repo: db.repositories.question.QuestionRepository,
        active_game: game.models.GameModel,
        question_in_game_id_str: str,
    ) -> str | tuple:
        try:
            question_in_game_id = uuid.UUID(question_in_game_id_str)
        except ValueError:
            return "Invalid question selection."

        detail = await question_repo.get_question_in_game_detail(
            question_in_game_id
        )
        if detail is None:
            return "Question not found."

        question_in_game = detail[0]
        if question_in_game.game_id != active_game.id:
            return "This question doesn't belong to your game."

        if (
            question_in_game.status
            != game.constants.QuestionInGameStatus.PENDING
        ):
            return "This question has already been played."

        return detail

    async def handle_possible_answer(
        self,
        chat_id: int,
        telegram_id: int,
        username: str,
        text: str,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            game_repo = db.repositories.game.GameRepository(session)
            participant_repo = db.repositories.participant.ParticipantRepository(
                session
            )

            active_game = await game_repo.get_active_by_chat(chat_id)
            if (
                active_game is None
                or active_game.status != game.constants.GameStatus.ACTIVE
            ):
                return []

            game_state = await game_repo.get_state(active_game.id)
            if (
                game_state is None
                or game_state.status != game.constants.GamePhase.WAITING_ANSWER
            ):
                return []

            participant = await participant_repo.get_by_telegram_id(
                active_game.id,
                telegram_id,
            )
            if (
                participant is None
                or participant.id != game_state.buzzer_pressed_by
            ):
                return []

            return await self._process_answer(
                session,
                active_game,
                game_state,
                participant,
                username,
                text,
            )

    async def handle_score(
        self,
        chat_id: int,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            game_repo = db.repositories.game.GameRepository(session)

            active_game = await game_repo.get_active_by_chat(chat_id)
            if active_game is None:
                return [_result(chat_id, "no_active_game_here")]

            scoreboard_data = await game_repo.scoreboard(active_game.id)
            if not scoreboard_data:
                return [_result(chat_id, "plain", text="No players yet.")]

            return [
                _result(
                    chat_id,
                    "scoreboard",
                    title="📊 Current scores:\n",
                    scores=scoreboard_data,
                    with_controls=True,
                )
            ]

    async def _process_answer(
        self,
        session: sqlalchemy.ext.asyncio.AsyncSession,
        active_game: game.models.GameModel,
        game_state: game.models.GameStateModel,
        buzzer_participant: game.models.ParticipantModel,
        username: str,
        answer_text: str,
    ) -> list[game.schemas.ServiceResponse]:
        question_repo = db.repositories.question.QuestionRepository(session)
        chat_id = active_game.chat_id

        detail = await question_repo.get_question_in_game_detail(
            game_state.current_question_id,
        )
        if detail is None:
            return [_result(chat_id, "plain", text="Question data not found.")]

        question_in_game, _topic_title, _question_text, correct_answer, cost = (
            detail
        )

        now = datetime.datetime.now(datetime.UTC)
        is_correct = (
            answer_text.strip().lower() == correct_answer.strip().lower()
        )

        responses: list[game.schemas.ServiceResponse] = []

        if is_correct:
            buzzer_participant.score += cost
            question_in_game.status = (
                game.constants.QuestionInGameStatus.ANSWERED
            )
            question_in_game.answered_by = buzzer_participant.id
            question_in_game.answered_at = now
            active_game.current_player_id = buzzer_participant.id
            game_state.timer_ends_at = None
            responses.append(
                _result(
                    chat_id,
                    "answer_correct",
                    username=username,
                    cost=cost,
                    correct_answer=correct_answer,
                ),
            )
        else:
            buzzer_participant.score -= cost
            question_in_game.status = (
                game.constants.QuestionInGameStatus.ANSWERED
            )
            question_in_game.answered_by = buzzer_participant.id
            question_in_game.answered_at = now
            game_state.timer_ends_at = None
            responses.append(
                _result(
                    chat_id,
                    "answer_wrong",
                    username=username,
                    cost=cost,
                    correct_answer=correct_answer,
                ),
            )

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
