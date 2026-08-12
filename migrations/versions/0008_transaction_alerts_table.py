"""transaction_alerts table (tenant-scoped, RLS, audited) -- one row per
triggered rule from the in-house AML monitoring engine.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.db.rls import rls_policy_statements

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "transaction_alerts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("rule_code", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("detail", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_transaction_alerts_tenant_id", "transaction_alerts", ["tenant_id"])
    op.create_index("ix_transaction_alerts_transaction_id", "transaction_alerts", ["transaction_id"])
    op.create_index("ix_transaction_alerts_customer_id", "transaction_alerts", ["customer_id"])
    for stmt in rls_policy_statements("transaction_alerts"):
        op.execute(sa.text(stmt))


def downgrade() -> None:
    op.drop_table("transaction_alerts")
