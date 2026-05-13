"""add reviews table

Revision ID: 016_reviews
Revises: 015_carrier_profiles
Create Date: 2026-05-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "016_reviews"
down_revision = "015_carrier_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "order_draft_id",
            sa.Integer(),
            sa.ForeignKey("order_drafts.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("carrier_code", sa.String(50), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_reviews_rating_range"),
    )
    op.create_index("ix_reviews_order_draft_id", "reviews", ["order_draft_id"], unique=True)
    op.create_index("ix_reviews_user_id", "reviews", ["user_id"])
    op.create_index("ix_reviews_carrier_code", "reviews", ["carrier_code"])


def downgrade() -> None:
    op.drop_index("ix_reviews_carrier_code", table_name="reviews")
    op.drop_index("ix_reviews_user_id", table_name="reviews")
    op.drop_index("ix_reviews_order_draft_id", table_name="reviews")
    op.drop_table("reviews")
