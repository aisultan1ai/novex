"""Add urgency_guid to rate_quotes for CSE tariff dispatch

Revision ID: 030_rate_quote_urgency_guid
Revises: 029_missing_indexes
Create Date: 2026-07-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "030_rate_quote_urgency_guid"
down_revision = "029_missing_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rate_quotes",
        sa.Column("urgency_guid", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("rate_quotes", "urgency_guid")
