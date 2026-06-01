"""Add carrier_api_credentials table

Revision ID: 022_carrier_api_creds
Revises: 021_docs_notif_qt
Create Date: 2026-06-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "022_carrier_api_creds"
down_revision = "021_docs_notif_qt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "carrier_api_credentials",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "carrier_code",
            sa.String(50),
            sa.ForeignKey("carriers.code", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("api_url", sa.Text(), nullable=False),
        sa.Column("api_token", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("extra_config", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_carrier_api_credentials_carrier_code",
        "carrier_api_credentials",
        ["carrier_code"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_carrier_api_credentials_carrier_code", table_name="carrier_api_credentials")
    op.drop_table("carrier_api_credentials")
