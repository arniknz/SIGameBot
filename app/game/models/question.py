from __future__ import annotations

import datetime
import typing
import uuid

import game.base
import game.constants
import sqlalchemy
import sqlalchemy.dialects.postgresql
import sqlalchemy.orm

if typing.TYPE_CHECKING:
    import game.models.game

    GameModel = game.models.game.GameModel


class TopicModel(game.base.Base):
    __tablename__ = "topics"

    id: sqlalchemy.orm.Mapped[uuid.UUID] = sqlalchemy.orm.mapped_column(
        sqlalchemy.dialects.postgresql.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(
        sqlalchemy.Text,
        unique=True,
        nullable=False,
    )
    is_visible: sqlalchemy.orm.Mapped[bool] = sqlalchemy.orm.mapped_column(
        sqlalchemy.Boolean,
        default=True,
        server_default="true",
    )
    created_by: sqlalchemy.orm.Mapped[int | None] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.BigInteger,
            sqlalchemy.ForeignKey("users.id", ondelete="SET NULL"),
        )
    )

    questions: sqlalchemy.orm.Mapped[list[QuestionModel]] = (
        sqlalchemy.orm.relationship(
            back_populates="topic",
        )
    )


class QuestionModel(game.base.Base):
    __tablename__ = "questions"
    __table_args__ = (
        sqlalchemy.CheckConstraint("cost > 0", name="ck_question_cost"),
    )

    id: sqlalchemy.orm.Mapped[uuid.UUID] = sqlalchemy.orm.mapped_column(
        sqlalchemy.dialects.postgresql.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    topic_id: sqlalchemy.orm.Mapped[uuid.UUID] = sqlalchemy.orm.mapped_column(
        sqlalchemy.dialects.postgresql.UUID(as_uuid=True),
        sqlalchemy.ForeignKey("topics.id"),
        nullable=False,
    )
    text: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(
        sqlalchemy.Text,
        nullable=False,
    )
    answer: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(
        sqlalchemy.Text,
        nullable=False,
    )
    normalized_answer: sqlalchemy.orm.Mapped[str | None] = (
        sqlalchemy.orm.mapped_column(sqlalchemy.Text, nullable=True)
    )
    cost: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.Integer,
        nullable=False,
    )
    is_visible: sqlalchemy.orm.Mapped[bool] = sqlalchemy.orm.mapped_column(
        sqlalchemy.Boolean,
        default=True,
        server_default="true",
    )
    created_by: sqlalchemy.orm.Mapped[int | None] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.BigInteger,
            sqlalchemy.ForeignKey("users.id", ondelete="SET NULL"),
        )
    )

    topic: sqlalchemy.orm.Mapped[TopicModel] = sqlalchemy.orm.relationship(
        back_populates="questions",
    )


class QuestionInGameModel(game.base.Base):
    __tablename__ = "questions_in_game"
    __table_args__ = (
        sqlalchemy.UniqueConstraint(
            "game_id", "question_id", name="uq_game_question"
        ),
    )

    id: sqlalchemy.orm.Mapped[uuid.UUID] = sqlalchemy.orm.mapped_column(
        sqlalchemy.dialects.postgresql.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    game_id: sqlalchemy.orm.Mapped[uuid.UUID] = sqlalchemy.orm.mapped_column(
        sqlalchemy.dialects.postgresql.UUID(as_uuid=True),
        sqlalchemy.ForeignKey("games.id"),
        nullable=False,
    )
    question_id: sqlalchemy.orm.Mapped[uuid.UUID] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.dialects.postgresql.UUID(as_uuid=True),
            sqlalchemy.ForeignKey("questions.id"),
            nullable=False,
        )
    )
    status: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(
        sqlalchemy.String(20),
        default=game.constants.QuestionInGameStatus.PENDING.value,
    )
    asked_by: sqlalchemy.orm.Mapped[uuid.UUID | None] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.dialects.postgresql.UUID(as_uuid=True),
            sqlalchemy.ForeignKey("participants.id"),
        )
    )
    answered_by: sqlalchemy.orm.Mapped[uuid.UUID | None] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.dialects.postgresql.UUID(as_uuid=True),
            sqlalchemy.ForeignKey("participants.id"),
        )
    )
    asked_at: sqlalchemy.orm.Mapped[datetime.datetime | None] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.DateTime(timezone=True),
        )
    )
    answered_at: sqlalchemy.orm.Mapped[datetime.datetime | None] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.DateTime(timezone=True),
        )
    )

    game: sqlalchemy.orm.Mapped[GameModel] = sqlalchemy.orm.relationship(
        back_populates="questions_in_game",
    )
    question: sqlalchemy.orm.Mapped[QuestionModel] = (
        sqlalchemy.orm.relationship()
    )
