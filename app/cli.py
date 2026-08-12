from __future__ import annotations

import uuid

import typer
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.audit import AuditChainHead, genesis_hash, verify_chain
from app.models.tenant import Tenant
from app.services import api_key_service

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


@app.command("create-api-key")
def create_api_key(tenant_slug: str, label: str) -> None:
    with Session(_migrations_engine) as db:
        tenant = db.execute(select(Tenant).where(Tenant.slug == tenant_slug)).scalar_one_or_none()
        if tenant is None:
            typer.echo(f"Unknown tenant slug: {tenant_slug}")
            raise typer.Exit(code=1)
        record, raw_key = api_key_service.create_api_key(db, tenant.id, label)
        db.commit()
        typer.echo(f"Created API key {record.id} (label={label!r}, tenant={tenant_slug})")
        typer.echo(f"Key (shown once, will not be retrievable again): {raw_key}")


@app.command("revoke-api-key")
def revoke_api_key(key_id: str) -> None:
    with Session(_migrations_engine) as db:
        api_key_service.revoke_api_key(db, uuid.UUID(key_id))
        db.commit()
        typer.echo(f"Revoked API key {key_id}")


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
