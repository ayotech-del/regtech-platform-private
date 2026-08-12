from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.transaction import Transaction
from app.services.monitoring.rules.base import MonitoringRule, RuleContext, RuleFinding
from app.services.monitoring.rules.large_amount import LargeAmountRule
from app.services.monitoring.rules.round_amount import RoundAmountRule
from app.services.monitoring.rules.velocity import VelocityRule

_RULES: list[MonitoringRule] = [LargeAmountRule(), VelocityRule(), RoundAmountRule()]
# New rule = one new class in rules/ + one entry here -- transaction_service.py
# and app/api/routes/transactions.py don't change, mirroring the provider
# factory pattern's "one adapter + one registration" idiom even though
# there's no vendor here.


def get_rules() -> list[MonitoringRule]:
    return list(_RULES)


def evaluate_transaction(
    db: Session, tenant_id: uuid.UUID, customer_id: uuid.UUID, transaction: Transaction
) -> list[RuleFinding]:
    ctx = RuleContext(db=db, tenant_id=tenant_id, customer_id=customer_id, transaction=transaction)
    return [finding for rule in get_rules() if (finding := rule.evaluate(ctx)) is not None]
