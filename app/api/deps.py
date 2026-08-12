from __future__ import annotations

import uuid
from collections.abc import Generator
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, tenant_session
from app.services import api_key_service


@dataclass
class TenantContext:
    tenant_id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_type: str


def get_current_tenant(authorization: str = Header(...)) -> TenantContext:
    """Resolves the tenant (and calling actor) from a Bearer API key.

    Looks up `api_keys` via a bare (unpinned) session -- safe because
    `api_keys` deliberately carries no RLS policy, for the same reason as
    `tenants`: resolving the key is what determines tenant_id in the first
    place, so requiring a tenant context to read it first would be
    circular (see app/models/api_key.py).
    """
    scheme, _, raw_key = authorization.partition(" ")
    if scheme.lower() != "bearer" or not raw_key:
        raise HTTPException(status_code=401, detail="Expected 'Authorization: Bearer <api-key>'")

    with SessionLocal() as db:
        key = api_key_service.authenticate(db, raw_key)
    if key is None:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")

    return TenantContext(tenant_id=key.tenant_id, actor_id=key.id, actor_type="api_key")


def get_db(ctx: TenantContext = Depends(get_current_tenant)) -> Generator[Session, None, None]:
    yield from tenant_session(ctx.tenant_id, actor_id=ctx.actor_id, actor_type=ctx.actor_type)
