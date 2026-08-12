from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class ReportCreate(BaseModel):
    report_type: Literal["STR", "SAR"] = "STR"


class ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    case_id: uuid.UUID
    customer_id: uuid.UUID
    report_type: str
    provider_name: str
    status: str
    provider_reference: str | None
    payload: dict[str, Any]
    error_detail: str | None
    submitted_at: datetime
    created_at: datetime
