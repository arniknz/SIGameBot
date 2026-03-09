from __future__ import annotations

import datetime
import uuid

import sqlalchemy
import sqlalchemy.dialects.postgresql
import sqlalchemy.orm


class Base(sqlalchemy.orm.DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"

    id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    telegram_id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.BigInteger,
        unique=True,
        nullable=False,
    )
    username: sqlalchemy.orm.Mapped[str | None] = sqlalchemy.orm.mapped_column(
        sqlalchemy.String(255),
    )
    created_at: sqlalchemy.orm.Mapped[datetime.datetime] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.DateTime(timezone=True),
            default=lambda: datetime.datetime.now(datetime.UTC),
        )
    )

    participants: sqlalchemy.orm.Mapped[list[ParticipantModel]] = (
        sqlalchemy.orm.relationship(
            back_populates="user",
        )
    )


class GameModel(Base):
    __tablename__ = "games"

    id: sqlalchemy.orm.Mapped[uuid.UUID] = sqlalchemy.orm.mapped_column(
        sqlalchemy.dialects.postgresql.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    chat_id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.BigInteger,
        nullable=False,
    )
    status: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(
        sqlalchemy.String(20),
        default="waiting",
    )
    current_player_id: sqlalchemy.orm.Mapped[uuid.UUID | None] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.dialects.postgresql.UUID(as_uuid=True),
            sqlalchemy.ForeignKey("participants.id"),
        )
    )
    host_id: sqlalchemy.orm.Mapped[int | None] = sqlalchemy.orm.mapped_column(
        sqlalchemy.BigInteger,
        sqlalchemy.ForeignKey("users.id"),
    )
    created_at: sqlalchemy.orm.Mapped[datetime.datetime] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.DateTime(timezone=True),
            default=lambda: datetime.datetime.now(datetime.UTC),
        )
    )
    finished_at: sqlalchemy.orm.Mapped[datetime.datetime | None] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.DateTime(timezone=True),
        )
    )

    participants: sqlalchemy.orm.Mapped[list[ParticipantModel]] = (
        sqlalchemy.orm.relationship(
            back_populates="game",
            foreign_keys="ParticipantModel.game_id",
        )
    )
    state: sqlalchemy.orm.Mapped[GameStateModel | None] = (
        sqlalchemy.orm.relationship(
            back_populates="game",
        )
    )
    questions_in_game: sqlalchemy.orm.Mapped[list[QuestionInGameModel]] = (
        sqlalchemy.orm.relationship(
            back_populates="game",
        )
    )


class ParticipantModel(Base):
    __tablename__ = "participants"
    __table_args__ = (
        sqlalchemy.UniqueConstraint("game_id", "user_id", name="uq_game_user"),
    )

    id: sqlalchemy.orm.Mapped[uuid.UUID] = sqlalchemy.orm.mapped_column(
        sqlalchemy.dialects.postgresql.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.BigInteger,
        sqlalchemy.ForeignKey("users.id"),
        nullable=False,
    )
    game_id: sqlalchemy.orm.Mapped[uuid.UUID] = sqlalchemy.orm.mapped_column(
        sqlalchemy.dialects.postgresql.UUID(as_uuid=True),
        sqlalchemy.ForeignKey("games.id"),
        nullable=False,
    )
    role: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(
        sqlalchemy.String(20),
        nullable=False,
        default="player",
    )
    score: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.Integer,
        default=0,
    )
    joined_at: sqlalchemy.orm.Mapped[datetime.datetime] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.DateTime(timezone=True),
            default=lambda: datetime.datetime.now(datetime.UTC),
        )
    )
    is_active: sqlalchemy.orm.Mapped[bool] = sqlalchemy.orm.mapped_column(
        sqlalchemy.Boolean,
        default=True,
    )

    user: sqlalchemy.orm.Mapped[UserModel] = sqlalchemy.orm.relationship(
        back_populates="participants",
    )
    game: sqlalchemy.orm.Mapped[GameModel] = sqlalchemy.orm.relationship(
        back_populates="participants",
        foreign_keys=[game_id],
    )


class TopicModel(Base):
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

    questions: sqlalchemy.orm.Mapped[list[QuestionModel]] = (
        sqlalchemy.orm.relationship(
            back_populates="topic",
        )
    )


class QuestionModel(Base):
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
    cost: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.Integer,
        nullable=False,
    )

    topic: sqlalchemy.orm.Mapped[TopicModel] = sqlalchemy.orm.relationship(
        back_populates="questions",
    )


class QuestionInGameModel(Base):
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
        default="pending",
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


class GameStateModel(Base):
    __tablename__ = "game_states"

    id: sqlalchemy.orm.Mapped[uuid.UUID] = sqlalchemy.orm.mapped_column(
        sqlalchemy.dialects.postgresql.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    game_id: sqlalchemy.orm.Mapped[uuid.UUID] = sqlalchemy.orm.mapped_column(
        sqlalchemy.dialects.postgresql.UUID(as_uuid=True),
        sqlalchemy.ForeignKey("games.id"),
        unique=True,
        nullable=False,
    )
    status: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(
        sqlalchemy.String(20),
    )
    current_question_id: sqlalchemy.orm.Mapped[uuid.UUID | None] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.dialects.postgresql.UUID(as_uuid=True),
            sqlalchemy.ForeignKey("questions_in_game.id"),
        )
    )
    buzzer_pressed_by: sqlalchemy.orm.Mapped[uuid.UUID | None] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.dialects.postgresql.UUID(as_uuid=True),
            sqlalchemy.ForeignKey("participants.id"),
        )
    )
    buzzer_pressed_at: sqlalchemy.orm.Mapped[datetime.datetime | None] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.DateTime(timezone=True),
        )
    )
    timer_ends_at: sqlalchemy.orm.Mapped[datetime.datetime | None] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.DateTime(timezone=True),
        )
    )
    updated_at: sqlalchemy.orm.Mapped[datetime.datetime] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.DateTime(timezone=True),
            default=lambda: datetime.datetime.now(datetime.UTC),
            onupdate=lambda: datetime.datetime.now(datetime.UTC),
        )
    )

    game: sqlalchemy.orm.Mapped[GameModel] = sqlalchemy.orm.relationship(
        back_populates="state",
    )
