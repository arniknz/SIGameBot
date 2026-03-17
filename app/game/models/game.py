from __future__ import annotations

import datetime
import typing
import uuid

import game.constants
import game.models.base
import sqlalchemy
import sqlalchemy.dialects.postgresql
import sqlalchemy.orm

if typing.TYPE_CHECKING:
    import game.models.question
    import game.models.user

    QuestionInGameModel = game.models.question.QuestionInGameModel
    UserModel = game.models.user.UserModel


class GameModel(game.models.base.Base):
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
        default=game.constants.GameStatus.WAITING.value,
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


class ParticipantModel(game.models.base.Base):
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
        default=game.constants.ParticipantRole.PLAYER.value,
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
    all_in_used: sqlalchemy.orm.Mapped[bool] = sqlalchemy.orm.mapped_column(
        sqlalchemy.Boolean,
        default=False,
    )

    user: sqlalchemy.orm.Mapped[UserModel] = sqlalchemy.orm.relationship(
        back_populates="participants",
    )
    game: sqlalchemy.orm.Mapped[GameModel] = sqlalchemy.orm.relationship(
        back_populates="participants",
        foreign_keys=[game_id],
    )


class GameStateModel(game.models.base.Base):
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
    cost_override: sqlalchemy.orm.Mapped[int | None] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.Integer,
        )
    )
    all_in_active: sqlalchemy.orm.Mapped[bool] = sqlalchemy.orm.mapped_column(
        sqlalchemy.Boolean,
        default=False,
    )
    lobby_message_id: sqlalchemy.orm.Mapped[int | None] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.BigInteger,
        )
    )
    failed_selections_count: sqlalchemy.orm.Mapped[int] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.Integer,
            default=0,
            server_default="0",
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
