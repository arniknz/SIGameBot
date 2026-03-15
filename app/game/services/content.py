from __future__ import annotations

import logging
import uuid

import db.repositories.game
import db.repositories.question
import db.repositories.user
import game.constants
import game.schemas
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

            user_repo = db.repositories.user.UserRepository(session)
            user = await user_repo.get_by_telegram_id(telegram_id)

            existing = await question_repo.get_topic_by_title(topic_name)
            if existing is not None:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ Topic already exists.",
                    )
                ]

            new_topic = await question_repo.create_topic(
                topic_name,
                created_by=user.id if user else None,
            )
            logger.info(
                "Topic '%s' created (id=%s)",
                topic_name,
                new_topic.id,
            )

            return [
                _result(
                    chat_id,
                    game.constants.ViewName.PLAIN,
                    text=f"✅ Topic «{topic_name}» created!",
                )
            ]

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
            user_repo = db.repositories.user.UserRepository(session)
            user = await user_repo.get_by_telegram_id(telegram_id)

            try:
                topic_id = uuid.UUID(topic_id_str)
            except ValueError:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ Invalid topic ID.",
                    )
                ]

            new_question = await question_repo.create_question(
                topic_id,
                text,
                answer,
                cost,
                created_by=user.id if user else None,
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
                    game.constants.ViewName.PLAIN,
                    text=(
                        f"✅ Question added "
                        f"(#{question_count} in topic), "
                        f"worth {cost} points!"
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
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text=(
                            "📭 No topics yet. "
                            "Create one with /add_topic <name>"
                        ),
                    )
                ]

            return [
                _result(
                    chat_id,
                    game.constants.ViewName.TOPIC_SELECT_FOR_ADD,
                    topics=topics,
                ),
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
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="📭 No topics to delete.",
                    )
                ]

            return [
                _result(
                    chat_id,
                    game.constants.ViewName.TOPIC_SELECT_FOR_DELETE,
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
            user_repo = db.repositories.user.UserRepository(session)

            try:
                topic_id = uuid.UUID(topic_id_str)
            except ValueError:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ Invalid topic ID.",
                    )
                ]

            topic = await question_repo.get_topic_by_id(topic_id)
            if topic is None:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ Topic not found.",
                    )
                ]

            user = await user_repo.get_by_telegram_id(telegram_id)
            if user is None:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ User not found.",
                    )
                ]

            if topic.created_by is not None and topic.created_by != user.id:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="🚫 You can only delete topics you created.",
                    )
                ]

            await question_repo.soft_delete_topic(topic_id)

            logger.info(
                "Topic %s soft-deleted by user %s",
                topic_id,
                telegram_id,
            )

            return [
                _result(
                    chat_id,
                    game.constants.ViewName.PLAIN,
                    text=(
                        f"🗑 Topic «{topic.title}» hidden. "
                        f"Use /restore_topic to restore it."
                    ),
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
                        game.constants.ViewName.PLAIN,
                        text="📭 No topics with questions to delete.",
                    )
                ]

            return [
                _result(
                    chat_id,
                    game.constants.ViewName.TOPIC_SELECT_FOR_DELETE_QUESTION,
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
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ Invalid topic ID.",
                    )
                ]

            questions = await question_repo.get_questions_by_topic(topic_id)
            if not questions:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="📭 No questions in this topic.",
                    )
                ]

            return [
                _result(
                    chat_id,
                    game.constants.ViewName.QUESTION_SELECT_FOR_DELETE,
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
            user_repo = db.repositories.user.UserRepository(session)

            try:
                question_id = uuid.UUID(question_id_str)
            except ValueError:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ Invalid question ID.",
                    )
                ]

            question = await question_repo.get_question_by_id(question_id)
            if question is None:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ Question not found.",
                    )
                ]

            user = await user_repo.get_by_telegram_id(telegram_id)
            if user is None:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ User not found.",
                    )
                ]

            if (
                question.created_by is not None
                and question.created_by != user.id
            ):
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="🚫 You can only delete questions you created.",
                    )
                ]

            await question_repo.soft_delete_question(question_id)

            logger.info(
                "Question %s soft-deleted by user %s",
                question_id,
                telegram_id,
            )

            return [
                _result(
                    chat_id,
                    game.constants.ViewName.PLAIN,
                    text=(
                        "🗑 Question hidden. "
                        "Use /restore_question to restore it."
                    ),
                )
            ]

    async def handle_my_games(
        self,
        chat_id: int,
        telegram_id: int,
    ) -> list[game.schemas.ServiceResponse]:
        async with (
            self._session_factory() as session,
            session.begin(),
        ):
            user_repo = db.repositories.user.UserRepository(session)
            game_repo = db.repositories.game.GameRepository(session)

            user = await user_repo.get_by_telegram_id(telegram_id)
            if user is None:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text=(
                            "🎮 No games yet. Add me to a group and use /start!"
                        ),
                    )
                ]

            hosted = await game_repo.get_hosted_with_player_counts(user.id)
            if not hosted:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="🎮 No active hosted games.",
                    )
                ]

            games_payload = [
                {
                    "chat_id": g.chat_id,
                    "status": str(g.status),
                    "player_count": count,
                    "created_at": (
                        g.created_at.strftime("%Y-%m-%d %H:%M")
                        if g.created_at
                        else "?"
                    ),
                }
                for g, count in hosted
            ]

            return [
                _result(
                    chat_id,
                    game.constants.ViewName.MY_GAMES,
                    games=games_payload,
                )
            ]

    async def handle_help(
        self,
        chat_id: int,
    ) -> list[game.schemas.ServiceResponse]:
        return [_result(chat_id, game.constants.ViewName.HELP)]

    async def handle_rules(
        self,
        chat_id: int,
    ) -> list[game.schemas.ServiceResponse]:
        return [
            _result(
                chat_id,
                game.constants.ViewName.RULES,
                buzzer_timeout=self._buzzer_timeout,
                answer_timeout=self._answer_timeout,
            )
        ]

    async def handle_restore_topic(
        self,
        chat_id: int,
        telegram_id: int,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            question_repo = db.repositories.question.QuestionRepository(session)
            user_repo = db.repositories.user.UserRepository(session)

            user = await user_repo.get_by_telegram_id(telegram_id)
            if user is None:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ User not found.",
                    )
                ]

            hidden = await question_repo.hidden_topics_for_user(user.id)
            if not hidden:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="📭 No hidden topics to restore.",
                    )
                ]

            return [
                _result(
                    chat_id,
                    game.constants.ViewName.TOPIC_SELECT_FOR_RESTORE,
                    topics=hidden,
                )
            ]

    async def confirm_restore_topic(
        self,
        chat_id: int,
        telegram_id: int,
        topic_id_str: str,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            question_repo = db.repositories.question.QuestionRepository(session)
            user_repo = db.repositories.user.UserRepository(session)

            try:
                topic_id = uuid.UUID(topic_id_str)
            except ValueError:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ Invalid topic ID.",
                    )
                ]

            topic = await question_repo.get_topic_by_id(topic_id)
            if topic is None:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ Topic not found.",
                    )
                ]

            user = await user_repo.get_by_telegram_id(telegram_id)
            if user is None:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ User not found.",
                    )
                ]

            if topic.created_by is not None and topic.created_by != user.id:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="🚫 You can only restore topics you created.",
                    )
                ]

            await question_repo.restore_topic(topic_id)

            logger.info(
                "Topic %s restored by user %s",
                topic_id,
                telegram_id,
            )

            return [
                _result(
                    chat_id,
                    game.constants.ViewName.PLAIN,
                    text=f"✅ Topic «{topic.title}» restored!",
                )
            ]

    async def handle_restore_question(
        self,
        chat_id: int,
        telegram_id: int,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            question_repo = db.repositories.question.QuestionRepository(session)
            user_repo = db.repositories.user.UserRepository(session)

            user = await user_repo.get_by_telegram_id(telegram_id)
            if user is None:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ User not found.",
                    )
                ]

            hidden = await question_repo.hidden_questions_for_user(user.id)
            if not hidden:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="📭 No hidden questions to restore.",
                    )
                ]

            return [
                _result(
                    chat_id,
                    game.constants.ViewName.QUESTION_SELECT_FOR_RESTORE,
                    questions=hidden,
                )
            ]

    async def confirm_restore_question(
        self,
        chat_id: int,
        telegram_id: int,
        question_id_str: str,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            question_repo = db.repositories.question.QuestionRepository(session)
            user_repo = db.repositories.user.UserRepository(session)

            try:
                question_id = uuid.UUID(question_id_str)
            except ValueError:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ Invalid question ID.",
                    )
                ]

            question = await question_repo.get_question_by_id(question_id)
            if question is None:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ Question not found.",
                    )
                ]

            user = await user_repo.get_by_telegram_id(telegram_id)
            if user is None:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ User not found.",
                    )
                ]

            if (
                question.created_by is not None
                and question.created_by != user.id
            ):
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="🚫 You can only restore questions you created.",
                    )
                ]

            await question_repo.restore_question(question_id)

            logger.info(
                "Question %s restored by user %s",
                question_id,
                telegram_id,
            )

            return [
                _result(
                    chat_id,
                    game.constants.ViewName.PLAIN,
                    text="✅ Question restored!",
                )
            ]
