from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "003_order_draft_core"
down_revision = "002_quote_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_drafts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("quote_session_id", sa.Integer(), sa.ForeignKey("quote_sessions.id"), nullable=False),
        sa.Column("selected_rate_quote_id", sa.Integer(), sa.ForeignKey("rate_quotes.id"), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="draft"),
        sa.Column("carrier_code_snapshot", sa.String(length=50), nullable=False),
        sa.Column("carrier_name_snapshot", sa.String(length=100), nullable=False),
        sa.Column("tariff_name_snapshot", sa.String(length=100), nullable=False),
        sa.Column("price_snapshot", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency_snapshot", sa.String(length=3), nullable=False),
        sa.Column("eta_days_min_snapshot", sa.Integer(), nullable=False),
        sa.Column("eta_days_max_snapshot", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", "quote_session_id", name="uq_order_drafts_user_quote_session"),
    )
    op.create_index("ix_order_drafts_user_id", "order_drafts", ["user_id"], unique=False)
    op.create_index("ix_order_drafts_quote_session_id", "order_drafts", ["quote_session_id"], unique=False)
    op.create_index("ix_order_drafts_selected_rate_quote_id", "order_drafts", ["selected_rate_quote_id"], unique=False)

    op.create_table(
        "shipment_parties",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_draft_id", sa.Integer(), sa.ForeignKey("order_drafts.id"), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("address_line1", sa.String(length=255), nullable=False),
        sa.Column("address_line2", sa.String(length=255), nullable=True),
        sa.Column("postal_code", sa.String(length=50), nullable=True),
        sa.Column("comment", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_shipment_parties_order_draft_id", "shipment_parties", ["order_draft_id"], unique=False)

    op.create_table(
        "shipment_packages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_draft_id", sa.Integer(), sa.ForeignKey("order_drafts.id"), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("weight_kg", sa.Numeric(10, 2), nullable=False),
        sa.Column("width_cm", sa.Numeric(10, 2), nullable=False),
        sa.Column("height_cm", sa.Numeric(10, 2), nullable=False),
        sa.Column("depth_cm", sa.Numeric(10, 2), nullable=False),
        sa.Column("declared_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("declared_value_currency", sa.String(length=3), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_shipment_packages_order_draft_id", "shipment_packages", ["order_draft_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_shipment_packages_order_draft_id", table_name="shipment_packages")
    op.drop_table("shipment_packages")

    op.drop_index("ix_shipment_parties_order_draft_id", table_name="shipment_parties")
    op.drop_table("shipment_parties")

    op.drop_index("ix_order_drafts_selected_rate_quote_id", table_name="order_drafts")
    op.drop_index("ix_order_drafts_quote_session_id", table_name="order_drafts")
    op.drop_index("ix_order_drafts_user_id", table_name="order_drafts")
    op.drop_table("order_drafts")