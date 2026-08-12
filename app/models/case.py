import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Auditable, Base, TenantScopedMixin


class Case(Base, TenantScopedMixin, Auditable):
    """One row per investigation opened against a triggering record. The
    trigger is referenced polymorphically (source_type + source_id, no DB
    FK -- Postgres can't FK one column to either of two tables) rather than
    two nullable FKs, so a new triggering-record type is a new source_type
    value, not a schema change. Referential integrity on source_id is
    enforced at the application layer instead (see case_service.open_case).
    """

    __tablename__ = "cases"

    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)  # "sanctions_screening" | "transaction_alert"
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid(), nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(10), nullable=False)  # "low" | "medium" | "high"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")  # open | in_review | resolved
    resolution: Mapped[str | None] = mapped_column(String(20), nullable=True)  # confirmed | false_positive | escalated
    resolution_notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # Plain string, not a user FK -- there's no real auth/user table yet
    # (see app/api/deps.py:get_current_tenant), so this mirrors that stub
    # rather than inventing a fake identity system.
    assigned_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
