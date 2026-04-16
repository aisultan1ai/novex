from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "002_quote_core"
down_revision = "001_identity_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quote_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("from_country", sa.String(length=2), nullable=False),
        sa.Column("from_city", sa.String(length=100), nullable=False),
        sa.Column("to_country", sa.String(length=2), nullable=False),
        sa.Column("to_city", sa.String(length=100), nullable=False),
        sa.Column("shipment_type", sa.String(length=20), nullable=False),
        sa.Column("weight_kg", sa.Numeric(10, 2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("width_cm", sa.Numeric(10, 2), nullable=False),
        sa.Column("height_cm", sa.Numeric(10, 2), nullable=False),
        sa.Column("depth_cm", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_quote_sessions_from_country", "quote_sessions", ["from_country"], unique=False)
    op.create_index("ix_quote_sessions_to_country", "quote_sessions", ["to_country"], unique=False)

    op.create_table(
        "rate_quotes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("quote_session_id", sa.Integer(), sa.ForeignKey("quote_sessions.id"), nullable=False),
        sa.Column("carrier_code", sa.String(length=50), nullable=False),
        sa.Column("carrier_name", sa.String(length=100), nullable=False),
        sa.Column("tariff_name", sa.String(length=100), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="KZT"),
        sa.Column("eta_days_min", sa.Integer(), nullable=False),
        sa.Column("eta_days_max", sa.Integer(), nullable=False),
        sa.Column("badge", sa.String(length=50), nullable=True),
        sa.Column("is_selected", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_rate_quotes_quote_session_id", "rate_quotes", ["quote_session_id"], unique=False)
    op.create_index("ix_rate_quotes_carrier_code", "rate_quotes", ["carrier_code"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_rate_quotes_carrier_code", table_name="rate_quotes")
    op.drop_index("ix_rate_quotes_quote_session_id", table_name="rate_quotes")
    op.drop_table("rate_quotes")

    op.drop_index("ix_quote_sessions_to_country", table_name="quote_sessions")
    op.drop_index("ix_quote_sessions_from_country", table_name="quote_sessions")
    op.drop_table("quote_sessions")