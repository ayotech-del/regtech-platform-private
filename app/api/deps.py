from __future__ import annotations

import uuid
from collections.abc import Generator
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, tenant_session
from app.models.tenant import Tenant


@dataclass
class TenantContext:
    tenant_id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_type: str


def get_current_tenant(x_tenant_slug: str = Header(...)) -> TenantContext:
    """Resolves the tenant from a request header.

    This is a stub: real deployments will resolve the tenant from a JWT
    claim or API key, not a trusted client-supplied header. It's the single
    seam where that auth work plugs in later -- everything downstream
    (get_db, RLS) only cares about the resulting tenant_id.

    Looks up `tenants` via a bare (unpinned) session -- safe because
    `tenants` deliberately carries no RLS policy (see app/models/tenant.py).
    """
    with SessionLocal() as db:
        tenant = db.execute(
            select(Tenant).where(Tenant.slug == x_tenant_slug)
        ).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail=f"Unknown tenant slug: {x_tenant_slug}")
    return TenantContext(tenant_id=tenant.id, actor_id=None, actor_type="user")


def get_db(ctx: TenantContext = Depends(get_current_tenant)) -> Generator[Session, None, None]:
    yield from tenant_session(ctx.tenant_id, actor_id=ctx.actor_id, actor_type=ctx.actor_type)
