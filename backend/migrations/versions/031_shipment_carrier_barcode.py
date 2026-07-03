"""Add carrier_barcode to shipments

Revision ID: 031_shipment_carrier_barcode
Revises: 030_rate_quote_urgency_guid
Create Date: 2026-07-03
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "031_shipment_carrier_barcode"
down_revision = "030_rate_quote_urgency_guid"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shipments",
        sa.Column("carrier_barcode", sa.String(100), nullable=True),
    )
    op.create_index(
        "ix_shipments_carrier_barcode",
        "shipments",
        ["carrier_barcode"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_shipments_carrier_barcode", table_name="shipments")
    op.drop_column("shipments", "carrier_barcode")
