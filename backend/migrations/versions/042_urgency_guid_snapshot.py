"""Snapshot CSE urgency_guid on OrderDraft so dispatch survives RateQuote deletion

Revision ID: 042
Revises: 041
Create Date: 2026-07-25

Why:
    Prior to this change DispatchWorker resolved urgency_guid by loading
    RateQuote via order.selected_rate_quote_id at dispatch time. quote_sessions
    are ON DELETE cleaned up (housekeeping cron), and RateQuote rows go with
    them. If a customer paid an order but our dispatch cron ran after that
    cleanup, CSE dispatch aborted with "urgency_guid missing".

    Solution mirrors the existing carrier_/tariff_/price_snapshot pattern: we
    freeze the value at quote-selection time so dispatch reads from the order
    itself, not from a reference row that may be gone.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "042_urgency_guid_snapshot"
down_revision = "041_notification_link_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "order_drafts",
        sa.Column("urgency_guid_snapshot", sa.String(length=100), nullable=True),
    )
    # Backfill from the linked RateQuote where still available. Non-CSE and
    # already-dispatched orders can stay NULL — DispatchWorker treats the
    # snapshot as authoritative but keeps the RateQuote read as a fallback.
    op.execute(
        """
        UPDATE order_drafts od
        SET urgency_guid_snapshot = rq.urgency_guid
        FROM rate_quotes rq
        WHERE rq.id = od.selected_rate_quote_id
          AND rq.urgency_guid IS NOT NULL
          AND od.urgency_guid_snapshot IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("order_drafts", "urgency_guid_snapshot")
