"""carrier_webhooks table

Revision ID: 013_carrier_webhooks
Revises: 012_platform_settings
Create Date: 2026-05-12
"""
from alembic import op
import sqlalchemy as sa

revision = "013_carrier_webhooks"
down_revision = "012_platform_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "carrier_webhooks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("carrier_code", sa.String(50), nullable=False),
        sa.Column("push_url", sa.Text(), nullable=False),
        sa.Column("webhook_secret", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["carrier_code"], ["carriers.code"], ondelete="CASCADE"),
        sa.UniqueConstraint("carrier_code", name="uq_carrier_webhooks_carrier_code"),
    )


def downgrade() -> None:
    op.drop_table("carrier_webhooks")
