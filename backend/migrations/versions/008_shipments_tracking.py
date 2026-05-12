"""add shipments and tracking_events tables

Revision ID: 008_shipments_tracking
Revises: 007_payments
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "008_shipments_tracking"
down_revision = "007_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shipments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_draft_id", sa.Integer(), nullable=False),
        sa.Column("tracking_number", sa.String(100), nullable=False),
        sa.Column("carrier_tracking_number", sa.String(100), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="created"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["order_draft_id"], ["order_drafts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_draft_id", name="uq_shipments_order_draft_id"),
        sa.UniqueConstraint("tracking_number", name="uq_shipments_tracking_number"),
    )
    op.create_index("ix_shipments_order_draft_id", "shipments", ["order_draft_id"])
    op.create_index("ix_shipments_tracking_number", "shipments", ["tracking_number"])

    op.create_table(
        "tracking_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_draft_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("carrier_status", sa.String(100), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=False),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["order_draft_id"], ["order_drafts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tracking_events_order_draft_id", "tracking_events", ["order_draft_id"])
    op.create_index("ix_tracking_events_occurred_at", "tracking_events", ["occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_tracking_events_occurred_at", table_name="tracking_events")
    op.drop_index("ix_tracking_events_order_draft_id", table_name="tracking_events")
    op.drop_table("tracking_events")

    op.drop_index("ix_shipments_tracking_number", table_name="shipments")
    op.drop_index("ix_shipments_order_draft_id", table_name="shipments")
    op.drop_table("shipments")
