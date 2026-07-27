"""Add UNIQUE (order_draft_id, carrier_status, occurred_at) on tracking_events.

Backs the bulk-dedup rewrite in polling/scheduler.py: instead of per-event
`SELECT ... WHERE order = ? AND carrier_status = ? AND occurred_at = ?`, the
scheduler now sends one `SELECT (carrier_status, occurred_at) IN (...)` and
then a single `INSERT ... ON CONFLICT DO NOTHING`. This constraint is what
makes the ON CONFLICT clause do its job.

Legacy rows first: earlier polling code could double-insert if two ticks
ran concurrently before the SKIP LOCKED fix. Delete duplicates keeping the
smallest id per unique key. Uses IS NOT DISTINCT FROM so NULL carrier_status
values also collapse together (they would not compare equal with plain =).

Revision ID: 040_tracking_events_dedup_unique
Revises: 039_hotpath_indexes
Create Date: 2026-07-23
"""
from __future__ import annotations

from alembic import op

revision = "040_tracking_events_dedup_unique"
down_revision = "039_hotpath_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Deduplicate any pre-existing rows that would violate the new constraint.
    # Keep the row with the smallest id per (order_draft_id, carrier_status,
    # occurred_at) group.
    op.execute(
        """
        DELETE FROM tracking_events a
        USING tracking_events b
        WHERE a.id > b.id
          AND a.order_draft_id = b.order_draft_id
          AND a.occurred_at    = b.occurred_at
          AND a.carrier_status IS NOT DISTINCT FROM b.carrier_status
        """
    )

    # ADD CONSTRAINT has no IF NOT EXISTS in Postgres before 15; use a
    # DO-block so this migration is idempotent against a hand-added
    # constraint (same reasoning as migration 039's IF NOT EXISTS guards).
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_tracking_events_order_carrier_status_occurred_at'
            ) THEN
                ALTER TABLE tracking_events
                ADD CONSTRAINT uq_tracking_events_order_carrier_status_occurred_at
                UNIQUE (order_draft_id, carrier_status, occurred_at);
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_tracking_events_order_carrier_status_occurred_at",
        "tracking_events",
        type_="unique",
    )
