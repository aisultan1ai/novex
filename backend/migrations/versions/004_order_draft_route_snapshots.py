from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "004_order_draft_route_snapshots"
down_revision = "003_order_draft_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "order_drafts",
        sa.Column("from_country_snapshot", sa.String(length=2), nullable=True),
    )
    op.add_column(
        "order_drafts",
        sa.Column("from_city_snapshot", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "order_drafts",
        sa.Column("to_country_snapshot", sa.String(length=2), nullable=True),
    )
    op.add_column(
        "order_drafts",
        sa.Column("to_city_snapshot", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "order_drafts",
        sa.Column("shipment_type_snapshot", sa.String(length=20), nullable=True),
    )

    op.execute(
        """
        UPDATE order_drafts
        SET
            from_country_snapshot = qs.from_country,
            from_city_snapshot = qs.from_city,
            to_country_snapshot = qs.to_country,
            to_city_snapshot = qs.to_city,
            shipment_type_snapshot = qs.shipment_type
        FROM quote_sessions qs
        WHERE order_drafts.quote_session_id = qs.id
        """
    )

    op.alter_column("order_drafts", "from_country_snapshot", nullable=False)
    op.alter_column("order_drafts", "from_city_snapshot", nullable=False)
    op.alter_column("order_drafts", "to_country_snapshot", nullable=False)
    op.alter_column("order_drafts", "to_city_snapshot", nullable=False)
    op.alter_column("order_drafts", "shipment_type_snapshot", nullable=False)


def downgrade() -> None:
    op.drop_column("order_drafts", "shipment_type_snapshot")
    op.drop_column("order_drafts", "to_city_snapshot")
    op.drop_column("order_drafts", "to_country_snapshot")
    op.drop_column("order_drafts", "from_city_snapshot")
    op.drop_column("order_drafts", "from_country_snapshot")