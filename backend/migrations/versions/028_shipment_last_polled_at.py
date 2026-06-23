"""Add last_polled_at to shipments for polling cooldown

Revision ID: 028_shipment_last_polled_at
Revises: 027_cse_carrier
Create Date: 2026-06-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "028_shipment_last_polled_at"
down_revision = "027_cse_carrier"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shipments",
        sa.Column("last_polled_at", sa.DateTime, nullable=True),
    )
    op.create_index(
        "ix_shipments_last_polled_at",
        "shipments",
        ["last_polled_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_shipments_last_polled_at", table_name="shipments")
    op.drop_column("shipments", "last_polled_at")
