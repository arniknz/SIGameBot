"""add daily rewards and cascade FK constraints

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-13

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("last_daily_claim", sa.DateTime(timezone=True), nullable=True),
    )

    op.drop_constraint(
        "questions_in_game_question_id_fkey",
        "questions_in_game",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "questions_in_game_question_id_fkey",
        "questions_in_game",
        "questions",
        ["question_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "questions_topic_id_fkey",
        "questions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "questions_topic_id_fkey",
        "questions",
        "topics",
        ["topic_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "game_item_usage_question_in_game_id_fkey",
        "game_item_usage",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "game_item_usage_question_in_game_id_fkey",
        "game_item_usage",
        "questions_in_game",
        ["question_in_game_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_constraint(
        "game_states_current_question_id_fkey",
        "game_states",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "game_states_current_question_id_fkey",
        "game_states",
        "questions_in_game",
        ["current_question_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "game_states_current_question_id_fkey",
        "game_states",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "game_states_current_question_id_fkey",
        "game_states",
        "questions_in_game",
        ["current_question_id"],
        ["id"],
    )

    op.drop_constraint(
        "game_item_usage_question_in_game_id_fkey",
        "game_item_usage",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "game_item_usage_question_in_game_id_fkey",
        "game_item_usage",
        "questions_in_game",
        ["question_in_game_id"],
        ["id"],
    )

    op.drop_constraint(
        "questions_topic_id_fkey",
        "questions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "questions_topic_id_fkey",
        "questions",
        "topics",
        ["topic_id"],
        ["id"],
    )

    op.drop_constraint(
        "questions_in_game_question_id_fkey",
        "questions_in_game",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "questions_in_game_question_id_fkey",
        "questions_in_game",
        "questions",
        ["question_id"],
        ["id"],
    )

    op.drop_column("users", "last_daily_claim")
