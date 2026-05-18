"""add payments table

Revision ID: 007
Revises: 006
Create Date: 2026-05-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "007_payments"
down_revision = "006_rate_quotes_composite_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_draft_id", sa.Integer(), nullable=False),
        sa.Column(
            "provider",
            sa.Enum("kaspi", "mock", name="payment_provider_enum"),
            nullable=False,
        ),
        sa.Column("provider_payment_id", sa.String(255), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="KZT"),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "paid",
                "failed",
                "cancelled",
                "refunded",
                name="payment_status_enum",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["order_draft_id"], ["order_drafts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payments_order_draft_id", "payments", ["order_draft_id"])
    op.create_index(
        "ix_payments_provider_payment_id", "payments", ["provider_payment_id"]
    )
    op.create_index("ix_payments_status", "payments", ["status"])


def downgrade() -> None:
    op.drop_index("ix_payments_status", table_name="payments")
    op.drop_index("ix_payments_provider_payment_id", table_name="payments")
    op.drop_index("ix_payments_order_draft_id", table_name="payments")
    op.drop_table("payments")
    op.execute("DROP TYPE IF EXISTS payment_provider_enum")
    op.execute("DROP TYPE IF EXISTS payment_status_enum")
