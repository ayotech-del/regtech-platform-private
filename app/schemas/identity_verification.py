from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator


class IdentityVerificationCreate(BaseModel):
    identifier_type: Literal["BVN", "NIN"]
    identifier: str
    # Raw value: validated here, used once by the service, never stored
    # verbatim, never echoed back in any response.

    @field_validator("identifier")
    @classmethod
    def identifier_must_be_11_digits(cls, v: str) -> str:
        if not (v.isdigit() and len(v) == 11):
            raise ValueError("identifier must be exactly 11 digits")
        return v


class IdentityVerificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    customer_id: uuid.UUID
    identifier_type: str
    identifier_last4: str
    provider_name: str
    status: str
    matched: bool
    provider_reference: str | None
    profile_data: dict[str, Any] | None
    error_detail: str | None
    checked_at: datetime
    created_at: datetime
    # identifier_hash deliberately NOT exposed -- internal dedup key only.
