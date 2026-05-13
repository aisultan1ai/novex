"""identity: add carrier role and carrier_profiles table

Revision ID: 015_carrier_profiles
Revises: 014_order_dispatch_fields
Create Date: 2026-05-13
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "015_carrier_profiles"
down_revision = "014_order_dispatch_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ADD VALUE cannot be used in the same transaction where the new value is used.
    # autocommit_block commits the surrounding transaction first, adds the value, then resumes.
    with op.get_context().autocommit_block():
        op.execute(sa.text("ALTER TYPE role_code_enum ADD VALUE IF NOT EXISTS 'carrier'"))

    # Insert carrier role row (new transaction — value is now committed)
    op.execute(
        sa.text(
            "INSERT INTO roles (code, name, created_at, updated_at) "
            "VALUES ('carrier', 'Carrier', now(), now()) "
            "ON CONFLICT (code) DO NOTHING"
        )
    )

    op.create_table(
        "carrier_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("carrier_id", sa.Integer(), sa.ForeignKey("carriers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_carrier_profiles_user_id", "carrier_profiles", ["user_id"], unique=True)
    op.create_index("ix_carrier_profiles_carrier_id", "carrier_profiles", ["carrier_id"])


def downgrade() -> None:
    op.drop_index("ix_carrier_profiles_carrier_id", table_name="carrier_profiles")
    op.drop_index("ix_carrier_profiles_user_id", table_name="carrier_profiles")
    op.drop_table("carrier_profiles")
    # Note: PostgreSQL doesn't support removing enum values; role row removal only
    op.execute("DELETE FROM roles WHERE code = 'carrier'")
