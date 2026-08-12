from __future__ import annotations

from decimal import Decimal

from app.config import settings
from app.services.monitoring.rules.base import MonitoringRule, RuleContext, RuleFinding


class LargeAmountRule(MonitoringRule):
    code = "LARGE_AMOUNT"

    def evaluate(self, ctx: RuleContext) -> RuleFinding | None:
        threshold = Decimal(str(settings.monitoring_large_amount_threshold))
        if ctx.transaction.amount < threshold:
            return None
        return RuleFinding(
            rule_code=self.code,
            severity="high",
            detail={
                "amount": float(ctx.transaction.amount),
                "currency": ctx.transaction.currency,
                "threshold": settings.monitoring_large_amount_threshold,
            },
        )
