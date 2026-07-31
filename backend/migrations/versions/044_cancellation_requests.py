"""Cancellation requests — new table + carrier.notification_email

Revision ID: 044_cancellation_requests
Revises: 043_commission_reversal
Create Date: 2026-07-30

Why:
    Azimuth has no cancel API and CSE/Exline reject cancellation in some
    statuses. Previously the customer got a 409 with «свяжитесь с
    поддержкой», which pushed the whole cancellation flow off-platform.

    New model: a cancellation request is an explicit record that the
    customer wants to cancel. It lives in one of four states —
    pending / approved (manual) / api_cancelled (via carrier API) /
    rejected. Whoever confirms (carrier for Azimuth, admin as fallback,
    successful API call for CSE/Exline) transitions the order into
    'cancelled' through a single finalize path so commission reversal
    and refund_pending stay consistent.

    Partial unique index guarantees only one pending request per order
    while keeping the historical trail of resolved ones.

    `carriers.notification_email` is a separate ops mailbox for the
    carrier (deliberately not tied to any User.email — a carrier may
    have several staff accounts but a single ops address for
    cancellation notifications).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "044_cancellation_requests"
down_revision = "043_commission_reversal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "carriers",
        sa.Column("notification_email", sa.String(length=255), nullable=True),
    )

    op.create_table(
        "cancellation_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "order_draft_id",
            sa.Integer(),
            sa.ForeignKey("order_drafts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "requested_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("carrier_code", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "api_attempted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("api_error", sa.Text(), nullable=True),
        sa.Column("carrier_response", sa.Text(), nullable=True),
        sa.Column(
            "resolved_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_cancellation_requests_order_draft_id",
        "cancellation_requests",
        ["order_draft_id"],
    )
    op.create_index(
        "ix_cancellation_requests_carrier_code",
        "cancellation_requests",
        ["carrier_code"],
    )
    op.create_index(
        "ix_cancellation_requests_status",
        "cancellation_requests",
        ["status"],
    )
    # Partial unique: at most one active (pending) request per order, but
    # historical resolved rows may co-exist.
    op.create_index(
        "uq_cancellation_requests_active",
        "cancellation_requests",
        ["order_draft_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_cancellation_requests_active", table_name="cancellation_requests"
    )
    op.drop_index(
        "ix_cancellation_requests_status", table_name="cancellation_requests"
    )
    op.drop_index(
        "ix_cancellation_requests_carrier_code", table_name="cancellation_requests"
    )
    op.drop_index(
        "ix_cancellation_requests_order_draft_id",
        table_name="cancellation_requests",
    )
    op.drop_table("cancellation_requests")
    op.drop_column("carriers", "notification_email")
