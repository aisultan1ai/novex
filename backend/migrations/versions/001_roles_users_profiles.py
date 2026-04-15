from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "001_identity_core"
down_revision = None
branch_labels = None
depends_on = None


role_code_enum = sa.Enum(
    "customer",
    "admin",
    "operator",
    name="role_code_enum",
)

customer_type_enum = sa.Enum(
    "individual",
    "company",
    name="customer_type_enum",
)

billing_mode_enum = sa.Enum(
    "prepaid",
    "postpaid",
    name="billing_mode_enum",
)


def upgrade() -> None:

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", role_code_enum, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_roles_code", "roles", ["code"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "customer_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("customer_type", customer_type_enum, nullable=False, server_default="individual"),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("billing_mode", billing_mode_enum, nullable=False, server_default="prepaid"),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_customer_profiles_user_id", "customer_profiles", ["user_id"], unique=True)

    role_table = sa.table(
        "roles",
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
    )

    op.bulk_insert(
        role_table,
        [
            {"code": "customer", "name": "Customer"},
            {"code": "admin", "name": "Admin"},
            {"code": "operator", "name": "Operator"},
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_customer_profiles_user_id", table_name="customer_profiles")
    op.drop_table("customer_profiles")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    op.drop_index("ix_roles_code", table_name="roles")
    op.drop_table("roles")
