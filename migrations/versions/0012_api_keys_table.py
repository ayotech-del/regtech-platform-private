"""api_keys table (root-level, not RLS-filtered -- see app/models/api_key.py)

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("key_hash", sa.CHAR(64), nullable=False),
        sa.Column("key_last4", sa.String(4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_api_keys_tenant_id", "api_keys", ["tenant_id"])
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"], unique=True)
    # No RLS on api_keys: resolving the key is what determines tenant_id in
    # the first place (same rationale as tenants). app_user only gets
    # SELECT; all writes go through app.cli as the migrations/owner role.
    op.execute(sa.text("GRANT SELECT ON api_keys TO app_user"))


def downgrade() -> None:
    op.execute(sa.text("REVOKE SELECT ON api_keys FROM app_user"))
    op.drop_table("api_keys")
