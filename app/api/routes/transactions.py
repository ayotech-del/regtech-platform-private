from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.transaction import TransactionAlertRead, TransactionCreate, TransactionRead, TransactionRecordResult
from app.services import customer_service, transaction_service

router = APIRouter(prefix="/customers/{customer_id}/transactions", tags=["transactions"])
alerts_router = APIRouter(prefix="/customers/{customer_id}/transaction-alerts", tags=["transactions"])


@router.post("", response_model=TransactionRecordResult, status_code=201)
def record_transaction(
    customer_id: uuid.UUID, payload: TransactionCreate, db: Session = Depends(get_db)
) -> TransactionRecordResult:
    customer = customer_service.get_customer(db, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    txn, alerts = transaction_service.record_transaction(db, db.info["tenant_id"], customer_id, payload)
    return TransactionRecordResult(
        transaction=TransactionRead.model_validate(txn),
        alerts=[TransactionAlertRead.model_validate(a) for a in alerts],
    )


@router.get("", response_model=list[TransactionRead])
def list_transactions(customer_id: uuid.UUID, db: Session = Depends(get_db)) -> list[TransactionRead]:
    customer = customer_service.get_customer(db, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    return [TransactionRead.model_validate(t) for t in transaction_service.list_transactions(db, customer_id)]


@alerts_router.get("", response_model=list[TransactionAlertRead])
def list_transaction_alerts(customer_id: uuid.UUID, db: Session = Depends(get_db)) -> list[TransactionAlertRead]:
    customer = customer_service.get_customer(db, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    return [
        TransactionAlertRead.model_validate(a)
        for a in transaction_service.list_transaction_alerts(db, customer_id)
    ]
