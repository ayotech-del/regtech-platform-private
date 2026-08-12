import uuid
from datetime import datetime

from sqlalchemy import CHAR, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ApiKey(Base):
    """Root-level, like Tenant: no RLS, no Auditable. Resolving the key is
    what determines tenant_id in the first place -- requiring a tenant
    context to read it first would be circular. app_user only gets SELECT
    (see migration 0012); all writes go through app.cli as the
    migrations/owner role, same precedent as create-tenant.
    """

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    # Bare SHA-256, not HMAC-peppered like identifier_hash -- the raw key
    # has 256 bits of entropy (secrets.token_urlsafe(32)), so a bare hash
    # is already infeasible to brute-force, unlike an 11-digit BVN.
    key_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False, unique=True, index=True)
    key_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
