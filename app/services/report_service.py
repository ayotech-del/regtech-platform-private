from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.case import Case
from app.models.report import Report
from app.services.regulatory.factory import get_regulator_provider


def _build_payload(case: Case, report_type: str) -> dict[str, Any]:
    return {
        "report_type": report_type,
        "case_id": str(case.id),
        "customer_id": str(case.customer_id),
        "priority": case.priority,
        "source_type": case.source_type,
        "source_id": str(case.source_id),
        "opened_at": case.opened_at.isoformat(),
        "resolved_at": case.resolved_at.isoformat() if case.resolved_at else None,
        "resolution": case.resolution,
        "resolution_notes": case.resolution_notes,
    }


def generate_report(db: Session, tenant_id: uuid.UUID, case: Case, report_type: str) -> Report:
    if case.status != "resolved" or case.resolution != "confirmed":
        raise ValueError("case must be resolved with resolution=confirmed to generate a report")

    payload = _build_payload(case, report_type)
    result = get_regulator_provider().submit(payload)

    report = Report(
        tenant_id=tenant_id,
        case_id=case.id,
        customer_id=case.customer_id,
        report_type=report_type,
        provider_name=settings.regulator_provider,
        status=result.status,
        provider_reference=result.provider_reference,
        payload=payload,
        error_detail=result.error_detail,
    )
    db.add(report)
    db.flush()
    db.refresh(report)
    return report


def list_reports_for_case(db: Session, case_id: uuid.UUID) -> list[Report]:
    return list(
        db.execute(
            select(Report).where(Report.case_id == case_id).order_by(Report.submitted_at.desc())
        ).scalars().all()
    )
