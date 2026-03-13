from __future__ import annotations

import datetime
import typing
import uuid

import sqlalchemy
import sqlalchemy.dialects.postgresql
import sqlalchemy.orm
from game.models.base import Base

if typing.TYPE_CHECKING:
    from game.models.game import GameModel, ParticipantModel
    from game.models.user import UserModel


class ShopItemModel(Base):
    __tablename__ = "shop_items"

    id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.Integer,
        primary_key=True,
    )
    emoji: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(
        sqlalchemy.String(10),
        nullable=False,
    )
    name: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(
        sqlalchemy.String(100),
        nullable=False,
    )
    description: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(
        sqlalchemy.Text,
        nullable=False,
    )
    price: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.Integer,
        nullable=False,
    )
    category: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(
        sqlalchemy.String(20),
        nullable=False,
    )
    effect: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(
        sqlalchemy.String(30),
        nullable=False,
    )


class UserInventoryModel(Base):
    __tablename__ = "user_inventory"

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
    item_id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey("shop_items.id"),
        nullable=False,
    )
    purchased_at: sqlalchemy.orm.Mapped[datetime.datetime] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.DateTime(timezone=True),
            default=lambda: datetime.datetime.now(datetime.UTC),
        )
    )
    used_in_game_id: sqlalchemy.orm.Mapped[uuid.UUID | None] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.dialects.postgresql.UUID(as_uuid=True),
            sqlalchemy.ForeignKey("games.id"),
        )
    )
    used_at: sqlalchemy.orm.Mapped[datetime.datetime | None] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.DateTime(timezone=True),
        )
    )

    user: sqlalchemy.orm.Mapped[UserModel] = sqlalchemy.orm.relationship()
    item: sqlalchemy.orm.Mapped[ShopItemModel] = sqlalchemy.orm.relationship()


class GameItemUsageModel(Base):
    __tablename__ = "game_item_usage"

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
    participant_id: sqlalchemy.orm.Mapped[uuid.UUID] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.dialects.postgresql.UUID(as_uuid=True),
            sqlalchemy.ForeignKey("participants.id"),
            nullable=False,
        )
    )
    item_id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey("shop_items.id"),
        nullable=False,
    )
    inventory_id: sqlalchemy.orm.Mapped[uuid.UUID] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.dialects.postgresql.UUID(as_uuid=True),
            sqlalchemy.ForeignKey("user_inventory.id"),
            nullable=False,
        )
    )
    question_in_game_id: sqlalchemy.orm.Mapped[uuid.UUID | None] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.dialects.postgresql.UUID(as_uuid=True),
            sqlalchemy.ForeignKey("questions_in_game.id"),
        )
    )
    used_at: sqlalchemy.orm.Mapped[datetime.datetime] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.DateTime(timezone=True),
            default=lambda: datetime.datetime.now(datetime.UTC),
        )
    )
    effect_data: sqlalchemy.orm.Mapped[dict | None] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.dialects.postgresql.JSONB,
        )
    )
