from __future__ import annotations

import uuid

import game.constants
import game.models
import sqlalchemy
import sqlalchemy.ext.asyncio


class QuestionRepository:
    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession) -> None:
        self._session = session

    async def create_topic(
        self,
        title: str,
        created_by: int | None = None,
    ) -> game.models.TopicModel:
        topic = game.models.TopicModel(title=title, created_by=created_by)
        self._session.add(topic)
        await self._session.flush()
        return topic

    async def get_topic_by_title(
        self,
        title: str,
    ) -> game.models.TopicModel | None:
        statement = sqlalchemy.select(game.models.TopicModel).where(
            game.models.TopicModel.title == title,
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def all_topics(self) -> list[game.models.TopicModel]:
        statement = (
            sqlalchemy.select(game.models.TopicModel)
            .where(game.models.TopicModel.is_visible.is_(True))
            .order_by(game.models.TopicModel.title)
        )
        return list((await self._session.execute(statement)).scalars().all())

    async def delete_topic(
        self,
        topic_id: uuid.UUID,
    ) -> int:
        deleted_question_count = (
            await self._session.execute(
                sqlalchemy.select(sqlalchemy.func.count())
                .select_from(game.models.QuestionModel)
                .where(game.models.QuestionModel.topic_id == topic_id),
            )
        ).scalar_one()

        question_ids_stmt = sqlalchemy.select(
            game.models.QuestionModel.id
        ).where(game.models.QuestionModel.topic_id == topic_id)
        question_ids = [
            row[0]
            for row in (await self._session.execute(question_ids_stmt)).all()
        ]

        if question_ids:
            qig_ids_stmt = sqlalchemy.select(
                game.models.QuestionInGameModel.id
            ).where(
                game.models.QuestionInGameModel.question_id.in_(question_ids),
            )
            qig_ids = [
                row[0]
                for row in (await self._session.execute(qig_ids_stmt)).all()
            ]
            if qig_ids:
                await self._session.execute(
                    sqlalchemy.delete(game.models.GameItemUsageModel).where(
                        game.models.GameItemUsageModel.question_in_game_id.in_(
                            qig_ids
                        ),
                    )
                )
                await self._session.execute(
                    sqlalchemy.update(game.models.GameStateModel)
                    .where(
                        game.models.GameStateModel.current_question_id.in_(
                            qig_ids
                        ),
                    )
                    .values(current_question_id=None)
                )
            await self._session.execute(
                sqlalchemy.delete(game.models.QuestionInGameModel).where(
                    game.models.QuestionInGameModel.question_id.in_(
                        question_ids
                    ),
                )
            )
            await self._session.execute(
                sqlalchemy.delete(game.models.QuestionModel).where(
                    game.models.QuestionModel.topic_id == topic_id,
                )
            )

        await self._session.execute(
            sqlalchemy.delete(game.models.TopicModel).where(
                game.models.TopicModel.id == topic_id
            ),
        )
        return deleted_question_count

    async def create_question(
        self,
        topic_id: uuid.UUID,
        text: str,
        answer: str,
        cost: int,
        created_by: int | None = None,
        *,
        normalized_answer: str | None = None,
    ) -> game.models.QuestionModel:
        question = game.models.QuestionModel(
            topic_id=topic_id,
            text=text,
            answer=answer,
            cost=cost,
            created_by=created_by,
            normalized_answer=normalized_answer,
        )
        self._session.add(question)
        await self._session.flush()
        return question

    async def get_questions_by_topic(
        self,
        topic_id: uuid.UUID,
    ) -> list[game.models.QuestionModel]:
        statement = (
            sqlalchemy.select(game.models.QuestionModel)
            .where(
                game.models.QuestionModel.topic_id == topic_id,
                game.models.QuestionModel.is_visible.is_(True),
            )
            .order_by(game.models.QuestionModel.cost)
        )
        return list((await self._session.execute(statement)).scalars().all())

    async def all_question_ids(self) -> list[uuid.UUID]:
        statement = (
            sqlalchemy.select(game.models.QuestionModel.id)
            .join(
                game.models.TopicModel,
                game.models.QuestionModel.topic_id == game.models.TopicModel.id,
            )
            .where(
                game.models.QuestionModel.is_visible.is_(True),
                game.models.TopicModel.is_visible.is_(True),
            )
        )
        rows = await self._session.execute(statement)
        return [row[0] for row in rows.all()]

    async def delete_question(
        self,
        question_id: uuid.UUID,
    ) -> bool:
        qig_ids_stmt = sqlalchemy.select(
            game.models.QuestionInGameModel.id
        ).where(
            game.models.QuestionInGameModel.question_id == question_id,
        )
        qig_ids = [
            row[0] for row in (await self._session.execute(qig_ids_stmt)).all()
        ]

        if qig_ids:
            await self._session.execute(
                sqlalchemy.delete(game.models.GameItemUsageModel).where(
                    game.models.GameItemUsageModel.question_in_game_id.in_(
                        qig_ids
                    ),
                )
            )
            await self._session.execute(
                sqlalchemy.update(game.models.GameStateModel)
                .where(
                    game.models.GameStateModel.current_question_id.in_(qig_ids),
                )
                .values(current_question_id=None)
            )
            await self._session.execute(
                sqlalchemy.delete(game.models.QuestionInGameModel).where(
                    game.models.QuestionInGameModel.question_id == question_id,
                )
            )

        result = await self._session.execute(
            sqlalchemy.delete(game.models.QuestionModel).where(
                game.models.QuestionModel.id == question_id
            ),
        )
        return result.rowcount > 0

    async def question_count_by_topic(
        self,
        topic_id: uuid.UUID,
    ) -> int:
        return (
            await self._session.execute(
                sqlalchemy.select(sqlalchemy.func.count())
                .select_from(game.models.QuestionModel)
                .where(
                    game.models.QuestionModel.topic_id == topic_id,
                    game.models.QuestionModel.is_visible.is_(True),
                ),
            )
        ).scalar_one()

    async def bulk_create_questions_in_game(
        self,
        game_id: uuid.UUID,
        question_ids: list[uuid.UUID],
    ) -> None:
        rows = [
            {"game_id": game_id, "question_id": question_id}
            for question_id in question_ids
        ]
        if not rows:
            return
        await self._session.execute(
            sqlalchemy.insert(game.models.QuestionInGameModel),
            rows,
        )

    async def get_random_pending(
        self,
        game_id: uuid.UUID,
    ) -> (
        sqlalchemy.Row[
            tuple[
                game.models.QuestionInGameModel,
                str,
                str,
                str,
                int,
            ]
        ]
        | None
    ):
        statement = (
            sqlalchemy.select(
                game.models.QuestionInGameModel,
                game.models.TopicModel.title,
                game.models.QuestionModel.text,
                game.models.QuestionModel.answer,
                game.models.QuestionModel.cost,
            )
            .join(
                game.models.QuestionModel,
                game.models.QuestionInGameModel.question_id
                == game.models.QuestionModel.id,
            )
            .join(
                game.models.TopicModel,
                game.models.QuestionModel.topic_id == game.models.TopicModel.id,
            )
            .where(
                game.models.QuestionInGameModel.game_id == game_id,
                game.models.QuestionInGameModel.status
                == game.constants.QuestionInGameStatus.PENDING,
            )
            .order_by(sqlalchemy.func.random())
            .limit(1)
        )
        return (await self._session.execute(statement)).one_or_none()

    async def get_pending_board(
        self,
        game_id: uuid.UUID,
    ) -> list[sqlalchemy.Row[tuple[uuid.UUID, str, int, str, str]]]:
        statement = (
            sqlalchemy.select(
                game.models.QuestionInGameModel.id,
                game.models.TopicModel.title,
                game.models.QuestionModel.cost,
                game.models.QuestionModel.text,
                game.models.QuestionModel.answer,
            )
            .join(
                game.models.QuestionModel,
                game.models.QuestionInGameModel.question_id
                == game.models.QuestionModel.id,
            )
            .join(
                game.models.TopicModel,
                game.models.QuestionModel.topic_id == game.models.TopicModel.id,
            )
            .where(
                game.models.QuestionInGameModel.game_id == game_id,
                game.models.QuestionInGameModel.status
                == game.constants.QuestionInGameStatus.PENDING,
            )
            .order_by(
                game.models.TopicModel.title, game.models.QuestionModel.cost
            )
        )
        return list((await self._session.execute(statement)).all())

    async def get_question_in_game_detail(
        self,
        question_in_game_id: uuid.UUID,
    ) -> (
        sqlalchemy.Row[
            tuple[
                game.models.QuestionInGameModel,
                str,
                str,
                str,
                int,
            ]
        ]
        | None
    ):
        statement = (
            sqlalchemy.select(
                game.models.QuestionInGameModel,
                game.models.TopicModel.title,
                game.models.QuestionModel.text,
                game.models.QuestionModel.answer,
                game.models.QuestionModel.cost,
            )
            .join(
                game.models.QuestionModel,
                game.models.QuestionInGameModel.question_id
                == game.models.QuestionModel.id,
            )
            .join(
                game.models.TopicModel,
                game.models.QuestionModel.topic_id == game.models.TopicModel.id,
            )
            .where(game.models.QuestionInGameModel.id == question_in_game_id)
        )
        return (await self._session.execute(statement)).one_or_none()

    async def get_answered_in_game(
        self,
        game_id: uuid.UUID,
    ) -> list[game.models.QuestionInGameModel]:
        statement = sqlalchemy.select(game.models.QuestionInGameModel).where(
            game.models.QuestionInGameModel.game_id == game_id,
            game.models.QuestionInGameModel.status
            == game.constants.QuestionInGameStatus.ANSWERED,
        )
        return list((await self._session.execute(statement)).scalars().all())

    async def topics_with_question_counts(
        self,
    ) -> list[sqlalchemy.Row[tuple[game.models.TopicModel, int]]]:
        statement = (
            sqlalchemy.select(
                game.models.TopicModel,
                sqlalchemy.func.count(game.models.QuestionModel.id),
            )
            .outerjoin(
                game.models.QuestionModel,
                sqlalchemy.and_(
                    game.models.QuestionModel.topic_id
                    == game.models.TopicModel.id,
                    game.models.QuestionModel.is_visible.is_(True),
                ),
            )
            .where(game.models.TopicModel.is_visible.is_(True))
            .group_by(game.models.TopicModel.id)
            .order_by(game.models.TopicModel.title)
        )
        return list((await self._session.execute(statement)).all())

    async def get_topic_by_id(
        self,
        topic_id: uuid.UUID,
    ) -> game.models.TopicModel | None:
        return await self._session.get(game.models.TopicModel, topic_id)

    async def get_question_by_id(
        self,
        question_id: uuid.UUID,
    ) -> game.models.QuestionModel | None:
        return await self._session.get(game.models.QuestionModel, question_id)

    async def soft_delete_topic(
        self,
        topic_id: uuid.UUID,
    ) -> bool:
        topic = await self.get_topic_by_id(topic_id)
        if topic is None:
            return False
        topic.is_visible = False
        await self._session.execute(
            sqlalchemy.update(game.models.QuestionModel)
            .where(game.models.QuestionModel.topic_id == topic_id)
            .values(is_visible=False)
        )
        return True

    async def soft_delete_question(
        self,
        question_id: uuid.UUID,
    ) -> bool:
        question = await self.get_question_by_id(question_id)
        if question is None:
            return False
        question.is_visible = False
        return True

    async def restore_topic(
        self,
        topic_id: uuid.UUID,
    ) -> bool:
        topic = await self.get_topic_by_id(topic_id)
        if topic is None:
            return False
        topic.is_visible = True
        await self._session.execute(
            sqlalchemy.update(game.models.QuestionModel)
            .where(game.models.QuestionModel.topic_id == topic_id)
            .values(is_visible=True)
        )
        return True

    async def restore_question(
        self,
        question_id: uuid.UUID,
    ) -> bool:
        question = await self.get_question_by_id(question_id)
        if question is None:
            return False
        question.is_visible = True
        return True

    async def hidden_topics_for_user(
        self,
        user_id: int,
    ) -> list[game.models.TopicModel]:
        statement = (
            sqlalchemy.select(game.models.TopicModel)
            .where(
                game.models.TopicModel.is_visible.is_(False),
                game.models.TopicModel.created_by == user_id,
            )
            .order_by(game.models.TopicModel.title)
        )
        return list((await self._session.execute(statement)).scalars().all())

    async def hidden_questions_for_user(
        self,
        user_id: int,
    ) -> list[sqlalchemy.Row[tuple[game.models.QuestionModel, str]]]:
        statement = (
            sqlalchemy.select(
                game.models.QuestionModel,
                game.models.TopicModel.title,
            )
            .join(
                game.models.TopicModel,
                game.models.QuestionModel.topic_id == game.models.TopicModel.id,
            )
            .where(
                game.models.QuestionModel.is_visible.is_(False),
                game.models.QuestionModel.created_by == user_id,
            )
            .order_by(
                game.models.TopicModel.title,
                game.models.QuestionModel.cost,
            )
        )
        return list((await self._session.execute(statement)).all())

    async def topics_by_creator(
        self,
        user_id: int,
    ) -> list[sqlalchemy.Row[tuple[game.models.TopicModel, int]]]:
        user_q_count = sqlalchemy.func.count(
            game.models.QuestionModel.id
        )
        statement = (
            sqlalchemy.select(
                game.models.TopicModel,
                user_q_count,
            )
            .outerjoin(
                game.models.QuestionModel,
                sqlalchemy.and_(
                    game.models.QuestionModel.topic_id
                    == game.models.TopicModel.id,
                    game.models.QuestionModel.is_visible.is_(True),
                    game.models.QuestionModel.created_by == user_id,
                ),
            )
            .where(
                game.models.TopicModel.is_visible.is_(True),
            )
            .group_by(game.models.TopicModel.id)
            .having(
                sqlalchemy.or_(
                    game.models.TopicModel.created_by == user_id,
                    user_q_count > 0,
                )
            )
            .order_by(game.models.TopicModel.title)
        )
        return list((await self._session.execute(statement)).all())

    async def questions_by_creator_in_topic(
        self,
        user_id: int,
        topic_id: uuid.UUID,
    ) -> tuple[
        game.models.TopicModel | None,
        list[game.models.QuestionModel],
    ]:
        topic = await self.get_topic_by_id(topic_id)
        statement = (
            sqlalchemy.select(game.models.QuestionModel)
            .where(
                game.models.QuestionModel.topic_id == topic_id,
                game.models.QuestionModel.created_by == user_id,
                game.models.QuestionModel.is_visible.is_(True),
            )
            .order_by(game.models.QuestionModel.cost)
        )
        questions = list(
            (await self._session.execute(statement)).scalars().all()
        )
        return topic, questions
