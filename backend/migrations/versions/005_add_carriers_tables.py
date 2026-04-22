"""add carriers tables

Revision ID: 005
Revises: 004
Create Date: 2026-04-22
"""

from __future__ import annotations
from datetime import date
import sqlalchemy as sa
from alembic import op

revision = "005_add_carriers_tables"
down_revision = "004_order_draft_route_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "carriers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_carriers_code", "carriers", ["code"])

    op.create_table(
        "carrier_services",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("carrier_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("shipment_type", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.ForeignKeyConstraint(["carrier_id"], ["carriers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("carrier_id", "code", name="uq_carrier_service_code"),
    )

    op.create_table(
        "carrier_tariff_rates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("service_id", sa.Integer(), nullable=False),
        sa.Column("zone", sa.Integer(), nullable=False),
        sa.Column("weight_from_kg", sa.Numeric(10, 3), nullable=False, server_default="0"),
        sa.Column("weight_to_kg", sa.Numeric(10, 3), nullable=True),
        sa.Column("base_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("per_unit_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("per_unit_weight_kg", sa.Numeric(10, 3), nullable=True),
        sa.Column("currency", sa.String(10), nullable=False, server_default="KZT"),
        sa.Column("eta_days_min", sa.Integer(), nullable=True),
        sa.Column("eta_days_max", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("effective_from", sa.Date(), nullable=False, server_default=str(date.today())),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.ForeignKeyConstraint(["service_id"], ["carrier_services.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_carrier_tariff_rates_service_zone", "carrier_tariff_rates", ["service_id", "zone"])

    op.create_table(
        "carrier_zone_cities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("carrier_id", sa.Integer(), nullable=False),
        sa.Column("city_name", sa.String(255), nullable=False),
        sa.Column("city_name_normalized", sa.String(255), nullable=False),
        sa.Column("zone", sa.Integer(), nullable=False),
        sa.Column("city_type", sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(["carrier_id"], ["carriers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("carrier_id", "city_name_normalized", name="uq_carrier_city"),
    )
    op.create_index("ix_carrier_zone_cities_normalized", "carrier_zone_cities", ["city_name_normalized"])

    # Seed: Bestsender
    op.execute("""
        INSERT INTO carriers (code, name, description, is_active)
        VALUES ('bestsender', 'Bestsender',
                'Казахстанская курьерская служба. Тарифы 2026 г. (с НДС).',
                true)
    """)
    for svc_code, svc_name, svc_type in [
        ("standard", "Стандарт", "parcel"),
        ("express",  "Экспресс", "parcel"),
        ("economy",  "Эконом",   "cargo"),
    ]:
        op.execute(f"""
            INSERT INTO carrier_services (carrier_id, code, name, shipment_type, is_active)
            SELECT id, '{svc_code}', '{svc_name}', '{svc_type}', true
            FROM carriers WHERE code = 'bestsender'
        """)

    regional = [
        ("Актобе","актобе"), ("Алматы","алматы"), ("Астана","астана"),
        ("Атырау","атырау"), ("Жезказган","жезказган"), ("Караганда","караганда"),
        ("Кокшетау","кокшетау"), ("Костанай","костанай"), ("Кызылорда","кызылорда"),
        ("Оскемен","оскемен"), ("Усть-Каменогорск","усть-каменогорск"),
        ("Павлодар","павлодар"), ("Петропавловск","петропавловск"),
        ("Семей","семей"), ("Талдыкорган","талдыкорган"), ("Тараз","тараз"),
        ("Уральск","уральск"), ("Шымкент","шымкент"), ("Актау","актау"),
    ]
    district = [
        ("Аксай","аксай"), ("Экибастуз","экибастуз"), ("Рудный","рудный"),
        ("Темиртау","темиртау"), ("Сарыагаш","сарыагаш"), ("Жанаозен","жанаозен"),
        ("Аксу","аксу"), ("Капшагай","капшагай"), ("Щучинск","щучинск"),
        ("Степногорск","степногорск"), ("Туркестан","туркестан"),
    ]
    for city_name, normalized in regional:
        op.execute(f"""
            INSERT INTO carrier_zone_cities (carrier_id, city_name, city_name_normalized, zone, city_type)
            SELECT id, '{city_name}', '{normalized}', 1, 'regional_center'
            FROM carriers WHERE code = 'bestsender'
        """)
    for city_name, normalized in district:
        op.execute(f"""
            INSERT INTO carrier_zone_cities (carrier_id, city_name, city_name_normalized, zone, city_type)
            SELECT id, '{city_name}', '{normalized}', 2, 'district_center'
            FROM carriers WHERE code = 'bestsender'
        """)


def downgrade() -> None:
    op.drop_table("carrier_zone_cities")
    op.drop_table("carrier_tariff_rates")
    op.drop_table("carrier_services")
    op.drop_table("carriers")