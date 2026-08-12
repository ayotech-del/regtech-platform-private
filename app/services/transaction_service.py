from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.transaction import Transaction
from app.models.transaction_alert import TransactionAlert
from app.schemas.transaction import TransactionCreate
from app.services import case_service
from app.services.monitoring.engine import evaluate_transaction


def record_transaction(
    db: Session, tenant_id: uuid.UUID, customer_id: uuid.UUID, payload: TransactionCreate
) -> tuple[Transaction, list[TransactionAlert]]:
    txn = Transaction(tenant_id=tenant_id, customer_id=customer_id, amount=payload.amount, currency=payload.currency)
    db.add(txn)
    db.flush()
    db.refresh(txn)  # populates txn.id + server-defaulted created_at before rules run

    findings = evaluate_transaction(db, tenant_id, customer_id, txn)

    alerts = [
        TransactionAlert(
            tenant_id=tenant_id,
            transaction_id=txn.id,
            customer_id=customer_id,
            rule_code=f.rule_code,
            severity=f.severity,
            detail=f.detail,
            status="open",
        )
        for f in findings
    ]
    db.add_all(alerts)
    db.flush()
    for alert in alerts:
        db.refresh(alert)
    for alert in alerts:
        case_service.open_case_for_transaction_alert(db, tenant_id, customer_id, alert)
    return txn, alerts


def list_transactions(db: Session, customer_id: uuid.UUID) -> list[Transaction]:
    # No tenant_id filter -- RLS makes this correct, same idiom as every
    # other list_X in this codebase.
    return list(
        db.execute(
            select(Transaction).where(Transaction.customer_id == customer_id).order_by(Transaction.created_at.desc())
        ).scalars().all()
    )


def list_transaction_alerts(db: Session, customer_id: uuid.UUID) -> list[TransactionAlert]:
    return list(
        db.execute(
            select(TransactionAlert)
            .where(TransactionAlert.customer_id == customer_id)
            .order_by(TransactionAlert.evaluated_at.desc())
        ).scalars().all()
    )
