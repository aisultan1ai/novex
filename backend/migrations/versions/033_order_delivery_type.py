"""Add delivery_type + PVZ GUIDs to order_drafts

Supports the four CSE DeliveryType combinations:
  door_to_door           — ДоставкаДоДверей (default)
  warehouse_to_door      — СкладДверь (sender drops at PVZ)
  door_to_warehouse      — Самовывоз (recipient picks up from PVZ)
  warehouse_to_warehouse — СкладСклад (both PVZ)

sender_pvz_guid / recipient_pvz_guid store the chosen CSE PVZ GUID for the
warehouse legs.

Revision ID: 033_order_delivery_type
Revises: 032_carrier_pricing_columns
Create Date: 2026-07-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "033_order_delivery_type"
down_revision = "032_carrier_pricing_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "order_drafts",
        sa.Column(
            "delivery_type",
            sa.String(30),
            nullable=False,
            server_default="door_to_door",
        ),
    )
    op.add_column(
        "order_drafts",
        sa.Column("sender_pvz_guid", sa.String(50), nullable=True),
    )
    op.add_column(
        "order_drafts",
        sa.Column("recipient_pvz_guid", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("order_drafts", "recipient_pvz_guid")
    op.drop_column("order_drafts", "sender_pvz_guid")
    op.drop_column("order_drafts", "delivery_type")
