"""Add missing indexes: quote_sessions.expires_at, payment_transactions composite

Revision ID: 029_missing_indexes
Revises: 028_shipment_last_polled_at
Create Date: 2026-06-24
"""
from __future__ import annotations

from alembic import op

revision = "029_missing_indexes"
down_revision = "028_shipment_last_polled_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_quote_sessions_expires_at",
        "quote_sessions",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_payment_transactions_order_id_status",
        "payment_transactions",
        ["order_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_payment_transactions_order_id_status", table_name="payment_transactions")
    op.drop_index("ix_quote_sessions_expires_at", table_name="quote_sessions")
