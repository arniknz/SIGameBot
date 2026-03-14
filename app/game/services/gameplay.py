from __future__ import annotations

import datetime
import logging
import random
import uuid

import db.repositories.game
import db.repositories.participant
import db.repositories.question
import db.repositories.shop
import db.repositories.user
import game.constants
import game.models
import game.schemas
import game.shop_items
import sqlalchemy
import sqlalchemy.ext.asyncio

logger = logging.getLogger(__name__)


def _result(
    chat_id: int, view: game.constants.ViewName, **payload: object
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
        question_selection_timeout: int,
        buzzer_timeout: int,
        answer_timeout: int,
    ) -> None:
        self._session_factory = session_factory
        self._question_selection_timeout = question_selection_timeout
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
            participant_repo = (
                db.repositories.participant.ParticipantRepository(session)
            )
            question_repo = db.repositories.question.QuestionRepository(session)

            error = await self._validate_start(
                game_repo,
                user_repo,
                participant_repo,
                question_repo,
                chat_id,
                telegram_id,
            )
            if error is not None:
                return error

            active_game = await game_repo.get_active_by_chat(chat_id)
            assert active_game is not None
            all_question_ids = await question_repo.all_question_ids()

            await question_repo.bulk_create_questions_in_game(
                active_game.id,
                all_question_ids,
            )

            first_player = await participant_repo.pick_random(active_game.id)
            if first_player is None:
                return []
            active_game.status = game.constants.GameStatus.ACTIVE
            active_game.current_player_id = first_player.id

            game_state = await game_repo.get_state(active_game.id)
            if game_state is None:
                return []
            now = datetime.datetime.now(datetime.UTC)
            game_state.status = game.constants.GamePhase.CHOOSING_QUESTION
            game_state.timer_ends_at = now + datetime.timedelta(
                seconds=self._question_selection_timeout,
            )

            first_player_name = await game_repo.current_player_username(
                active_game
            )
            pending_board = await question_repo.get_pending_board(
                active_game.id
            )

            logger.info(
                "Game %s started in chat %s, first player: %s",
                active_game.id,
                chat_id,
                first_player_name,
            )

            return [
                _result(
                    chat_id,
                    game.constants.ViewName.BOARD,
                    intro="🎯 Game started! Let's go!",
                    current_player=first_player_name,
                    rows=pending_board,
                    selection_timeout=(self._question_selection_timeout),
                )
            ]

    @staticmethod
    async def _validate_start(
        game_repo: db.repositories.game.GameRepository,
        user_repo: db.repositories.user.UserRepository,
        participant_repo: db.repositories.participant.ParticipantRepository,
        question_repo: db.repositories.question.QuestionRepository,
        chat_id: int,
        telegram_id: int,
    ) -> list[game.schemas.ServiceResponse] | None:
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
                    game.constants.ViewName.GAME_IN_PROGRESS,
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

        active_players = await participant_repo.get_active_players(
            active_game.id
        )
        if len(active_players) < 2:
            return [
                _result(
                    chat_id,
                    game.constants.ViewName.NEED_TWO_PLAYERS,
                )
            ]

        all_question_ids = await question_repo.all_question_ids()
        if not all_question_ids:
            return [
                _result(
                    chat_id,
                    game.constants.ViewName.NO_QUESTIONS,
                )
            ]

        return None

    async def handle_buzzer(
        self,
        chat_id: int,
        telegram_id: int,
        username: str,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            game_repo = db.repositories.game.GameRepository(session)
            participant_repo = (
                db.repositories.participant.ParticipantRepository(session)
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

            game_state = await game_repo.get_state_for_update(active_game.id)
            if (
                game_state is None
                or game_state.status != game.constants.GamePhase.WAITING_BUZZER
            ):
                return []

            if game_state.buzzer_pressed_by is not None:
                return []

            now = datetime.datetime.now(datetime.UTC)
            game_state.buzzer_pressed_by = participant.id
            game_state.buzzer_pressed_at = now
            game_state.status = game.constants.GamePhase.WAITING_ANSWER
            game_state.all_in_active = False
            game_state.timer_ends_at = now + datetime.timedelta(
                seconds=self._answer_timeout,
            )

            show_all_in = False
            if not participant.all_in_used:
                max_score = await participant_repo.get_max_score(active_game.id)
                if max_score > 0 and participant.score < max_score / 2:
                    show_all_in = True

            logger.info(
                "%s pressed buzzer in game %s (all_in_eligible=%s)",
                username,
                active_game.id,
                show_all_in,
            )

            return [
                _result(
                    chat_id,
                    game.constants.ViewName.BUZZER_PRESSED,
                    username=username,
                    answer_timeout=self._answer_timeout,
                    show_all_in=show_all_in,
                )
            ]

    async def handle_cat_in_bag(
        self,
        chat_id: int,
        telegram_id: int,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            game_repo = db.repositories.game.GameRepository(session)
            participant_repo = (
                db.repositories.participant.ParticipantRepository(session)
            )
            question_repo = db.repositories.question.QuestionRepository(session)

            active_game = await game_repo.get_active_by_chat(chat_id)
            if (
                active_game is None
                or active_game.status != game.constants.GameStatus.ACTIVE
            ):
                return []

            game_state = await game_repo.get_state_for_update(active_game.id)
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
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.NOT_YOUR_TURN,
                    )
                ]

            detail = await question_repo.get_random_pending(active_game.id)
            if detail is None:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="🎲 No questions left in the bag!",
                    )
                ]

            (
                question_in_game,
                topic_title,
                question_text,
                _answer,
                _original_cost,
            ) = detail

            cat_cost = random.choice([100, 200, 300])

            now = datetime.datetime.now(datetime.UTC)
            question_in_game.status = game.constants.QuestionInGameStatus.ASKED
            question_in_game.asked_by = participant.id
            question_in_game.asked_at = now

            game_state.status = game.constants.GamePhase.WAITING_BUZZER
            game_state.current_question_id = question_in_game.id
            game_state.buzzer_pressed_by = None
            game_state.buzzer_pressed_at = None
            game_state.cost_override = cat_cost
            game_state.timer_ends_at = now + datetime.timedelta(
                seconds=self._buzzer_timeout,
            )
            game_state.updated_at = now

            logger.info(
                "🎲 Cat in a Bag: [%s] %s (%d pts) in game %s",
                topic_title,
                question_text[:50],
                cat_cost,
                active_game.id,
            )

            return [
                _result(
                    chat_id,
                    game.constants.ViewName.CAT_REVEALED,
                    topic=topic_title,
                    cost=cat_cost,
                    text=question_text,
                    buzzer_timeout=self._buzzer_timeout,
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
            participant_repo = (
                db.repositories.participant.ParticipantRepository(session)
            )
            question_repo = db.repositories.question.QuestionRepository(session)

            active_game = await game_repo.get_active_by_chat(chat_id)
            if (
                active_game is None
                or active_game.status != game.constants.GameStatus.ACTIVE
            ):
                return []

            game_state = await game_repo.get_state_for_update(active_game.id)
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
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.NOT_YOUR_TURN,
                    )
                ]

            validation = await self._validate_question_selection(
                question_repo,
                active_game,
                question_in_game_id_str,
            )
            if isinstance(validation, str):
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text=validation,
                    )
                ]
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
            game_state.cost_override = None
            game_state.timer_ends_at = now + datetime.timedelta(
                seconds=self._buzzer_timeout,
            )
            game_state.updated_at = now

            logger.info(
                "Question selected: [%s] %s (%d pts) in game %s",
                topic_title,
                question_text[:50],
                cost,
                active_game.id,
            )

            responses: list[game.schemas.ServiceResponse] = [
                _result(
                    chat_id,
                    game.constants.ViewName.QUESTION_ASKED,
                    topic=topic_title,
                    cost=cost,
                    text=question_text,
                    buzzer_timeout=self._buzzer_timeout,
                )
            ]

            shop_repo = db.repositories.shop.ShopRepository(session)
            auto_buzzers = await shop_repo.get_all_pending_auto_buzzers(
                active_game.id,
            )
            if auto_buzzers:
                ab = auto_buzzers[0]
                ab.question_in_game_id = question_in_game.id
                ab_participant = await participant_repo.get_active_player_by_id(
                    active_game.id, ab.participant_id
                )
                if ab_participant and ab_participant.is_active:
                    user_repo = db.repositories.user.UserRepository(session)
                    ab_user = await user_repo.get_by_id(ab_participant.user_id)
                    ab_name = ab_user.username if ab_user else "Unknown"

                    game_state.buzzer_pressed_by = ab_participant.id
                    game_state.buzzer_pressed_at = now
                    game_state.status = game.constants.GamePhase.WAITING_ANSWER
                    game_state.timer_ends_at = now + datetime.timedelta(
                        seconds=self._answer_timeout,
                    )
                    responses.append(
                        _result(
                            chat_id,
                            game.constants.ViewName.BUZZER_PRESSED,
                            username=f"⚡ {ab_name} (auto)",
                            answer_timeout=self._answer_timeout,
                        )
                    )
                    logger.info(
                        "Auto-buzzer triggered for %s in game %s",
                        ab_name,
                        active_game.id,
                    )

            return responses

    @staticmethod
    async def _validate_question_selection(
        question_repo: db.repositories.question.QuestionRepository,
        active_game: game.models.GameModel,
        question_in_game_id_str: str,
    ) -> (
        str
        | sqlalchemy.Row[
            tuple[
                game.models.QuestionInGameModel,
                str,
                str,
                str,
                int,
            ]
        ]
    ):
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
            participant_repo = (
                db.repositories.participant.ParticipantRepository(session)
            )

            active_game = await game_repo.get_active_by_chat(chat_id)
            if (
                active_game is None
                or active_game.status != game.constants.GameStatus.ACTIVE
            ):
                return []

            game_state = await game_repo.get_state_for_update(active_game.id)
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
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.NO_ACTIVE_GAME_HERE,
                    )
                ]

            scoreboard_data = await game_repo.scoreboard(active_game.id)
            if not scoreboard_data:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="No players yet.",
                    )
                ]

            return [
                _result(
                    chat_id,
                    game.constants.ViewName.SCOREBOARD,
                    title="📊 Current scores:\n",
                    scores=scoreboard_data,
                    with_controls=True,
                )
            ]

    async def handle_all_in(
        self,
        chat_id: int,
        telegram_id: int,
        username: str,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            game_repo = db.repositories.game.GameRepository(session)
            participant_repo = (
                db.repositories.participant.ParticipantRepository(session)
            )

            active_game = await game_repo.get_active_by_chat(chat_id)
            if (
                active_game is None
                or active_game.status != game.constants.GameStatus.ACTIVE
            ):
                return []

            game_state = await game_repo.get_state_for_update(active_game.id)
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

            if participant.all_in_used or game_state.all_in_active:
                return []

            game_state.all_in_active = True

            effective_cost = game_state.cost_override or 0
            if effective_cost == 0 and game_state.current_question_id:
                question_repo = db.repositories.question.QuestionRepository(
                    session
                )
                detail = await question_repo.get_question_in_game_detail(
                    game_state.current_question_id,
                )
                if detail is not None:
                    effective_cost = detail[4]

            logger.info(
                "⚡ %s activated ALL-IN in game %s",
                username,
                active_game.id,
            )

            return [
                _result(
                    chat_id,
                    game.constants.ViewName.ALL_IN_ACTIVATED,
                    username=username,
                    cost=effective_cost,
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

        if game_state.current_question_id is None:
            return [
                _result(
                    chat_id,
                    game.constants.ViewName.PLAIN,
                    text="Question data not found.",
                )
            ]
        detail = await question_repo.get_question_in_game_detail(
            game_state.current_question_id,
        )
        if detail is None:
            return [
                _result(
                    chat_id,
                    game.constants.ViewName.PLAIN,
                    text="Question data not found.",
                )
            ]

        (
            question_in_game,
            _topic_title,
            _question_text,
            correct_answer,
            original_cost,
        ) = detail

        effective_cost = game_state.cost_override or original_cost
        is_all_in = game_state.all_in_active

        now = datetime.datetime.now(datetime.UTC)
        is_correct = (
            answer_text.strip().lower() == correct_answer.strip().lower()
        )

        effects = await self._get_active_effects(
            session,
            active_game.id,
            buzzer_participant.id,
            game_state.current_question_id,
        )

        for eff in effects:
            if eff == game.constants.ItemEffect.FORCE_CORRECT:
                is_correct = True
            elif eff == game.constants.ItemEffect.DOUBLE_POINTS:
                effective_cost *= 2

        responses: list[game.schemas.ServiceResponse] = []

        game_state.timer_ends_at = None

        has_no_penalty = game.constants.ItemEffect.NO_PENALTY in effects
        has_pass_on_wrong = game.constants.ItemEffect.PASS_ON_WRONG in effects
        has_transfer_penalty = (
            game.constants.ItemEffect.TRANSFER_PENALTY in effects
        )
        has_become_chooser = game.constants.ItemEffect.BECOME_CHOOSER in effects

        if is_correct:
            points = effective_cost * 2 if is_all_in else effective_cost
            buzzer_participant.score += points
            active_game.current_player_id = buzzer_participant.id
            question_in_game.status = (
                game.constants.QuestionInGameStatus.ANSWERED
            )
            question_in_game.answered_by = buzzer_participant.id
            question_in_game.answered_at = now
            responses.append(
                _result(
                    chat_id,
                    game.constants.ViewName.ANSWER_CORRECT,
                    username=username,
                    cost=points,
                    correct_answer=correct_answer,
                ),
            )
        elif has_pass_on_wrong:
            question_in_game.status = (
                game.constants.QuestionInGameStatus.PENDING
            )
            question_in_game.asked_by = None
            question_in_game.asked_at = None
            question_in_game.answered_by = None
            question_in_game.answered_at = None
            responses.append(
                _result(
                    chat_id,
                    game.constants.ViewName.ANSWER_WRONG,
                    username=username,
                    cost=0,
                    correct_answer="(💀 question returned to board)",
                ),
            )
        elif has_transfer_penalty:
            participant_repo = (
                db.repositories.participant.ParticipantRepository(session)
            )
            players = await participant_repo.get_active_players(active_game.id)
            opponents = [p for p in players if p.id != buzzer_participant.id]
            if opponents:
                victim = random.choice(opponents)
                victim.score -= effective_cost
                victim_user = await db.repositories.user.UserRepository(
                    session
                ).get_by_id(victim.user_id)
                victim_name = victim_user.username if victim_user else "someone"
                responses.append(
                    _result(
                        chat_id,
                        game.constants.ViewName.ANSWER_WRONG,
                        username=username,
                        cost=effective_cost,
                        correct_answer=(
                            f"{correct_answer}\n"
                            f"🪞 Penalty transferred to {victim_name}!"
                        ),
                    ),
                )
            else:
                buzzer_participant.score -= effective_cost
                responses.append(
                    _result(
                        chat_id,
                        game.constants.ViewName.ANSWER_WRONG,
                        username=username,
                        cost=effective_cost,
                        correct_answer=correct_answer,
                    ),
                )
            question_in_game.status = (
                game.constants.QuestionInGameStatus.ANSWERED
            )
            question_in_game.answered_by = buzzer_participant.id
            question_in_game.answered_at = now
        elif has_no_penalty:
            question_in_game.status = (
                game.constants.QuestionInGameStatus.ANSWERED
            )
            question_in_game.answered_by = buzzer_participant.id
            question_in_game.answered_at = now
            responses.append(
                _result(
                    chat_id,
                    game.constants.ViewName.ANSWER_WRONG,
                    username=username,
                    cost=0,
                    correct_answer=(
                        f"{correct_answer}\n🛡️ Shield absorbed the penalty!"
                    ),
                ),
            )
        else:
            if is_all_in:
                buzzer_participant.score = 0
            else:
                buzzer_participant.score -= effective_cost
            question_in_game.status = (
                game.constants.QuestionInGameStatus.ANSWERED
            )
            question_in_game.answered_by = buzzer_participant.id
            question_in_game.answered_at = now
            responses.append(
                _result(
                    chat_id,
                    game.constants.ViewName.ANSWER_WRONG,
                    username=username,
                    cost=effective_cost,
                    correct_answer=correct_answer,
                ),
            )

        if has_become_chooser and not is_correct:
            active_game.current_player_id = buzzer_participant.id

        if is_all_in:
            buzzer_participant.all_in_used = True

        game_state.cost_override = None
        game_state.all_in_active = False

        round_responses = await self._next_round_or_finish(
            session,
            active_game,
            game_state,
            chat_id,
        )
        responses.extend(round_responses)
        return responses

    @staticmethod
    async def _get_active_effects(
        session: sqlalchemy.ext.asyncio.AsyncSession,
        game_id: uuid.UUID,
        participant_id: uuid.UUID,
        question_in_game_id: uuid.UUID,
    ) -> set[game.constants.ItemEffect]:
        shop_repo = db.repositories.shop.ShopRepository(session)
        usages = await shop_repo.get_active_effects(
            game_id, participant_id, question_in_game_id
        )
        effects: set[game.constants.ItemEffect] = set()
        for usage in usages:
            item_def = game.shop_items.ITEMS_BY_ID.get(usage.item_id)
            if item_def:
                effects.add(item_def.effect)
        return effects

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
            _result(
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

        logger.info("Game %s finished (stopped=%s)", active_game.id, stopped)

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
