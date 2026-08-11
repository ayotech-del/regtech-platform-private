from __future__ import annotations

import uuid

import typer
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.db.audit import AuditChainHead, genesis_hash, verify_chain
from app.models.tenant import Tenant

app = typer.Typer(help="RegTech platform admin CLI (tenant provisioning, audit verification)")

# Runs as the migrations/owner role -- a superuser, so it bypasses RLS
# regardless of FORCE ROW LEVEL SECURITY. This is intentional: provisioning
# a tenant (and its audit_chain_head genesis row) must happen before any
# tenant context exists to set app.current_tenant for.
_migrations_engine = create_engine(settings.database_url_migrations)


@app.command("create-tenant")
def create_tenant(name: str, slug: str) -> None:
    with Session(_migrations_engine) as db:
        tenant = Tenant(id=uuid.uuid4(), name=name, slug=slug)
        db.add(tenant)
        db.flush()

        head = AuditChainHead(tenant_id=tenant.id, last_seq=0, last_hash=genesis_hash(tenant.id))
        db.add(head)

        db.commit()
        typer.echo(f"Created tenant {tenant.name!r} (slug={tenant.slug}, id={tenant.id})")


@app.command("verify-chain")
def verify_chain_cmd(tenant_id: str) -> None:
    with Session(_migrations_engine) as db:
        result = verify_chain(db, uuid.UUID(tenant_id))
    if result.valid:
        typer.echo(f"PASS: chain valid, {result.length} entries")
    else:
        typer.echo(f"FAIL: tampering detected at seq={result.failed_at_seq}: {result.reason}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
