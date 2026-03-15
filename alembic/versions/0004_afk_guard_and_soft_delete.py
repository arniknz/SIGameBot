"""add failed_selections_count to game_states, is_visible and created_by to topics and questions

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-15

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "game_states",
        sa.Column(
            "failed_selections_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )

    op.add_column(
        "topics",
        sa.Column(
            "is_visible",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
    )
    op.add_column(
        "topics",
        sa.Column(
            "created_by",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    op.add_column(
        "questions",
        sa.Column(
            "is_visible",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
    )
    op.add_column(
        "questions",
        sa.Column(
            "created_by",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("questions", "created_by")
    op.drop_column("questions", "is_visible")
    op.drop_column("topics", "created_by")
    op.drop_column("topics", "is_visible")
    op.drop_column("game_states", "failed_selections_count")
