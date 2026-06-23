"""Add CSE carrier to carriers table

Revision ID: 027_cse_carrier
Revises: 026
Create Date: 2026-06-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "027_cse_carrier"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text("""
            INSERT INTO carriers (code, name, description, is_active)
            VALUES ('cse', 'CSE', 'Courier Service Express — тарифы через SOAP API', true)
            ON CONFLICT (code) DO NOTHING
        """)
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM carriers WHERE code = 'cse'")
    )
