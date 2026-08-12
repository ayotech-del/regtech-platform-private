import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Auditable, Base, TenantScopedMixin


class TransactionAlert(Base, TenantScopedMixin, Auditable):
    """One row per *triggered rule*, not per transaction -- a transaction
    can have 0..N alerts. `status` defaults to "open" as a forward-looking
    hook for a future case-management module to transition (same rationale
    as SanctionsScreening.highest_score / full hit-list).
    """

    __tablename__ = "transaction_alerts"

    transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transactions.id"), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    # Denormalized onto the alert row, matching identity/sanctions'
    # convention of duplicating customer_id onto the child table for direct
    # queries without a join through transactions.
    rule_code: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)  # "low" | "medium" | "high"
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
