from __future__ import annotations

import uuid

import game.models
import sqlalchemy
import sqlalchemy.ext.asyncio
import game.constants


class QuestionRepository:
    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession) -> None:
        self._session = session

    async def create_topic(
        self,
        title: str,
    ) -> game.models.TopicModel:
        topic = game.models.TopicModel(title=title)
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
        statement = sqlalchemy.select(game.models.TopicModel).order_by(
            game.models.TopicModel.title,
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
    ) -> game.models.QuestionModel:
        question = game.models.QuestionModel(
            topic_id=topic_id,
            text=text,
            answer=answer,
            cost=cost,
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
            .where(game.models.QuestionModel.topic_id == topic_id)
            .order_by(game.models.QuestionModel.cost)
        )
        return list((await self._session.execute(statement)).scalars().all())

    async def all_question_ids(self) -> list[uuid.UUID]:
        statement = sqlalchemy.select(game.models.QuestionModel.id)
        rows = await self._session.execute(statement)
        return [row[0] for row in rows.all()]

    async def delete_question(
        self,
        question_id: uuid.UUID,
    ) -> bool:
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
                .where(game.models.QuestionModel.topic_id == topic_id),
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

    async def get_pending_board(
        self,
        game_id: uuid.UUID,
    ) -> list[tuple]:
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
    ) -> tuple | None:
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

    async def topics_with_question_counts(
        self,
    ) -> list[tuple[game.models.TopicModel, int]]:
        statement = (
            sqlalchemy.select(
                game.models.TopicModel,
                sqlalchemy.func.count(game.models.QuestionModel.id),
            )
            .outerjoin(
                game.models.QuestionModel,
                game.models.QuestionModel.topic_id == game.models.TopicModel.id,
            )
            .group_by(game.models.TopicModel.id)
            .order_by(game.models.TopicModel.title)
        )
        return list((await self._session.execute(statement)).all())
