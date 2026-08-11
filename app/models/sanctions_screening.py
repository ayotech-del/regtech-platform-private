import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Auditable, Base, TenantScopedMixin


class SanctionsScreening(Base, TenantScopedMixin, Auditable):
    """One row per screening attempt -- a history, not latest-state, since
    periodic re-screening against updated lists is expected (mirrors
    IdentityVerification). Unlike BVN/NIN verification, a screening isn't
    binary: `status` is "clear" | "potential_match" | "error", `hits`
    carries every candidate scoring at/above `match_threshold` (not just
    the best one, since a human reviewer needs to see all candidates), and
    `highest_score` is the best score seen across the whole candidate set
    (even below threshold) so a future review queue can sort/filter on
    "which screenings are closest to needing review", not just confirmed
    matches.
    """

    __tablename__ = "sanctions_screenings"

    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    screened_name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # "clear" | "potential_match" | "error"
    highest_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    match_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    # Threshold in effect at screening time -- stored per-row (not just read
    # from current settings) so a historical record stays self-explanatory
    # and reproducible even if the configured threshold changes later.
    hits: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    error_detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    screened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
