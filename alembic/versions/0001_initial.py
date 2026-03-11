"""initial

Revision ID: 0001
Revises:
Create Date: 2026-03-10

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("telegram_id", sa.BigInteger, unique=True, nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "topics",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True
        ),
        sa.Column("title", sa.Text, unique=True, nullable=False),
    )

    op.create_table(
        "questions",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True
        ),
        sa.Column(
            "topic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("topics.id"),
            nullable=False,
        ),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("answer", sa.Text, nullable=False),
        sa.Column("cost", sa.Integer, nullable=False),
        sa.CheckConstraint("cost > 0", name="ck_question_cost"),
    )

    op.create_table(
        "games",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True
        ),
        sa.Column("chat_id", sa.BigInteger, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="waiting"),
        sa.Column(
            "current_player_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "host_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "participants",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True
        ),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "game_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("games.id"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False, server_default="player"),
        sa.Column("score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.UniqueConstraint("game_id", "user_id", name="uq_game_user"),
    )

    op.create_foreign_key(
        "fk_games_current_player",
        "games",
        "participants",
        ["current_player_id"],
        ["id"],
    )

    op.create_table(
        "questions_in_game",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True
        ),
        sa.Column(
            "game_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("games.id"),
            nullable=False,
        ),
        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("questions.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column(
            "asked_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("participants.id"),
            nullable=True,
        ),
        sa.Column(
            "answered_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("participants.id"),
            nullable=True,
        ),
        sa.Column("asked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("game_id", "question_id", name="uq_game_question"),
    )

    op.create_table(
        "game_states",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True
        ),
        sa.Column(
            "game_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("games.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "current_question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("questions_in_game.id"),
            nullable=True,
        ),
        sa.Column(
            "buzzer_pressed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("participants.id"),
            nullable=True,
        ),
        sa.Column("buzzer_pressed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timer_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("game_states")
    op.drop_table("questions_in_game")
    op.drop_constraint("fk_games_current_player", "games", type_="foreignkey")
    op.drop_table("participants")
    op.drop_table("games")
    op.drop_table("questions")
    op.drop_table("topics")
    op.drop_table("users")
