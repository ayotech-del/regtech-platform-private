import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Auditable, Base, TenantScopedMixin


class Report(Base, TenantScopedMixin, Auditable):
    """One row per report generation attempt -- a history, not latest-state,
    mirroring IdentityVerification/SanctionsScreening: a failed submission
    can be retried, producing a new row, rather than mutating one.
    """

    __tablename__ = "reports"

    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "STR" | "SAR"
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # "submitted" | "error"
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    error_detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
