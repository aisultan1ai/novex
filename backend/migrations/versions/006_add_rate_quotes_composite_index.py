"""add composite index on rate_quotes(quote_session_id, is_selected)

Revision ID: 006
Revises: 005
Create Date: 2026-04-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "006_rate_quotes_composite_idx"
down_revision = "005_add_carriers_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_rate_quotes_session_selected",
        "rate_quotes",
        ["quote_session_id", "is_selected"],
    )


def downgrade() -> None:
    op.drop_index("ix_rate_quotes_session_selected", table_name="rate_quotes")
