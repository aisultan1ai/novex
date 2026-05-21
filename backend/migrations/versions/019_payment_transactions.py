"""Add payment_transactions, payment_proofs, payment_status_history,
provider_webhook_events, tracking_webhook_events

Revision ID: 019_payment_transactions
Revises: 018_commission_models
Create Date: 2026-05-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "019_payment_transactions"
down_revision = "018_commission_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── payment_transactions ──────────────────────────────────────────────────
    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "order_id",
            sa.Integer(),
            sa.ForeignKey("order_drafts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "provider",
            sa.String(50),
            nullable=False,
            comment="manual_bank_transfer | kaspi | halyk_epay | freedompay | cloudpayments | other",
        ),
        sa.Column(
            "method",
            sa.String(30),
            nullable=False,
            comment="bank_transfer | card | qr | payment_link",
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'KZT'")),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default=sa.text("'awaiting_payment'"),
            comment=(
                "unpaid | awaiting_payment | payment_under_review | paid | "
                "payment_rejected | refunded | cancelled | expired"
            ),
        ),
        sa.Column("external_payment_id", sa.String(255), nullable=True),
        sa.Column("payment_url", sa.Text(), nullable=True),
        sa.Column("payment_reference", sa.String(100), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_payment_transactions_order_id", "payment_transactions", ["order_id"])
    op.create_index("ix_payment_transactions_status", "payment_transactions", ["status"])
    op.create_index(
        "ix_payment_transactions_external_payment_id",
        "payment_transactions",
        ["external_payment_id"],
    )

    # ── payment_proofs ────────────────────────────────────────────────────────
    op.create_table(
        "payment_proofs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "payment_id",
            sa.Integer(),
            sa.ForeignKey("payment_transactions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            sa.Integer(),
            sa.ForeignKey("order_drafts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_url", sa.Text(), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_mime_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "uploaded_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("reviewed_by_admin_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "review_status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
            comment="pending | approved | rejected",
        ),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_payment_proofs_payment_id", "payment_proofs", ["payment_id"])
    op.create_index("ix_payment_proofs_order_id", "payment_proofs", ["order_id"])
    op.create_index("ix_payment_proofs_review_status", "payment_proofs", ["review_status"])

    # ── payment_status_history ────────────────────────────────────────────────
    op.create_table(
        "payment_status_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "payment_id",
            sa.Integer(),
            sa.ForeignKey("payment_transactions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("old_status", sa.String(50), nullable=False),
        sa.Column("new_status", sa.String(50), nullable=False),
        sa.Column("changed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_payment_status_history_payment_id", "payment_status_history", ["payment_id"]
    )

    # ── provider_webhook_events ───────────────────────────────────────────────
    op.create_table(
        "provider_webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("external_event_id", sa.String(255), nullable=False),
        sa.Column("external_payment_id", sa.String(255), nullable=True),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("raw_payload", sa.Text(), nullable=False),
        sa.Column("headers", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'received'"),
        ),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provider", "external_event_id", name="uq_provider_webhook_event"),
    )
    op.create_index("ix_provider_webhook_events_provider", "provider_webhook_events", ["provider"])

    # ── tracking_webhook_events ───────────────────────────────────────────────
    op.create_table(
        "tracking_webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("carrier_code", sa.String(50), nullable=False),
        sa.Column("external_event_id", sa.String(255), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("raw_payload", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'received'"),
        ),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "carrier_code", "external_event_id", name="uq_tracking_webhook_event"
        ),
    )
    op.create_index(
        "ix_tracking_webhook_events_carrier_code",
        "tracking_webhook_events",
        ["carrier_code"],
    )


def downgrade() -> None:
    op.drop_table("tracking_webhook_events")
    op.drop_table("provider_webhook_events")
    op.drop_table("payment_status_history")
    op.drop_table("payment_proofs")
    op.drop_table("payment_transactions")
