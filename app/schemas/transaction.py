from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class TransactionCreate(BaseModel):
    amount: float
    currency: str = "NGN"

    @field_validator("amount")
    @classmethod
    def positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("amount must be positive")
        return v

    @field_validator("currency")
    @classmethod
    def three_letter_code(cls, v: str) -> str:
        if len(v) != 3 or not v.isalpha():
            raise ValueError("currency must be a 3-letter code")
        return v.upper()


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    customer_id: uuid.UUID
    amount: float
    currency: str
    created_at: datetime


class TransactionAlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    transaction_id: uuid.UUID
    customer_id: uuid.UUID
    rule_code: str
    severity: str
    detail: dict[str, Any]
    status: str
    evaluated_at: datetime
    created_at: datetime


class TransactionRecordResult(BaseModel):
    """Composite response for POST .../transactions -- not a 1:1 model
    mapping (no relationship() exists between Transaction and
    TransactionAlert, same as the rest of the codebase), just what the
    service call already produced, wrapped for the caller.
    """

    transaction: TransactionRead
    alerts: list[TransactionAlertRead]
