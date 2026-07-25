"""Hot-path indexes.

Motivation:
  * shipments.carrier_tracking_number — used to correlate carrier webhooks and
    referenced by admin search, but had no index. Every admin barcode lookup
    (ilike '%X%') plus every webhook `WHERE carrier_tracking_number = :n`
    hit a seq-scan on a table that keeps growing 1:1 with orders.
  * payment_transactions(order_id, status) — order_id and status each have
    their own btree, but filters like "active tx for this order" combine
    both. Postgres picks one index and post-filters; a composite lets it go
    straight to the rows and beats bitmap-heap-scan under moderate volume.
  * Admin barcode search is `ilike '%X%'` on three shipment columns. Plain
    btree indexes cannot serve infix LIKE — installing pg_trgm gives us GIN
    trigram indexes that do.

Revision ID: 039_hotpath_indexes
Revises: 038_order_pickup_fields
Create Date: 2026-07-23
"""
from __future__ import annotations

from alembic import op

revision = "039_hotpath_indexes"
down_revision = "038_order_pickup_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pg_trgm is required for the GIN trigram indexes below. IF NOT EXISTS
    # is safe on repeat runs and on shared clusters where another schema
    # already installed it.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # All CREATE INDEX statements below use IF NOT EXISTS so this migration
    # is idempotent against hand-created indexes (occasionally an operator
    # creates a suggested index in prod before the migration lands, then the
    # migration crashes on rollout). Postgres treats index creation as
    # transactional, so a mid-migration failure otherwise rolls back the
    # entire step — meaning a single manual index turns into "run every
    # `CREATE INDEX` manually or you're stuck".
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_shipments_carrier_tracking_number "
        "ON shipments (carrier_tracking_number)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_payment_transactions_order_id_status "
        "ON payment_transactions (order_id, status)"
    )

    # GIN trigram indexes for infix LIKE on admin barcode search. Using raw
    # SQL because Alembic's create_index does not expose gin_trgm_ops nicely
    # across SQLAlchemy versions.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_shipments_tracking_number_trgm "
        "ON shipments USING gin (tracking_number gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_shipments_carrier_tracking_number_trgm "
        "ON shipments USING gin (carrier_tracking_number gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_shipments_carrier_barcode_trgm "
        "ON shipments USING gin (carrier_barcode gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_shipments_carrier_barcode_trgm")
    op.execute("DROP INDEX IF EXISTS ix_shipments_carrier_tracking_number_trgm")
    op.execute("DROP INDEX IF EXISTS ix_shipments_tracking_number_trgm")
    op.drop_index(
        "ix_payment_transactions_order_id_status",
        table_name="payment_transactions",
    )
    op.drop_index(
        "ix_shipments_carrier_tracking_number",
        table_name="shipments",
    )
    # Do NOT drop the pg_trgm extension — other objects across the DB may
    # depend on it.
