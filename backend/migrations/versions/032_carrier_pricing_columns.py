"""Split carrier price from customer price (markup)

Adds columns to persist the carrier-facing amount separately from what the
customer pays, plus the markup amount Novex earns.

Revision ID: 032_carrier_pricing_columns
Revises: 031_shipment_carrier_barcode
Create Date: 2026-07-03
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "032_carrier_pricing_columns"
down_revision = "031_shipment_carrier_barcode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # rate_quotes: carrier-side price + markup captured at quote time
    op.add_column(
        "rate_quotes",
        sa.Column("carrier_price", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "rate_quotes",
        sa.Column("markup_amount", sa.Numeric(12, 2), nullable=True),
    )

    # order_drafts: snapshot at select-quote time so historical audit is
    # independent of later rate/commission changes
    op.add_column(
        "order_drafts",
        sa.Column("carrier_price_snapshot", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "order_drafts",
        sa.Column("markup_amount_snapshot", sa.Numeric(12, 2), nullable=True),
    )

    # commissions: carrier payout (what we owe them) — commission_amount
    # remains the profit / markup, gross_amount stays as customer-paid.
    op.add_column(
        "commissions",
        sa.Column("carrier_payout", sa.Numeric(12, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("commissions", "carrier_payout")
    op.drop_column("order_drafts", "markup_amount_snapshot")
    op.drop_column("order_drafts", "carrier_price_snapshot")
    op.drop_column("rate_quotes", "markup_amount")
    op.drop_column("rate_quotes", "carrier_price")
