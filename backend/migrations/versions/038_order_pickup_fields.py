"""Add courier-pickup fields to order_drafts.

Backs the Azimuth /order-courier flow (see AzimuthAPIClient.schedule_pickup):
after the admin approves payment for an Azimuth order, the dispatch worker
first calls create_invoice and then, if pickup_requested = true, calls
schedule_pickup with the pickup date/time slot the customer chose on the
shipment form. If schedule_pickup fails after create_invoice succeeded, the
invoice stays but we record pickup_error so the admin can manually retry
only the pickup step (retrying dispatch as a whole would create a second
waybill).

pickup_scheduled_azimuth_id is what makes the pickup call idempotent: once
Azimuth has accepted a pickup and returned its own ID we store it and never
call schedule_pickup for this order again.

Revision ID: 038_order_pickup_fields
Revises: 037_azimuth_regions
Create Date: 2026-07-21
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "038_order_pickup_fields"
down_revision = "037_azimuth_regions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "order_drafts",
        sa.Column(
            "pickup_requested",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "order_drafts",
        sa.Column("pickup_date", sa.Date, nullable=True),
    )
    op.add_column(
        "order_drafts",
        sa.Column("pickup_time_slot", sa.String(50), nullable=True),
    )
    op.add_column(
        "order_drafts",
        sa.Column("pickup_contact_person", sa.String(255), nullable=True),
    )
    op.add_column(
        "order_drafts",
        sa.Column("pickup_contact_phone", sa.String(50), nullable=True),
    )
    op.add_column(
        "order_drafts",
        sa.Column("pickup_scheduled_azimuth_id", sa.String(100), nullable=True),
    )
    op.add_column(
        "order_drafts",
        sa.Column("pickup_error", sa.String, nullable=True),
    )


def downgrade() -> None:
    for col in (
        "pickup_error",
        "pickup_scheduled_azimuth_id",
        "pickup_contact_phone",
        "pickup_contact_person",
        "pickup_time_slot",
        "pickup_date",
        "pickup_requested",
    ):
        op.drop_column("order_drafts", col)
