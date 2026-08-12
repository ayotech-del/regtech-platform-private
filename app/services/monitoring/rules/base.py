from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

from sqlalchemy.orm import Session

from app.models.transaction import Transaction


@dataclass
class RuleContext:
    db: Session
    tenant_id: uuid.UUID
    customer_id: uuid.UUID
    transaction: Transaction


@dataclass
class RuleFinding:
    rule_code: str
    severity: str  # "low" | "medium" | "high"
    detail: dict[str, Any] = field(default_factory=dict)
    # detail values must be JSON-primitive (float/str/int), not Decimal --
    # the JSONB column's default serializer can't encode Decimal, and
    # Transaction.amount comes back as Decimal at runtime despite its
    # Mapped[float] annotation (Numeric(18,2) column). Cast with float()
    # before putting an amount in here.


class MonitoringRule(ABC):
    """ABC, matching IdentityProvider/WatchlistProvider -- not Protocol,
    which is unused elsewhere in this codebase. No vendor to swap here, but
    the same "one new class + one registration line" pluggability.
    """

    code: ClassVar[str]

    @abstractmethod
    def evaluate(self, ctx: RuleContext) -> RuleFinding | None: ...
