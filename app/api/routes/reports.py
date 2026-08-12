from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.report import ReportCreate, ReportRead
from app.services import case_service, report_service

router = APIRouter(prefix="/cases/{case_id}/reports", tags=["reports"])


@router.post("", response_model=ReportRead, status_code=201)
def generate_report(case_id: uuid.UUID, payload: ReportCreate, db: Session = Depends(get_db)) -> ReportRead:
    case = case_service.get_case(db, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    try:
        report = report_service.generate_report(db, db.info["tenant_id"], case, payload.report_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ReportRead.model_validate(report)


@router.get("", response_model=list[ReportRead])
def list_reports(case_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ReportRead]:
    case = case_service.get_case(db, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return [ReportRead.model_validate(r) for r in report_service.list_reports_for_case(db, case_id)]
