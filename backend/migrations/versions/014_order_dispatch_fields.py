"""order_drafts: add dispatch_error column

Revision ID: 014_order_dispatch_fields
Revises: 013_carrier_webhooks
Create Date: 2026-05-12
"""
from alembic import op
import sqlalchemy as sa

revision = "014_order_dispatch_fields"
down_revision = "013_carrier_webhooks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("order_drafts", sa.Column("dispatch_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("order_drafts", "dispatch_error")
