from __future__ import annotations

from decimal import Decimal

from app.config import settings
from app.services.monitoring.rules.base import MonitoringRule, RuleContext, RuleFinding


class RoundAmountRule(MonitoringRule):
    code = "ROUND_AMOUNT"

    def evaluate(self, ctx: RuleContext) -> RuleFinding | None:
        minimum = Decimal(str(settings.monitoring_round_amount_minimum))
        modulus = Decimal(str(settings.monitoring_round_amount_modulus))
        amount = ctx.transaction.amount
        if amount < minimum or amount % modulus != 0:
            return None
        return RuleFinding(
            rule_code=self.code,
            severity="low",
            detail={
                "amount": float(amount),
                "currency": ctx.transaction.currency,
                "modulus": settings.monitoring_round_amount_modulus,
            },
        )
