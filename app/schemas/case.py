from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

SourceType = Literal["sanctions_screening", "transaction_alert"]


class CaseCreate(BaseModel):
    customer_id: uuid.UUID
    source_type: SourceType
    source_id: uuid.UUID
    priority: str = "medium"

    @field_validator("priority")
    @classmethod
    def valid_priority(cls, v: str) -> str:
        if v not in {"low", "medium", "high"}:
            raise ValueError("priority must be one of: low, medium, high")
        return v


class CaseUpdate(BaseModel):
    status: str | None = None
    resolution: str | None = None
    resolution_notes: str | None = None
    assigned_to: str | None = None

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str | None) -> str | None:
        if v is not None and v not in {"open", "in_review", "resolved"}:
            raise ValueError("status must be one of: open, in_review, resolved")
        return v

    @field_validator("resolution")
    @classmethod
    def valid_resolution(cls, v: str | None) -> str | None:
        if v is not None and v not in {"confirmed", "false_positive", "escalated"}:
            raise ValueError("resolution must be one of: confirmed, false_positive, escalated")
        return v


class CaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    customer_id: uuid.UUID
    source_type: str
    source_id: uuid.UUID
    priority: str
    status: str
    resolution: str | None
    resolution_notes: str | None
    assigned_to: str | None
    opened_at: datetime
    resolved_at: datetime | None
    created_at: datetime


class CaseNoteCreate(BaseModel):
    author: str
    body: str

    @field_validator("author", "body")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v


class CaseNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    case_id: uuid.UUID
    author: str
    body: str
    created_at: datetime
