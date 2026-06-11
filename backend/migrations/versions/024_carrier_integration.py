"""Add carrier_integration_logs; extend carrier_webhooks with integration fields

Revision ID: 024_carrier_integration
Revises: 023_audit_logs
Create Date: 2026-06-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "024_carrier_integration"
down_revision = "023_audit_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── carrier_integration_logs ──────────────────────────────────────────────
    op.create_table(
        "carrier_integration_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("carrier_code", sa.String(50), nullable=False),
        sa.Column(
            "direction",
            sa.String(10),
            nullable=False,
            comment="outbound | inbound",
        ),
        sa.Column(
            "event_type",
            sa.String(50),
            nullable=False,
            comment="dispatch | tracking_webhook | test_webhook | test_connection",
        ),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'success'"),
            comment="success | error",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_carrier_integration_logs_carrier_code",
        "carrier_integration_logs",
        ["carrier_code"],
    )
    op.create_index(
        "ix_carrier_integration_logs_order_id",
        "carrier_integration_logs",
        ["order_id"],
    )
    op.create_index(
        "ix_carrier_integration_logs_created_at",
        "carrier_integration_logs",
        ["created_at"],
    )

    # ── carrier_webhooks: new columns ─────────────────────────────────────────
    op.add_column(
        "carrier_webhooks",
        sa.Column(
            "dispatch_mode",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'auto'"),
            comment="auto | api | webhook | manual",
        ),
    )
    op.add_column(
        "carrier_webhooks",
        sa.Column(
            "tracking_mode",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'webhook'"),
            comment="webhook | polling | manual",
        ),
    )
    op.add_column(
        "carrier_webhooks",
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "carrier_webhooks",
        sa.Column("last_error", sa.Text(), nullable=True),
    )

    # ── carrier_webhooks: make push_url nullable ──────────────────────────────
    op.alter_column("carrier_webhooks", "push_url", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.alter_column("carrier_webhooks", "push_url", existing_type=sa.Text(), nullable=False)
    op.drop_column("carrier_webhooks", "last_error")
    op.drop_column("carrier_webhooks", "last_success_at")
    op.drop_column("carrier_webhooks", "tracking_mode")
    op.drop_column("carrier_webhooks", "dispatch_mode")
    op.drop_index("ix_carrier_integration_logs_created_at", table_name="carrier_integration_logs")
    op.drop_index("ix_carrier_integration_logs_order_id", table_name="carrier_integration_logs")
    op.drop_index("ix_carrier_integration_logs_carrier_code", table_name="carrier_integration_logs")
    op.drop_table("carrier_integration_logs")
