"""drop answer_embedding column from questions

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-19

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("questions", "answer_embedding")


def downgrade() -> None:
    op.add_column(
        "questions",
        sa.Column("answer_embedding", sa.LargeBinary(), nullable=True),
    )
