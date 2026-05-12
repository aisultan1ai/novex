"""add platform_settings table

Revision ID: 012_platform_settings
Revises: 011_address_book
Create Date: 2026-05-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "012_platform_settings"
down_revision = "011_address_book"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.execute("INSERT INTO platform_settings (key, value) VALUES ('commission_rate', '0.00')")


def downgrade() -> None:
    op.drop_table("platform_settings")
