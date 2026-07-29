"""Commission reversal (storno) — add status/reverses_commission_id/reversed_at/reversal_reason

Revision ID: 043_commission_reversal
Revises: 042_urgency_guid_snapshot
Create Date: 2026-07-29

Why:
    Previously admin_refund physically DELETEd the commission row for a
    refunded/cancelled order, erasing it from the ledger. That made the
    admin summary meaningless (turnover excluded refunds) and destroyed
    audit history. We move to double-entry: the original row stays and
    gets marked 'reversed', and a mirror row with negative amounts is
    inserted as 'reversal'. Summary now sums everything; refunds
    naturally net out. Cancellations via admin_orders status change use
    the same path, closing the pre-existing hole where cancellations
    outside the refund flow left the commission active.

    UNIQUE(order_draft_id) is dropped: an order can now legitimately
    have two rows (original + reversal).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "043_commission_reversal"
down_revision = "042_urgency_guid_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "commissions",
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="active",
        ),
    )
    op.add_column(
        "commissions",
        sa.Column("reversed_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "commissions",
        sa.Column("reverses_commission_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "commissions",
        sa.Column("reversal_reason", sa.String(length=500), nullable=True),
    )
    op.create_foreign_key(
        "fk_commissions_reverses_commission_id",
        "commissions",
        "commissions",
        ["reverses_commission_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_commissions_status", "commissions", ["status"]
    )
    op.create_index(
        "ix_commissions_reverses_commission_id",
        "commissions",
        ["reverses_commission_id"],
    )
    op.drop_constraint(
        "uq_commissions_order_draft_id", "commissions", type_="unique"
    )


def downgrade() -> None:
    # Purge any storno rows so the unique(order_draft_id) can be re-imposed.
    op.execute("DELETE FROM commissions WHERE status = 'reversal'")
    op.execute("UPDATE commissions SET status = 'active' WHERE status = 'reversed'")

    op.create_unique_constraint(
        "uq_commissions_order_draft_id", "commissions", ["order_draft_id"]
    )
    op.drop_index("ix_commissions_reverses_commission_id", table_name="commissions")
    op.drop_index("ix_commissions_status", table_name="commissions")
    op.drop_constraint(
        "fk_commissions_reverses_commission_id", "commissions", type_="foreignkey"
    )
    op.drop_column("commissions", "reversal_reason")
    op.drop_column("commissions", "reverses_commission_id")
    op.drop_column("commissions", "reversed_at")
    op.drop_column("commissions", "status")
