from __future__ import annotations

import datetime
import typing

import game.models.base
import sqlalchemy
import sqlalchemy.orm

if typing.TYPE_CHECKING:
    import game.models.game

    ParticipantModel = game.models.game.ParticipantModel


class UserModel(game.models.base.Base):
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
    balance: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.Integer,
        default=0,
        server_default="0",
    )
    last_daily_claim: sqlalchemy.orm.Mapped[datetime.datetime | None] = (
        sqlalchemy.orm.mapped_column(
            sqlalchemy.DateTime(timezone=True),
        )
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
