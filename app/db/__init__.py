# Importing app.db.audit here registers its `before_flush` SQLAlchemy event
# listener as a side effect of importing anything under app.db (session,
# base, rls, ...) -- which every entrypoint (app.main, app.cli,
# scripts/smoke_test.py) does. Without this, a process that never happens
# to import app.db.audit directly would silently run with no audit logging
# at all: mutations would succeed, RLS would still isolate tenants, but
# nothing would land in audit_log. That's exactly the kind of gap that must
# not be possible to hit by accident in a compliance product.
from app.db import audit as _audit  # noqa: F401
