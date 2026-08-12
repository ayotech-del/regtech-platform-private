from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.sanctions_screening import SanctionsScreening
from app.models.transaction_alert import TransactionAlert
from app.schemas.case import CaseCreate, CaseNoteCreate, CaseNoteRead, CaseRead, CaseUpdate
from app.services import case_service, customer_service

router = APIRouter(prefix="/cases", tags=["cases"])

_SOURCE_MODELS = {
    "sanctions_screening": SanctionsScreening,
    "transaction_alert": TransactionAlert,
}


def _get_case_or_404(db: Session, case_id: uuid.UUID):
    case = case_service.get_case(db, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return case


@router.get("", response_model=list[CaseRead])
def list_cases(
    status: str | None = None, customer_id: uuid.UUID | None = None, db: Session = Depends(get_db)
) -> list[CaseRead]:
    return [CaseRead.model_validate(c) for c in case_service.list_cases(db, status=status, customer_id=customer_id)]


@router.get("/{case_id}", response_model=CaseRead)
def get_case(case_id: uuid.UUID, db: Session = Depends(get_db)) -> CaseRead:
    return CaseRead.model_validate(_get_case_or_404(db, case_id))


@router.post("", response_model=CaseRead, status_code=201)
def create_case(payload: CaseCreate, db: Session = Depends(get_db)) -> CaseRead:
    customer = customer_service.get_customer(db, payload.customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail=f"Customer {payload.customer_id} not found")
    source_model = _SOURCE_MODELS[payload.source_type]
    if db.get(source_model, payload.source_id) is None:
        raise HTTPException(status_code=404, detail=f"{payload.source_type} {payload.source_id} not found")
    case = case_service.open_case(
        db, db.info["tenant_id"], payload.customer_id, payload.source_type, payload.source_id, payload.priority
    )
    return CaseRead.model_validate(case)


@router.patch("/{case_id}", response_model=CaseRead)
def update_case(case_id: uuid.UUID, payload: CaseUpdate, db: Session = Depends(get_db)) -> CaseRead:
    case = _get_case_or_404(db, case_id)
    try:
        case = case_service.update_case_status(db, case, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CaseRead.model_validate(case)


@router.post("/{case_id}/notes", response_model=CaseNoteRead, status_code=201)
def add_case_note(case_id: uuid.UUID, payload: CaseNoteCreate, db: Session = Depends(get_db)) -> CaseNoteRead:
    _get_case_or_404(db, case_id)
    note = case_service.add_case_note(db, db.info["tenant_id"], case_id, payload)
    return CaseNoteRead.model_validate(note)


@router.get("/{case_id}/notes", response_model=list[CaseNoteRead])
def list_case_notes(case_id: uuid.UUID, db: Session = Depends(get_db)) -> list[CaseNoteRead]:
    _get_case_or_404(db, case_id)
    return [CaseNoteRead.model_validate(n) for n in case_service.list_case_notes(db, case_id)]
