"""Cancellation-request retry columns for Exline "ожидает синхронизации".

Revision ID: 045_cancellation_retry
Revises: 044_cancellation_requests
Create Date: 2026-07-30

Why:
    Exline (и в меньшей степени CSE) сразу после create_invoice удерживает
    заказ в статусе «Ожидает синхронизации» и отклоняет cancel-запрос с
    error=54. Синхронизация обычно проходит за минуты — если мы просто
    сложим руки и упадём в ручную заявку, клиент ждёт зря, админ тоже.

    Добавляем поля next_retry_at + retry_count. Worker периодически
    подхватывает заявки с api_attempted=True, next_retry_at<=now,
    retry_count<3 и вызывает retry_api_cancel. Backoff: 30s → 2m → 10m.
    После исчерпания заявка остаётся pending, next_retry_at=NULL — админ
    решает вручную.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "045_cancellation_retry"
down_revision = "044_cancellation_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cancellation_requests",
        sa.Column(
            "retry_count", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "cancellation_requests",
        sa.Column(
            "next_retry_at", sa.DateTime(timezone=False), nullable=True
        ),
    )
    # Индекс частичный — worker сканит только заявки, ждущие ретрая.
    op.create_index(
        "ix_cancellation_requests_next_retry_at",
        "cancellation_requests",
        ["next_retry_at"],
        postgresql_where=sa.text("next_retry_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_cancellation_requests_next_retry_at",
        table_name="cancellation_requests",
    )
    op.drop_column("cancellation_requests", "next_retry_at")
    op.drop_column("cancellation_requests", "retry_count")
