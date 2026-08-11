from __future__ import annotations

import uuid
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

# The API always connects as app_user (NOSUPERUSER NOBYPASSRLS). This engine
# must never be pointed at DATABASE_URL_MIGRATIONS.
engine = create_engine(settings.database_url_app, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=True, expire_on_commit=False)


def tenant_session(tenant_id: uuid.UUID, actor_id: uuid.UUID | None = None, actor_type: str = "user") -> Generator[Session, None, None]:
    """Opens one request-scoped session/transaction and pins it to a tenant
    via set_config('app.current_tenant', ...) before any query runs.

    set_config(..., is_local=true) is transaction-scoped (like SET LOCAL)
    and is a normal parameterized function call, unlike `SET LOCAL x = :y`
    which can't be safely parameterized. This must stay inside the same
    db.begin() block as the queries it protects -- never set on one
    transaction and queried on another, or RLS silently sees no tenant.
    """
    db = SessionLocal()
    db.info["tenant_id"] = tenant_id
    db.info["actor_id"] = actor_id
    db.info["actor_type"] = actor_type
    try:
        with db.begin():
            db.execute(
                text("SELECT set_config('app.current_tenant', :t, true)"),
                {"t": str(tenant_id)},
            )
            yield db
    finally:
        db.close()


def get_db_for_tenant(tenant_id: uuid.UUID, actor_id: uuid.UUID | None = None, actor_type: str = "user"):
    """FastAPI-dependency-shaped wrapper around tenant_session, for use as
    `Depends(...)` once request-level tenant resolution (app.api.deps) has
    determined the tenant.
    """
    yield from tenant_session(tenant_id, actor_id=actor_id, actor_type=actor_type)


# `tenant_session` is a bare generator function so FastAPI can drive it as a
# `Depends(...)` (FastAPI advances it past `yield` itself after the request).
# Outside FastAPI -- scripts, the CLI, tests -- wrap it as a context manager
# so `with tenant_session_cm(tenant_id) as db:` actually commits/closes on
# exit instead of leaving the generator (and its transaction) suspended.
tenant_session_cm = contextmanager(tenant_session)
