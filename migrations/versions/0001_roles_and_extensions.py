"""create app_user role (NOSUPERUSER NOBYPASSRLS)

Revision ID: 0001
Revises:
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.config import settings

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))

    # app_user is the ONLY role the running FastAPI app ever connects as.
    # NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE makes it structurally
    # incapable of acquiring a connection that bypasses RLS.
    #
    # Bind parameters can't be substituted inside a DO $$ ... $$ body (it's
    # parsed as plpgsql text, not SQL), so the password is escaped and
    # embedded directly. It comes from local config, not user input.
    escaped_password = settings.app_db_password.replace("'", "''")
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
                    CREATE ROLE app_user
                        WITH LOGIN
                        NOSUPERUSER
                        NOBYPASSRLS
                        NOCREATEDB
                        NOCREATEROLE
                        PASSWORD '{escaped_password}';
                END IF;
            END
            $$;
            """
        )
    )
    op.execute(sa.text("GRANT CONNECT ON DATABASE regtech TO app_user"))
    op.execute(sa.text("GRANT USAGE ON SCHEMA public TO app_user"))


def downgrade() -> None:
    op.execute(sa.text("REVOKE ALL ON SCHEMA public FROM app_user"))
    op.execute(sa.text("REVOKE ALL ON DATABASE regtech FROM app_user"))
    op.execute(sa.text("DROP ROLE IF EXISTS app_user"))
