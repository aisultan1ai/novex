"""Add planned_delivery_at column to tracking_events.

Revision ID: 046_tracking_planned_delivery
Revises: 045_cancellation_retry
Create Date: 2026-09-21

Why:
    CSE emits `planneddeliverydate` in every Tracking event (and updates it
    on «Переадресация»). Прежде мы игнорировали это поле, timeline не
    показывал перепланировку доставки клиенту.

    Nullable, потому что Exline и Azimuth его не эмитят, а также старые
    события до этой миграции не будут иметь плановой даты.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "046_tracking_planned_delivery"
down_revision = "045_cancellation_retry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tracking_events",
        sa.Column(
            "planned_delivery_at",
            sa.DateTime(timezone=False),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("tracking_events", "planned_delivery_at")
