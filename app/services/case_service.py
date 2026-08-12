from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.case import Case
from app.models.case_note import CaseNote
from app.models.sanctions_screening import SanctionsScreening
from app.models.transaction_alert import TransactionAlert
from app.schemas.case import CaseNoteCreate, CaseUpdate

_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2}


def open_case(
    db: Session, tenant_id: uuid.UUID, customer_id: uuid.UUID, source_type: str, source_id: uuid.UUID, priority: str
) -> Case:
    case = Case(
        tenant_id=tenant_id,
        customer_id=customer_id,
        source_type=source_type,
        source_id=source_id,
        priority=priority,
        status="open",
    )
    db.add(case)
    db.flush()
    db.refresh(case)
    return case


def open_case_for_sanctions_screening(
    db: Session, tenant_id: uuid.UUID, customer_id: uuid.UUID, screening: SanctionsScreening
) -> Case | None:
    # Unconditional -- a watchlist hit always warrants review regardless of
    # score, unlike a rule-engine heuristic (see open_case_for_transaction_alert).
    if screening.status != "potential_match":
        return None
    return open_case(db, tenant_id, customer_id, "sanctions_screening", screening.id, priority="high")


def open_case_for_transaction_alert(
    db: Session, tenant_id: uuid.UUID, customer_id: uuid.UUID, alert: TransactionAlert
) -> Case | None:
    floor = _SEVERITY_RANK[settings.case_auto_open_min_severity]
    if _SEVERITY_RANK[alert.severity] < floor:
        return None
    return open_case(db, tenant_id, customer_id, "transaction_alert", alert.id, priority=alert.severity)


def list_cases(db: Session, status: str | None = None, customer_id: uuid.UUID | None = None) -> list[Case]:
    # No tenant_id filter -- RLS makes this correct, same idiom as every
    # other list_X in this codebase. This is the tenant-wide review queue,
    # so customer_id is an optional filter here, not a required scope.
    stmt = select(Case).order_by(Case.opened_at.desc())
    if status is not None:
        stmt = stmt.where(Case.status == status)
    if customer_id is not None:
        stmt = stmt.where(Case.customer_id == customer_id)
    return list(db.execute(stmt).scalars().all())


def get_case(db: Session, case_id: uuid.UUID) -> Case | None:
    return db.get(Case, case_id)


def update_case_status(db: Session, case: Case, payload: CaseUpdate) -> Case:
    next_status = payload.status if payload.status is not None else case.status
    next_resolution = payload.resolution if payload.resolution is not None else case.resolution

    if next_status == "resolved" and next_resolution is None:
        raise ValueError("resolution is required to resolve a case")

    if payload.status is not None:
        case.status = payload.status
        if payload.status == "resolved":
            case.resolved_at = datetime.now(timezone.utc)
    if payload.resolution is not None:
        case.resolution = payload.resolution
    if payload.resolution_notes is not None:
        case.resolution_notes = payload.resolution_notes
    if payload.assigned_to is not None:
        case.assigned_to = payload.assigned_to

    db.flush()
    db.refresh(case)
    return case


def add_case_note(db: Session, tenant_id: uuid.UUID, case_id: uuid.UUID, payload: CaseNoteCreate) -> CaseNote:
    note = CaseNote(tenant_id=tenant_id, case_id=case_id, author=payload.author, body=payload.body)
    db.add(note)
    db.flush()
    db.refresh(note)
    return note


def list_case_notes(db: Session, case_id: uuid.UUID) -> list[CaseNote]:
    return list(
        db.execute(
            select(CaseNote).where(CaseNote.case_id == case_id).order_by(CaseNote.created_at.asc())
        ).scalars().all()
    )
