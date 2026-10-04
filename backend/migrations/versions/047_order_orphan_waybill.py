"""Add orphan_waybill_number to order_drafts.

Revision ID: 047_order_orphan_waybill
Revises: 046_tracking_planned_delivery
Create Date: 2026-10-04

Why:
    Customer pickup reschedule cancels the old waybill and creates a new one.
    When the cancel call fails the old waybill stays live at the carrier and a
    courier may come twice. We record it here so the admin order card can show
    a warning until staff cancels it by hand (audit 2026-10-04, T3).

    Nullable, additive only — existing rows are untouched.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "047_order_orphan_waybill"
down_revision = "046_tracking_planned_delivery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "order_drafts",
        sa.Column("orphan_waybill_number", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("order_drafts", "orphan_waybill_number")
