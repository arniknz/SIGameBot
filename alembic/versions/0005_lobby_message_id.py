"""add lobby_message_id to game_states

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-16

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "game_states",
        sa.Column("lobby_message_id", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("game_states", "lobby_message_id")
