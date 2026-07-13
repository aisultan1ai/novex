"""Add refund_pending status (no schema change)

Client-initiated cancellation of a paid order flips the payment to
`refund_pending` — the money is still with Novex and an admin has to
initiate the actual bank transfer back. `refunded` is set only when that
transfer completes.

The `payment_transactions.status` column is stored as VARCHAR(30) (see
migration 019), not a Postgres enum type, so adding a new value is a
no-op at the DB level — the new string just needs to be accepted by
application code (TxStatus.REFUND_PENDING). This migration stays in the
chain as a marker for that behavioural change.

Revision ID: 034_payment_refund_pending
Revises: 033_order_delivery_type
Create Date: 2026-07-13
"""
from __future__ import annotations

revision = "034_payment_refund_pending"
down_revision = "033_order_delivery_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
