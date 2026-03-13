"""add shop system

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-13

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("balance", sa.Integer, nullable=False, server_default="0"),
    )

    op.create_table(
        "shop_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("emoji", sa.String(10), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("price", sa.Integer, nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("effect", sa.String(30), nullable=False),
    )

    op.execute(
        sa.text("""
        INSERT INTO shop_items (id, emoji, name, description, price, category, effect) VALUES
        (1,  '🗡️', 'Double Blade',   'x2 points for correct answer',            500,  'weapons',   'double_points'),
        (2,  '🛡️', 'Shield',         'No penalty for wrong answer',              400,  'weapons',   'no_penalty'),
        (3,  '🏹', 'Time Arrow',     '+5 seconds to answer',                    300,  'weapons',   'extra_time'),
        (4,  '🔮', 'Crystal Ball',   'Reveals a hint about the answer',         200,  'weapons',   'reveal_hint'),
        (5,  '📖', 'Ancient Scroll', 'Shows the correct answer',                600,  'scrolls',   'reveal_answer'),
        (6,  '⚡', 'Lightning',      'Auto-buzz the next question',             800,  'scrolls',   'auto_buzzer'),
        (7,  '💀', 'Death Pass',     'Wrong answer returns question to board',  700,  'scrolls',   'pass_on_wrong'),
        (8,  '💎', 'Diamond',        'Treats any answer as correct',            1000, 'scrolls',   'force_correct'),
        (9,  '🃏', 'Joker',          'Replaces current question with another',  600,  'illusions',  'replace_question'),
        (10, '🪞', 'Mirror',         'Penalty transfers to a random opponent',  800,  'illusions',  'transfer_penalty'),
        (11, '⏳', 'Hourglass',      'Resurrects a random answered question',   1000, 'illusions',  'resurrect_question'),
        (12, '📦', 'Pandora''s Box', 'Opens a random new question immediately', 1200, 'illusions',  'open_any'),
        (13, '👑', 'Crown',          '+100 points immediately',                 800,  'titles',    'bonus_points'),
        (14, '🧥', 'Cloak',          'Hides your score from the board',         600,  'titles',    'hide_score'),
        (15, '🧌', 'Troll',          'Steals 50 points from an opponent',       900,  'titles',    'steal_points'),
        (16, '💍', 'Ring of Power',   'You choose the next question',            1200, 'titles',    'become_chooser')
        """)
    )

    op.create_table(
        "user_inventory",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
        ),
        sa.Column(
            "user_id", sa.BigInteger,
            sa.ForeignKey("users.id"), nullable=False,
        ),
        sa.Column(
            "item_id", sa.Integer,
            sa.ForeignKey("shop_items.id"), nullable=False,
        ),
        sa.Column(
            "purchased_at", sa.DateTime(timezone=True), nullable=False,
        ),
        sa.Column(
            "used_in_game_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("games.id"), nullable=True,
        ),
        sa.Column(
            "used_at", sa.DateTime(timezone=True), nullable=True,
        ),
    )
    op.create_index("ix_inventory_user_unused", "user_inventory", ["user_id"], postgresql_where=sa.text("used_at IS NULL"))

    op.create_table(
        "game_item_usage",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
        ),
        sa.Column(
            "game_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("games.id"), nullable=False,
        ),
        sa.Column(
            "participant_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("participants.id"), nullable=False,
        ),
        sa.Column(
            "item_id", sa.Integer,
            sa.ForeignKey("shop_items.id"), nullable=False,
        ),
        sa.Column(
            "inventory_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_inventory.id"), nullable=False,
        ),
        sa.Column(
            "question_in_game_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("questions_in_game.id"), nullable=True,
        ),
        sa.Column(
            "used_at", sa.DateTime(timezone=True), nullable=False,
        ),
        sa.Column(
            "effect_data", postgresql.JSONB, nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("game_item_usage")
    op.drop_index("ix_inventory_user_unused", "user_inventory")
    op.drop_table("user_inventory")
    op.drop_table("shop_items")
    op.drop_column("users", "balance")
