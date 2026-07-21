"""Cache table for Azimuth's /regions catalogue.

Azimuth's /api/integration/regions/{type} endpoint is the source of truth for
which KZ localities they service, in what direction (origin/destination), and
in what zone (kz_1 / kz_2 / kz_3). Previously we relied on a hardcoded set of
cities in zone_mapper.py, which drifts over time and never captured the
origin ≠ destination case (e.g. Talgar is delivery-only).

Populated by scripts/sync_azimuth_regions.py (monthly cron) and by lazy
on-demand fetches from tariff_engine when a customer types a city we have not
seen yet.

Revision ID: 037_azimuth_regions
Revises: 036_email_verification
Create Date: 2026-07-21
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "037_azimuth_regions"
down_revision = "036_email_verification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "azimuth_regions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        # Azimuth's own primary key from GET /regions/*.id. Same title may
        # appear multiple times across the country (six "Абай" in different
        # districts) — Azimuth's id is the only stable dedup key.
        sa.Column("azimuth_id", sa.Integer, nullable=False, unique=True, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        # Hierarchy string as returned ("Казахстан, Костанайская область").
        # Empty string when Azimuth returns no path.
        sa.Column("path", sa.String(500), nullable=False, server_default=""),
        # Raw zone label from Azimuth: kz_1 / kz_2 / kz_3. We keep the string
        # for auditability and derive zone_number (1/2/3) into a separate
        # column for fast filtering / joining with our tariff table.
        sa.Column("zone", sa.String(10), nullable=False),
        sa.Column("zone_number", sa.SmallInteger, nullable=False),
        sa.Column("is_origin", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_destination", sa.Boolean, nullable=False, server_default=sa.false()),
        # Lower-cased, whitespace-trimmed title for O(1) lookup from user
        # input. Not unique — multiple cities may normalise to the same key.
        sa.Column("title_normalized", sa.String(255), nullable=False, index=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("azimuth_regions")
