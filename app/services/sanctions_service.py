from __future__ import annotations

import dataclasses
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.sanctions_screening import SanctionsScreening
from app.schemas.sanctions_screening import SanctionsScreeningCreate
from app.services import case_service
from app.services.watchlist.factory import get_watchlist_provider


def create_sanctions_screening(
    db: Session,
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID,
    customer_full_name: str,
    payload: SanctionsScreeningCreate,
) -> SanctionsScreening:
    provider = get_watchlist_provider()
    name = payload.name_override or customer_full_name
    threshold = settings.sanctions_match_threshold

    result = provider.screen(name, threshold)

    record = SanctionsScreening(
        tenant_id=tenant_id,
        customer_id=customer_id,
        screened_name=name,
        provider_name=settings.watchlist_provider,
        status=result.status,
        highest_score=result.highest_score,
        match_threshold=threshold,
        hits=[dataclasses.asdict(h) for h in result.hits],
        error_detail=result.error_detail,
    )
    db.add(record)
    db.flush()
    db.refresh(record)
    case_service.open_case_for_sanctions_screening(db, tenant_id, customer_id, record)
    return record


def list_sanctions_screenings(db: Session, customer_id: uuid.UUID) -> list[SanctionsScreening]:
    # No tenant_id filter -- RLS makes this correct, same rationale as
    # identity_service.list_identity_verifications.
    return list(
        db.execute(
            select(SanctionsScreening)
            .where(SanctionsScreening.customer_id == customer_id)
            .order_by(SanctionsScreening.screened_at.desc())
        ).scalars().all()
    )
