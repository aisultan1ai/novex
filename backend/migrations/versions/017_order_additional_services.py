"""add additional services fields to order_drafts

Revision ID: 017_order_additional_services
Revises: 016_reviews
Create Date: 2026-05-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "017_order_additional_services"
down_revision = "016_reviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "order_drafts",
        sa.Column("call_before_delivery", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "order_drafts",
        sa.Column("insurance", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "order_drafts",
        sa.Column("fragile", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("order_drafts", "fragile")
    op.drop_column("order_drafts", "insurance")
    op.drop_column("order_drafts", "call_before_delivery")
