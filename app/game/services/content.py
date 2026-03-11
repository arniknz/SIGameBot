from __future__ import annotations

import logging
import uuid

import db.repositories.game
import db.repositories.question
import db.repositories.user
import game.schemas
import sqlalchemy.ext.asyncio

logger = logging.getLogger(__name__)


def _result(
    chat_id: int, view: str, **payload: object
) -> game.schemas.ServiceResponse:
    return game.schemas.ServiceResponse(
        chat_id=chat_id,
        view=view,
        payload=dict(payload),
    )


class ContentService:
    def __init__(
        self,
        session_factory: sqlalchemy.ext.asyncio.async_sessionmaker,
        buzzer_timeout: int,
        answer_timeout: int,
    ) -> None:
        self._session_factory = session_factory
        self._buzzer_timeout = buzzer_timeout
        self._answer_timeout = answer_timeout

    async def handle_add_topic(
        self,
        chat_id: int,
        telegram_id: int,
        topic_name: str,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            question_repo = db.repositories.question.QuestionRepository(session)

            existing = await question_repo.get_topic_by_title(topic_name)
            if existing is not None:
                return [_result(chat_id, "plain", text="Topic already exists.")]

            new_topic = await question_repo.create_topic(topic_name)
            logger.info("Topic '%s' created (id=%s)", topic_name, new_topic.id)

            return [_result(chat_id, "plain", text="Topic created successfully.")]

    async def handle_add_question(
        self,
        chat_id: int,
        telegram_id: int,
        topic_id_str: str,
        text: str,
        answer: str,
        cost: int,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            question_repo = db.repositories.question.QuestionRepository(session)

            try:
                topic_id = uuid.UUID(topic_id_str)
            except ValueError:
                return [_result(chat_id, "plain", text="Invalid topic ID.")]

            new_question = await question_repo.create_question(
                topic_id,
                text,
                answer,
                cost,
            )
            question_count = await question_repo.question_count_by_topic(
                topic_id
            )

            logger.info(
                "Question created (id=%s) in topic %s",
                new_question.id,
                topic_id,
            )

            return [
                _result(
                    chat_id,
                    "plain",
                    text=(
                        f"Question added (#{question_count} in this topic), "
                        f"cost: {cost} points."
                    ),
                )
            ]

    async def topic_keyboard_for_add(
        self,
        chat_id: int,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            question_repo = db.repositories.question.QuestionRepository(session)

            topics = await question_repo.all_topics()
            if not topics:
                return [_result(chat_id, "plain", text="No topics yet.")]

            return [
                _result(chat_id, "topic_select_for_add", topics=topics),
            ]

    async def handle_delete_topic(
        self,
        chat_id: int,
        telegram_id: int,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            question_repo = db.repositories.question.QuestionRepository(session)

            topics_with_counts = (
                await question_repo.topics_with_question_counts()
            )
            if not topics_with_counts:
                return [_result(chat_id, "plain", text="No topics to delete.")]

            return [
                _result(
                    chat_id,
                    "topic_select_for_delete",
                    topics_with_counts=topics_with_counts,
                )
            ]

    async def confirm_delete_topic(
        self,
        chat_id: int,
        telegram_id: int,
        topic_id_str: str,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            question_repo = db.repositories.question.QuestionRepository(session)

            try:
                topic_id = uuid.UUID(topic_id_str)
            except ValueError:
                return [_result(chat_id, "plain", text="Invalid topic ID.")]

            deleted_count = await question_repo.delete_topic(topic_id)

            logger.info(
                "Topic %s deleted with %d questions",
                topic_id,
                deleted_count,
            )

            return [
                _result(
                    chat_id,
                    "plain",
                    text=f"Topic deleted with {deleted_count} question(s).",
                )
            ]

    async def handle_delete_question(
        self,
        chat_id: int,
        telegram_id: int,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            question_repo = db.repositories.question.QuestionRepository(session)

            topics_with_counts = (
                await question_repo.topics_with_question_counts()
            )
            if not topics_with_counts:
                return [
                    _result(
                        chat_id,
                        "plain",
                        text="No topics with questions to delete.",
                    )
                ]

            return [
                _result(
                    chat_id,
                    "topic_select_for_delete_question",
                    topics_with_counts=topics_with_counts,
                )
            ]

    async def list_questions_for_delete(
        self,
        chat_id: int,
        topic_id_str: str,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            question_repo = db.repositories.question.QuestionRepository(session)

            try:
                topic_id = uuid.UUID(topic_id_str)
            except ValueError:
                return [_result(chat_id, "plain", text="Invalid topic ID.")]

            questions = await question_repo.get_questions_by_topic(topic_id)
            if not questions:
                return [_result(chat_id, "plain", text="No questions in this topic.")]

            return [
                _result(
                    chat_id,
                    "question_select_for_delete",
                    questions=questions,
                )
            ]

    async def confirm_delete_question(
        self,
        chat_id: int,
        telegram_id: int,
        question_id_str: str,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            question_repo = db.repositories.question.QuestionRepository(session)

            try:
                question_id = uuid.UUID(question_id_str)
            except ValueError:
                return [_result(chat_id, "plain", text="Invalid question ID.")]

            deleted = await question_repo.delete_question(question_id)
            if not deleted:
                return [
                    _result(
                        chat_id,
                        "plain",
                        text="Question not found or already deleted.",
                    )
                ]

            logger.info("Question %s deleted", question_id)

            return [_result(chat_id, "plain", text="Question deleted.")]

    async def handle_my_games(
        self,
        chat_id: int,
        telegram_id: int,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            user_repo = db.repositories.user.UserRepository(session)
            game_repo = db.repositories.game.GameRepository(session)

            user = await user_repo.get_by_telegram_id(telegram_id)
            if user is None:
                return [_result(chat_id, "plain", text="No games yet.")]

            hosted_games = await game_repo.get_hosted_by(user.id)
            if not hosted_games:
                return [
                    _result(chat_id, "plain", text="No active hosted games.")
                ]

            lines = ["🎮 Your active hosted games:\n"]
            lines.extend(
                f"• Chat {hg.chat_id} — "
                f"status: {hg.status}, "
                f"created: {hg.created_at:%Y-%m-%d %H:%M}"
                for hg in hosted_games
            )

            return [_result(chat_id, "plain", text="\n".join(lines))]

    async def handle_help(
        self,
        chat_id: int,
    ) -> list[game.schemas.ServiceResponse]:
        return [_result(chat_id, "help")]

    async def handle_rules(
        self,
        chat_id: int,
    ) -> list[game.schemas.ServiceResponse]:
        return [
            _result(
                chat_id,
                "rules",
                buzzer_timeout=self._buzzer_timeout,
                answer_timeout=self._answer_timeout,
            )
        ]
