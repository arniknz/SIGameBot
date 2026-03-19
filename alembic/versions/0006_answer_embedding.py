"""add answer_embedding and normalized_answer to questions

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-18

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "questions",
        sa.Column("normalized_answer", sa.Text(), nullable=True),
    )
    op.add_column(
        "questions",
        sa.Column("answer_embedding", sa.LargeBinary(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("questions", "answer_embedding")
    op.drop_column("questions", "normalized_answer")
