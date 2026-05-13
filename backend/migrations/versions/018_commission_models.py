"""add carrier_commission_configs table for per-carrier commission models

Revision ID: 018_commission_models
Revises: 017_order_additional_services
Create Date: 2026-05-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "018_commission_models"
down_revision = "017_order_additional_services"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "carrier_commission_configs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("carrier_code", sa.String(50), nullable=False, unique=True),
        sa.Column(
            "commission_type",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'percentage'"),
        ),
        sa.Column("commission_rate", sa.Numeric(5, 4), nullable=True),
        sa.Column("fixed_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'KZT'")),
        sa.CheckConstraint(
            "commission_type IN ('percentage', 'fixed', 'combined')",
            name="ck_commission_config_type",
        ),
    )
    op.create_index(
        "ix_carrier_commission_configs_carrier_code",
        "carrier_commission_configs",
        ["carrier_code"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_carrier_commission_configs_carrier_code",
        table_name="carrier_commission_configs",
    )
    op.drop_table("carrier_commission_configs")
