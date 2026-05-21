"""Add dispatch_jobs and order_status_history tables

Revision ID: 020_dispatch_jobs_status_history
Revises: 019_payment_transactions
Create Date: 2026-05-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "020_dispatch_jobs_status_history"
down_revision = "019_payment_transactions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── dispatch_jobs ─────────────────────────────────────────────────────────
    op.create_table(
        "dispatch_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "order_id",
            sa.Integer(),
            sa.ForeignKey("order_drafts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("carrier_code", sa.String(50), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'queued'"),
            comment="queued | processing | completed | failed | cancelled",
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_dispatch_jobs_order_id", "dispatch_jobs", ["order_id"])
    op.create_index("ix_dispatch_jobs_status", "dispatch_jobs", ["status"])
    op.create_index("ix_dispatch_jobs_next_retry_at", "dispatch_jobs", ["next_retry_at"])

    # ── order_status_history ──────────────────────────────────────────────────
    op.create_table(
        "order_status_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "order_id",
            sa.Integer(),
            sa.ForeignKey("order_drafts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("old_status", sa.String(50), nullable=False),
        sa.Column("new_status", sa.String(50), nullable=False),
        sa.Column("changed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "source",
            sa.String(30),
            nullable=False,
            server_default=sa.text("'system_worker'"),
            comment=(
                "customer | admin | payment_webhook | carrier_webhook | system_worker"
            ),
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_order_status_history_order_id", "order_status_history", ["order_id"])


def downgrade() -> None:
    op.drop_table("order_status_history")
    op.drop_table("dispatch_jobs")
