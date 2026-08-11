import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TenantScopedMixin:
    """Mixin for every table that lives inside RLS tenant isolation.

    `id` uses a client-side UUID default (not server_default) because the
    audit `before_flush` listener needs the primary key value before the
    INSERT is actually sent to the database.
    """

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


class Auditable:
    """Marker mixin: models mixing this in are captured by the audit
    before_flush listener registered in app.db.audit. This is an explicit,
    visible opt-in per model rather than auto-auditing every table.
    """
