"""Add link_url to notifications so client can navigate straight to the related entity

Revision ID: 041
Revises: 040
Create Date: 2026-07-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "041_notification_link_url"
down_revision = "040_tracking_events_dedup_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable so historic rows (no link) keep rendering — the UI just falls
    # back to a non-clickable notification for those.
    op.add_column(
        "notifications",
        sa.Column("link_url", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notifications", "link_url")
