"""Record personal-data processing consent.

Revision ID: 048_pd_consent
Revises: 047_order_orphan_waybill
Create Date: 2026-10-04

Why:
    KZ law «О персональных данных и их защите» requires consent to process
    personal data. We store when it was given (audit 2026-10-04, T10):
      * users.pd_consent_at — consent at sign-up;
      * order_drafts.pd_consent_at — the customer confirms consent of the
        sender / recipient (third parties) whose data goes to the carrier.

    Nullable, additive only — existing rows stay NULL (accounts and orders
    created before the checkbox existed).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "048_pd_consent"
down_revision = "047_order_orphan_waybill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("pd_consent_at", sa.DateTime(), nullable=True))
    op.add_column("order_drafts", sa.Column("pd_consent_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("order_drafts", "pd_consent_at")
    op.drop_column("users", "pd_consent_at")
