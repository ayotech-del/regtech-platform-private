"""audit_chain_head + audit_log: RLS, append-only REVOKE, raising triggers

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_chain_head",
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), primary_key=True),
        sa.Column("last_seq", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("last_hash", sa.CHAR(64), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), onupdate=sa.func.now(),
        ),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("seq", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_type", sa.String(20), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("table_name", sa.String(100), nullable=False),
        sa.Column("record_id", sa.Uuid(), nullable=False),
        sa.Column("old_values", postgresql.JSONB(), nullable=True),
        sa.Column("new_values", postgresql.JSONB(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("prev_hash", sa.CHAR(64), nullable=False),
        sa.Column("record_hash", sa.CHAR(64), nullable=False),
    )
    op.create_index("ix_audit_log_tenant_id", "audit_log", ["tenant_id"])
    op.create_index("ix_audit_log_tenant_seq", "audit_log", ["tenant_id", "seq"], unique=True)

    # --- audit_chain_head: RLS like any tenant-scoped table, but app_user
    # gets no INSERT/DELETE -- the row is created once at provisioning by
    # the migrations/owner role.
    op.execute(sa.text("ALTER TABLE audit_chain_head ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE audit_chain_head FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            """
            CREATE POLICY tenant_isolation_audit_chain_head ON audit_chain_head
              USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
              WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
            """
        )
    )
    op.execute(sa.text("GRANT SELECT, UPDATE ON audit_chain_head TO app_user"))

    # --- audit_log: RLS + append-only (REVOKE UPDATE/DELETE/TRUNCATE +
    # raising triggers). The triggers are defense-in-depth independent of
    # grants -- even a role with elevated intent that somehow runs as
    # app_user can't mutate history.
    op.execute(sa.text("ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE audit_log FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            """
            CREATE POLICY tenant_isolation_audit_log ON audit_log
              USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
              WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
            """
        )
    )
    op.execute(sa.text("GRANT SELECT, INSERT ON audit_log TO app_user"))
    op.execute(sa.text("REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM app_user"))
    # INSERT on the table doesn't imply USAGE on the identity/serial
    # sequence backing audit_log.id -- without this, every insert as
    # app_user fails with "permission denied for sequence audit_log_id_seq".
    op.execute(sa.text("GRANT USAGE, SELECT ON SEQUENCE audit_log_id_seq TO app_user"))

    op.execute(
        sa.text(
            """
            CREATE FUNCTION audit_log_immutable() RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION 'audit_log is append-only: % not permitted', TG_OP;
            END;
            $$ LANGUAGE plpgsql
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER audit_log_no_update
            BEFORE UPDATE ON audit_log
            FOR EACH ROW EXECUTE FUNCTION audit_log_immutable()
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER audit_log_no_delete
            BEFORE DELETE ON audit_log
            FOR EACH ROW EXECUTE FUNCTION audit_log_immutable()
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER IF EXISTS audit_log_no_delete ON audit_log"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS audit_log_no_update ON audit_log"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS audit_log_immutable()"))
    op.drop_table("audit_log")
    op.drop_table("audit_chain_head")
