from __future__ import annotations

import uuid
from collections.abc import Generator
from dataclasses import dataclass

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, tenant_session
from app.services import api_key_service

# A real FastAPI security scheme (not a bare Header(...) param) -- this is
# what makes Swagger UI show the padlock icons and a global "Authorize"
# button, and what puts a correct `securitySchemes` block in the OpenAPI
# spec for any client generator. auto_error=False so a missing header
# raises our own 401 with our own message, not FastAPI's generic 403.
_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class TenantContext:
    tenant_id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_type: str


def get_current_tenant(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> TenantContext:
    """Resolves the tenant (and calling actor) from a Bearer API key.

    Looks up `api_keys` via a bare (unpinned) session -- safe because
    `api_keys` deliberately carries no RLS policy, for the same reason as
    `tenants`: resolving the key is what determines tenant_id in the first
    place, so requiring a tenant context to read it first would be
    circular (see app/models/api_key.py).
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=401,
            detail="Expected 'Authorization: Bearer <api-key>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    with SessionLocal() as db:
        key = api_key_service.authenticate(db, credentials.credentials)
    if key is None:
        raise HTTPException(
            status_code=401, detail="Invalid or revoked API key", headers={"WWW-Authenticate": "Bearer"}
        )

    return TenantContext(tenant_id=key.tenant_id, actor_id=key.id, actor_type="api_key")


def get_db(ctx: TenantContext = Depends(get_current_tenant)) -> Generator[Session, None, None]:
    yield from tenant_session(ctx.tenant_id, actor_id=ctx.actor_id, actor_type=ctx.actor_type)
