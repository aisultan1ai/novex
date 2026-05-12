"""add commissions table

Revision ID: 010_commissions
Revises: 009_notifications
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "010_commissions"
down_revision = "009_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "commissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_draft_id", sa.Integer(), nullable=False),
        sa.Column("carrier_code", sa.String(50), nullable=False),
        sa.Column("gross_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("commission_rate", sa.Numeric(5, 4), nullable=False),
        sa.Column("commission_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="KZT"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["order_draft_id"], ["order_drafts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_draft_id", name="uq_commissions_order_draft_id"),
    )
    op.create_index("ix_commissions_order_draft_id", "commissions", ["order_draft_id"])
    op.create_index("ix_commissions_carrier_code", "commissions", ["carrier_code"])
    op.create_index("ix_commissions_created_at", "commissions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_commissions_created_at", table_name="commissions")
    op.drop_index("ix_commissions_carrier_code", table_name="commissions")
    op.drop_index("ix_commissions_order_draft_id", table_name="commissions")
    op.drop_table("commissions")
