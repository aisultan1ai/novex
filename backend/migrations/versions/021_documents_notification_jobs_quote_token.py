"""Add documents table, notification_jobs table, quote_sessions public_token

Revision ID: 021_docs_notif_qt
Revises: 020_dispatch_jobs_status_history
Create Date: 2026-05-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "021_docs_notif_qt"
down_revision = "020_dispatch_jobs_status_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── documents ─────────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "order_id",
            sa.Integer(),
            sa.ForeignKey("order_drafts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_type",
            sa.String(20),
            nullable=False,
            comment="label | invoice | receipt | act",
        ),
        sa.Column("file_url", sa.Text(), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_documents_order_id", "documents", ["order_id"])
    op.create_index("ix_documents_document_type", "documents", ["document_type"])

    # ── notification_jobs ─────────────────────────────────────────────────────
    op.create_table(
        "notification_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column(
            "event_type",
            sa.String(50),
            nullable=False,
            comment=(
                "payment_under_review | payment_approved | payment_rejected | "
                "order_sent_to_carrier | tracking_updated | delivered"
            ),
        ),
        sa.Column(
            "channel",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'email'"),
            comment="email | sms | telegram | push",
        ),
        sa.Column("payload", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
            comment="pending | processing | sent | failed | cancelled",
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_notification_jobs_user_id", "notification_jobs", ["user_id"])
    op.create_index("ix_notification_jobs_status", "notification_jobs", ["status"])
    op.create_index("ix_notification_jobs_next_retry_at", "notification_jobs", ["next_retry_at"])

    # ── quote_sessions: add public_token, expires_at, user_id ─────────────────
    op.add_column(
        "quote_sessions",
        sa.Column("public_token", sa.String(64), nullable=True, unique=True),
    )
    op.add_column(
        "quote_sessions",
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "quote_sessions",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_quote_sessions_public_token", "quote_sessions", ["public_token"], unique=True)
    op.create_index("ix_quote_sessions_user_id", "quote_sessions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_quote_sessions_user_id", table_name="quote_sessions")
    op.drop_index("ix_quote_sessions_public_token", table_name="quote_sessions")
    op.drop_column("quote_sessions", "user_id")
    op.drop_column("quote_sessions", "expires_at")
    op.drop_column("quote_sessions", "public_token")
    op.drop_table("notification_jobs")
    op.drop_table("documents")
