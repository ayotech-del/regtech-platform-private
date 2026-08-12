"""case_notes table (tenant-scoped, RLS, audited) -- free-text investigator
commentary on a case.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.db.rls import rls_policy_statements

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "case_notes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("author", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_case_notes_tenant_id", "case_notes", ["tenant_id"])
    op.create_index("ix_case_notes_case_id", "case_notes", ["case_id"])
    for stmt in rls_policy_statements("case_notes"):
        op.execute(sa.text(stmt))


def downgrade() -> None:
    op.drop_table("case_notes")
