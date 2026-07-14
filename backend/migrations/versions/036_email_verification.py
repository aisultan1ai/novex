"""Add email verification columns to users

Adds:
  - email_verified_at    — timestamp when the user confirmed their email
  - email_verify_sent_at — timestamp of the last verification email dispatched,
                           used to rate-limit "resend" requests.

Backfill policy (variant A): existing users are marked as verified with
NOW() so they do not lose access to protected actions after the feature ships.
Only new registrations after this migration go through the confirmation flow.

Revision ID: 036_email_verification
Revises: 035_tax_id
Create Date: 2026-07-14
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "036_email_verification"
down_revision = "035_tax_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("email_verify_sent_at", sa.DateTime(timezone=False), nullable=True),
    )
    # Backfill: grandfather existing accounts as verified.
    op.execute("UPDATE users SET email_verified_at = NOW() WHERE email_verified_at IS NULL")


def downgrade() -> None:
    op.drop_column("users", "email_verify_sent_at")
    op.drop_column("users", "email_verified_at")
