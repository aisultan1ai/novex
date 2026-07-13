"""Add tax_id (ИИН / БИН) to customer_profiles, shipment_parties, address_book

Kazakhstan tax identifier — 12 digits, single field regardless of whether it
holds an ИИН (individual) or a БИН (company). Kept nullable in the schema so
existing rows do not blow up; API layer enforces the "required" rule for new
records.

Revision ID: 035_tax_id
Revises: 034_payment_refund_pending
Create Date: 2026-07-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "035_tax_id"
down_revision = "034_payment_refund_pending"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "customer_profiles",
        sa.Column("tax_id", sa.String(12), nullable=True),
    )
    op.add_column(
        "shipment_parties",
        sa.Column("tax_id", sa.String(12), nullable=True),
    )
    op.add_column(
        "address_book",
        sa.Column("tax_id", sa.String(12), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("address_book", "tax_id")
    op.drop_column("shipment_parties", "tax_id")
    op.drop_column("customer_profiles", "tax_id")
