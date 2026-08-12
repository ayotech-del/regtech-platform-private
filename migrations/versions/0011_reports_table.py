"""reports table (tenant-scoped, RLS, audited) -- regulatory filing
(STR/SAR) generation attempts against a resolved, confirmed case.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.db.rls import rls_policy_statements

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("report_type", sa.String(20), nullable=False),
        sa.Column("provider_name", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("provider_reference", sa.String(255), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_detail", sa.String(500), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_reports_tenant_id", "reports", ["tenant_id"])
    op.create_index("ix_reports_case_id", "reports", ["case_id"])
    op.create_index("ix_reports_customer_id", "reports", ["customer_id"])
    for stmt in rls_policy_statements("reports"):
        op.execute(sa.text(stmt))


def downgrade() -> None:
    op.drop_table("reports")
