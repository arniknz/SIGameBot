from __future__ import annotations

import csv
import io
import logging
import uuid

import db.repositories.game
import db.repositories.question
import db.repositories.user
import game.answer_similarity
import game.constants
import game.models
import game.schemas
import game.utils
import sqlalchemy
import sqlalchemy.ext.asyncio

logger = logging.getLogger(__name__)


def _parse_csv_row(
    row: dict[str, str],
    field_map: dict[str, str],
    row_num: int,
) -> tuple[str, str, str, int] | str:
    topic = row[field_map["topic"]].strip()
    question = row[field_map["question"]].strip()
    answer = row[field_map["answer"]].strip()
    cost_raw = row[field_map["cost"]].strip()

    if not all([topic, question, answer, cost_raw]):
        return f"Row {row_num}: empty required field"
    try:
        cost = int(cost_raw)
        if cost <= 0:
            raise ValueError
    except ValueError:
        return f"Row {row_num}: cost must be a positive integer"
    return topic, question, answer, cost


class ContentService:
    def __init__(
        self,
        session_factory: sqlalchemy.ext.asyncio.async_sessionmaker,
        buzzer_timeout: int,
        answer_timeout: int,
        max_csv_rows: int = 1000,
    ) -> None:
        self._session_factory = session_factory
        self._buzzer_timeout = buzzer_timeout
        self._answer_timeout = answer_timeout
        self._max_csv_rows = max_csv_rows

    async def handle_add_topic(
        self,
        chat_id: int,
        telegram_id: int,
        topic_name: str,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            question_repo = db.repositories.question.QuestionRepository(session)

            user_repo = db.repositories.user.UserRepository(session)
            user = await user_repo.ensure_exists(telegram_id)

            existing = await question_repo.get_topic_by_title(topic_name)
            if existing is not None:
                return [
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ Такая тема уже есть.",
                    )
                ]

            new_topic = await question_repo.create_topic(
                topic_name,
                created_by=user.id,
            )
            logger.info(
                "Topic '%s' created (id=%s)",
                topic_name,
                new_topic.id,
            )

            return [
                game.utils.service_result(
                    chat_id,
                    game.constants.ViewName.PLAIN,
                    text=f"✅ Тема «{topic_name}» создана!",
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
            user = await user_repo.ensure_exists(telegram_id)

            try:
                topic_id = uuid.UUID(topic_id_str)
            except ValueError:
                return [
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ Неверный ID темы.",
                    )
                ]

            normalized_answer = game.answer_similarity.normalize_answer_text(
                answer
            )

            new_question = await question_repo.create_question(
                topic_id,
                text,
                answer,
                cost,
                created_by=user.id,
                normalized_answer=normalized_answer,
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
                game.utils.service_result(
                    chat_id,
                    game.constants.ViewName.PLAIN,
                    text=(
                        f"✅ Вопрос добавлен "
                        f"(№{question_count} в теме), "
                        f"стоимость {cost} очков!"
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
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text=(
                            "📭 Тем пока нет. Создайте: /add_topic <название>"
                        ),
                    )
                ]

            return [
                game.utils.service_result(
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
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="📭 Нет тем для удаления.",
                    )
                ]

            return [
                game.utils.service_result(
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
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ Неверный ID темы.",
                    )
                ]

            topic = await question_repo.get_topic_by_id(topic_id)
            if topic is None:
                return [
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ Тема не найдена.",
                    )
                ]

            user = await user_repo.ensure_exists(telegram_id)

            if topic.created_by is not None and topic.created_by != user.id:
                return [
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="🚫 Удалять можно только созданные вами темы.",
                    )
                ]

            await question_repo.soft_delete_topic(topic_id)

            logger.info(
                "Topic %s soft-deleted by user %s",
                topic_id,
                telegram_id,
            )

            return [
                game.utils.service_result(
                    chat_id,
                    game.constants.ViewName.PLAIN,
                    text=(
                        f"🗑 Тема «{topic.title}» скрыта. "
                        f"Восстановить: /restore_topic"
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
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="📭 Нет тем с вопросами для удаления.",
                    )
                ]

            return [
                game.utils.service_result(
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
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ Неверный ID темы.",
                    )
                ]

            questions = await question_repo.get_questions_by_topic(topic_id)
            if not questions:
                return [
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="📭 В этой теме нет вопросов.",
                    )
                ]

            return [
                game.utils.service_result(
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
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ Неверный ID вопроса.",
                    )
                ]

            question = await question_repo.get_question_by_id(question_id)
            if question is None:
                return [
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ Вопрос не найден.",
                    )
                ]

            user = await user_repo.ensure_exists(telegram_id)

            if (
                question.created_by is not None
                and question.created_by != user.id
            ):
                return [
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="🚫 Удалять можно только созданные вами вопросы.",
                    )
                ]

            await question_repo.soft_delete_question(question_id)

            logger.info(
                "Question %s soft-deleted by user %s",
                question_id,
                telegram_id,
            )

            return [
                game.utils.service_result(
                    chat_id,
                    game.constants.ViewName.PLAIN,
                    text=("🗑 Вопрос скрыт. Восстановить: /restore_question"),
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

            user = await user_repo.ensure_exists(telegram_id)

            hosted = await game_repo.get_hosted_with_player_counts(user.id)
            if not hosted:
                return [
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="🎮 Нет активных игр, где вы ведущий.",
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
                game.utils.service_result(
                    chat_id,
                    game.constants.ViewName.MY_GAMES,
                    games=games_payload,
                )
            ]

    async def handle_help(
        self,
        chat_id: int,
    ) -> list[game.schemas.ServiceResponse]:
        return [
            game.utils.service_result(chat_id, game.constants.ViewName.HELP)
        ]

    async def handle_rules(
        self,
        chat_id: int,
    ) -> list[game.schemas.ServiceResponse]:
        return [
            game.utils.service_result(
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

            user = await user_repo.ensure_exists(telegram_id)

            hidden = await question_repo.hidden_topics_for_user(user.id)
            if not hidden:
                return [
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="📭 Нет скрытых тем для восстановления.",
                    )
                ]

            return [
                game.utils.service_result(
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
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ Неверный ID темы.",
                    )
                ]

            topic = await question_repo.get_topic_by_id(topic_id)
            if topic is None:
                return [
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ Тема не найдена.",
                    )
                ]

            user = await user_repo.ensure_exists(telegram_id)

            if topic.created_by is not None and topic.created_by != user.id:
                return [
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text=(
                            "🚫 Восстанавливать можно только "
                            "созданные вами темы."
                        ),
                    )
                ]

            await question_repo.restore_topic(topic_id)

            logger.info(
                "Topic %s restored by user %s",
                topic_id,
                telegram_id,
            )

            return [
                game.utils.service_result(
                    chat_id,
                    game.constants.ViewName.PLAIN,
                    text=f"✅ Тема «{topic.title}» восстановлена!",
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

            user = await user_repo.ensure_exists(telegram_id)

            hidden = await question_repo.hidden_questions_for_user(user.id)
            if not hidden:
                return [
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="📭 Нет скрытых вопросов для восстановления.",
                    )
                ]

            return [
                game.utils.service_result(
                    chat_id,
                    game.constants.ViewName.QUESTION_SELECT_FOR_RESTORE,
                    questions=hidden,
                )
            ]

    @staticmethod
    def _parse_csv_rows(
        csv_text: str,
        max_rows: int,
    ) -> tuple[list[tuple[str, str, str, int]], list[str]] | None:
        reader = csv.DictReader(io.StringIO(csv_text))
        required = {"topic", "question", "answer", "cost"}
        if not reader.fieldnames or not required.issubset(
            {f.strip().lower() for f in reader.fieldnames}
        ):
            return None

        field_map = {f.strip().lower(): f for f in reader.fieldnames}
        errors: list[str] = []
        valid: list[tuple[str, str, str, int]] = []

        for i, row in enumerate(reader, start=2):
            if len(valid) >= max_rows:
                errors.append(
                    f"Row {i}: max {max_rows} rows exceeded, "
                    f"remaining rows skipped"
                )
                break
            parsed = _parse_csv_row(row, field_map, i)
            if isinstance(parsed, str):
                errors.append(parsed)
            else:
                valid.append(parsed)

        return valid, errors

    async def handle_csv_upload(
        self,
        chat_id: int,
        telegram_id: int,
        csv_content: bytes,
    ) -> list[game.schemas.ServiceResponse]:
        try:
            text = csv_content.decode("utf-8-sig")
        except UnicodeDecodeError:
            return [
                game.utils.service_result(
                    chat_id,
                    game.constants.ViewName.PLAIN,
                    text="⚠️ Не удалось прочитать файл. Используйте UTF-8.",
                )
            ]

        parsed = self._parse_csv_rows(text, self._max_csv_rows)
        if parsed is None:
            return [
                game.utils.service_result(
                    chat_id,
                    game.constants.ViewName.PLAIN,
                    text=(
                        "⚠️ CSV должен содержать столбцы: "
                        "topic, question, answer, cost"
                    ),
                )
            ]

        valid_rows, errors = parsed

        if not valid_rows:
            return [
                game.utils.service_result(
                    chat_id,
                    game.constants.ViewName.PLAIN,
                    text=(
                        "⚠️ Нет валидных строк для импорта."
                        + (
                            "\n\nОшибки:\n" + "\n".join(errors[:10])
                            if errors
                            else ""
                        )
                    ),
                )
            ]

        db_rows = await self._import_csv_rows(telegram_id, chat_id, valid_rows)
        if (
            isinstance(db_rows, list)
            and db_rows
            and isinstance(db_rows[0], game.schemas.ServiceResponse)
        ):
            return db_rows

        logger.info(
            "CSV upload by user %s: %d questions imported, %d errors",
            telegram_id,
            len(db_rows),
            len(errors),
        )

        return [
            game.utils.service_result(
                chat_id,
                game.constants.ViewName.CSV_UPLOAD_RESULT,
                created=len(db_rows),
                errors=errors,
            )
        ]

    async def _import_csv_rows(
        self,
        telegram_id: int,
        chat_id: int,
        valid_rows: list[tuple[str, str, str, int]],
    ) -> list:
        async with self._session_factory() as session, session.begin():
            user_repo = db.repositories.user.UserRepository(session)
            user = await user_repo.ensure_exists(telegram_id)

            topic_cache: dict[str, uuid.UUID] = {}
            db_rows: list[tuple[uuid.UUID, str, str, int]] = []

            for topic_title, q_text, a_text, cost in valid_rows:
                tid = await self._resolve_topic(
                    session,
                    topic_cache,
                    topic_title,
                    user,
                )
                db_rows.append((tid, q_text, a_text, cost))

            for topic_id, qtext, a_text, cost in db_rows:
                session.add(
                    game.models.QuestionModel(
                        topic_id=topic_id,
                        text=qtext,
                        answer=a_text,
                        cost=cost,
                        created_by=user.id,
                        normalized_answer=game.answer_similarity.normalize_answer_text(
                            a_text
                        ),
                    )
                )

        return db_rows

    @staticmethod
    async def _resolve_topic(
        session: sqlalchemy.ext.asyncio.AsyncSession,
        cache: dict[str, uuid.UUID],
        title: str,
        user: game.models.UserModel | None,
    ) -> uuid.UUID:
        if title in cache:
            return cache[title]
        existing = (
            await session.execute(
                sqlalchemy.select(game.models.TopicModel).where(
                    game.models.TopicModel.title == title,
                )
            )
        ).scalar_one_or_none()
        if existing:
            cache[title] = existing.id
            return existing.id
        new_topic = game.models.TopicModel(
            title=title,
            created_by=user.id if user is not None else None,
        )
        session.add(new_topic)
        await session.flush()
        cache[title] = new_topic.id
        return new_topic.id

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
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ Неверный ID вопроса.",
                    )
                ]

            question = await question_repo.get_question_by_id(question_id)
            if question is None:
                return [
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ Вопрос не найден.",
                    )
                ]

            user = await user_repo.ensure_exists(telegram_id)

            if (
                question.created_by is not None
                and question.created_by != user.id
            ):
                return [
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text=(
                            "🚫 Восстанавливать можно только "
                            "созданные вами вопросы."
                        ),
                    )
                ]

            await question_repo.restore_question(question_id)

            logger.info(
                "Question %s restored by user %s",
                question_id,
                telegram_id,
            )

            return [
                game.utils.service_result(
                    chat_id,
                    game.constants.ViewName.PLAIN,
                    text="✅ Вопрос восстановлен!",
                )
            ]

    async def handle_my_content(
        self,
        chat_id: int,
        telegram_id: int,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            user_repo = db.repositories.user.UserRepository(session)
            question_repo = db.repositories.question.QuestionRepository(session)

            user = await user_repo.ensure_exists(telegram_id)

            topics = await question_repo.topics_by_creator(user.id)
            if not topics:
                return [
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text=(
                            "📭 У вас пока нет тем. "
                            "Создайте тему: /add_topic <название>"
                        ),
                    )
                ]

            return [
                game.utils.service_result(
                    chat_id,
                    game.constants.ViewName.MY_CONTENT_TOPICS,
                    topics_with_counts=topics,
                )
            ]

    async def handle_my_content_topic(
        self,
        chat_id: int,
        telegram_id: int,
        topic_id_str: str,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            user_repo = db.repositories.user.UserRepository(session)
            question_repo = db.repositories.question.QuestionRepository(session)

            user = await user_repo.ensure_exists(telegram_id)

            try:
                topic_id = uuid.UUID(topic_id_str)
            except ValueError:
                return [
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ Неверный ID темы.",
                    )
                ]

            (
                topic,
                questions,
            ) = await question_repo.questions_by_creator_in_topic(
                user.id, topic_id
            )

            if topic is None:
                return [
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ Тема не найдена.",
                    )
                ]

            return [
                game.utils.service_result(
                    chat_id,
                    game.constants.ViewName.MY_CONTENT_QUESTIONS,
                    topic_title=topic.title,
                    topic_id=str(topic.id),
                    questions=questions,
                )
            ]

    async def handle_my_content_question(
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
                return [
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ Неверный ID вопроса.",
                    )
                ]

            question = await question_repo.get_question_by_id(question_id)
            if question is None:
                return [
                    game.utils.service_result(
                        chat_id,
                        game.constants.ViewName.PLAIN,
                        text="⚠️ Вопрос не найден.",
                    )
                ]

            topic = await question_repo.get_topic_by_id(question.topic_id)
            topic_title = topic.title if topic else "?"

            return [
                game.utils.service_result(
                    chat_id,
                    game.constants.ViewName.MY_CONTENT_QUESTION_DETAIL,
                    topic_title=topic_title,
                    topic_id=str(question.topic_id),
                    question_text=question.text,
                    question_answer=question.answer,
                    question_cost=question.cost,
                )
            ]
