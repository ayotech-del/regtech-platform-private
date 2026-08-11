"""sanctions_screenings table (tenant-scoped, RLS, audited) -- fuzzy-matched
sanctions/PEP watchlist screening history.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.db.rls import rls_policy_statements

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sanctions_screenings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("screened_name", sa.String(255), nullable=False),
        sa.Column("provider_name", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("highest_score", sa.Float(), nullable=True),
        sa.Column("match_threshold", sa.Float(), nullable=False),
        sa.Column("hits", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("error_detail", sa.String(500), nullable=True),
        sa.Column("screened_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_sanctions_screenings_tenant_id", "sanctions_screenings", ["tenant_id"])
    op.create_index("ix_sanctions_screenings_customer_id", "sanctions_screenings", ["customer_id"])
    for stmt in rls_policy_statements("sanctions_screenings"):
        op.execute(sa.text(stmt))


def downgrade() -> None:
    op.drop_table("sanctions_screenings")
