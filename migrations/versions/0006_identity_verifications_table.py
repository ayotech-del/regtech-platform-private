"""identity_verifications table (tenant-scoped, RLS, audited) -- BVN/NIN
verification history. Never stores the raw identifier: identifier_last4 +
identifier_hash (HMAC-SHA256) only.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.db.rls import rls_policy_statements

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "identity_verifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("identifier_type", sa.String(10), nullable=False),
        sa.Column("identifier_last4", sa.String(4), nullable=False),
        sa.Column("identifier_hash", sa.CHAR(64), nullable=False),
        sa.Column("provider_name", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("matched", sa.Boolean(), nullable=False),
        sa.Column("provider_reference", sa.String(100), nullable=True),
        sa.Column("profile_data", postgresql.JSONB(), nullable=True),
        sa.Column("error_detail", sa.String(500), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_identity_verifications_tenant_id", "identity_verifications", ["tenant_id"])
    op.create_index("ix_identity_verifications_customer_id", "identity_verifications", ["customer_id"])
    op.create_index("ix_identity_verifications_identifier_hash", "identity_verifications", ["identifier_hash"])
    for stmt in rls_policy_statements("identity_verifications"):
        op.execute(sa.text(stmt))


def downgrade() -> None:
    op.drop_table("identity_verifications")
