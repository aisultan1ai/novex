"""Add users.locale (interface language for emails and notifications).

Revision ID: 049_user_locale
Revises: 048_pd_consent
Create Date: 2026-10-13

Why:
    The frontend is bilingual (ru / kk). Emails and in-app notifications are
    produced outside the HTTP request (workers), so the user's language has to
    be stored. Existing users default to Russian.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "049_user_locale"
down_revision = "048_pd_consent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("locale", sa.String(length=2), nullable=False, server_default="ru"),
    )


def downgrade() -> None:
    op.drop_column("users", "locale")
