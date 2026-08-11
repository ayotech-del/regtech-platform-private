from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class SanctionsScreeningCreate(BaseModel):
    name_override: str | None = None
    # Optional. Defaults to the customer's stored full_name when omitted --
    # the common case, since that name already exists on the Customer row
    # (unlike BVN/NIN, which the caller must always supply). Set explicitly
    # to screen an alias/AKA/maiden name without needing a separate
    # customer record.

    @field_validator("name_override")
    @classmethod
    def not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("name_override must not be blank")
        return v


class WatchlistHitRead(BaseModel):
    matched_name: str
    list_name: str
    score: float


class SanctionsScreeningRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    customer_id: uuid.UUID
    screened_name: str
    provider_name: str
    status: str
    highest_score: float | None
    match_threshold: float
    hits: list[WatchlistHitRead]
    error_detail: str | None
    screened_at: datetime
    created_at: datetime
