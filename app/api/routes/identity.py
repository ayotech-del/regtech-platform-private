from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.identity_verification import IdentityVerificationCreate, IdentityVerificationRead
from app.services import customer_service, identity_service

router = APIRouter(prefix="/customers/{customer_id}/identity-verifications", tags=["identity"])


@router.post("", response_model=IdentityVerificationRead, status_code=201)
def create_identity_verification(
    customer_id: uuid.UUID, payload: IdentityVerificationCreate, db: Session = Depends(get_db)
) -> IdentityVerificationRead:
    customer = customer_service.get_customer(db, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    record = identity_service.create_identity_verification(db, db.info["tenant_id"], customer_id, payload)
    return IdentityVerificationRead.model_validate(record)


@router.get("", response_model=list[IdentityVerificationRead])
def list_identity_verifications(customer_id: uuid.UUID, db: Session = Depends(get_db)) -> list[IdentityVerificationRead]:
    customer = customer_service.get_customer(db, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    return [
        IdentityVerificationRead.model_validate(r)
        for r in identity_service.list_identity_verifications(db, customer_id)
    ]
