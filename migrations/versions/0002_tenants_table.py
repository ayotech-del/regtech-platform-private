"""tenants table (root directory, not RLS-filtered)

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # No RLS on tenants: it's the root directory and must be readable
    # (by slug/id) before any tenant context exists. app_user only gets
    # SELECT; all writes go through app.cli create-tenant as the
    # migrations/owner role.
    op.execute(sa.text("GRANT SELECT ON tenants TO app_user"))


def downgrade() -> None:
    op.execute(sa.text("REVOKE SELECT ON tenants FROM app_user"))
    op.drop_table("tenants")
