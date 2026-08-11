from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.sanctions_screening import SanctionsScreeningCreate, SanctionsScreeningRead
from app.services import customer_service, sanctions_service

router = APIRouter(prefix="/customers/{customer_id}/sanctions-screenings", tags=["sanctions"])


@router.post("", response_model=SanctionsScreeningRead, status_code=201)
def create_sanctions_screening(
    customer_id: uuid.UUID,
    payload: SanctionsScreeningCreate = SanctionsScreeningCreate(),
    db: Session = Depends(get_db),
) -> SanctionsScreeningRead:
    customer = customer_service.get_customer(db, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    record = sanctions_service.create_sanctions_screening(
        db, db.info["tenant_id"], customer_id, customer.full_name, payload
    )
    return SanctionsScreeningRead.model_validate(record)


@router.get("", response_model=list[SanctionsScreeningRead])
def list_sanctions_screenings(customer_id: uuid.UUID, db: Session = Depends(get_db)) -> list[SanctionsScreeningRead]:
    customer = customer_service.get_customer(db, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    return [
        SanctionsScreeningRead.model_validate(r)
        for r in sanctions_service.list_sanctions_screenings(db, customer_id)
    ]
