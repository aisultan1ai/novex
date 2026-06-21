"""Add index on order_drafts.status for admin list/filter queries

Revision ID: 026
Revises: 025
Create Date: 2026-06-20
"""
from __future__ import annotations

from alembic import op

revision = "026"
down_revision = "025_encrypt_carrier_creds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_order_drafts_status",
        "order_drafts",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_order_drafts_status", table_name="order_drafts")
