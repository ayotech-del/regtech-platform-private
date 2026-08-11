import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CHAR, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Auditable, Base, TenantScopedMixin


class IdentityVerification(Base, TenantScopedMixin, Auditable):
    """One row per BVN/NIN check attempt -- a history, not latest-state,
    since periodic re-verification is expected. Never stores the raw
    identifier: identifier_last4 + identifier_hash (HMAC-SHA256, see
    app/services/identity_service.py:hash_identifier) only.
    """

    __tablename__ = "identity_verifications"

    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    identifier_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "BVN" | "NIN"
    identifier_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    identifier_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False, index=True)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # "verified" | "no_match" | "error"
    matched: Mapped[bool] = mapped_column(Boolean, nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    profile_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
