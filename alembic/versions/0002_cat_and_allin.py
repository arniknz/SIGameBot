"""cat_in_bag and all_in features

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-12

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "participants",
        sa.Column(
            "all_in_used",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "game_states",
        sa.Column("cost_override", sa.Integer, nullable=True),
    )
    op.add_column(
        "game_states",
        sa.Column(
            "all_in_active",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("game_states", "all_in_active")
    op.drop_column("game_states", "cost_override")
    op.drop_column("participants", "all_in_used")
