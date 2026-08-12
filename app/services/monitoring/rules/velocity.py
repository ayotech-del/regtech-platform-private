from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.config import settings
from app.models.transaction import Transaction
from app.services.monitoring.rules.base import MonitoringRule, RuleContext, RuleFinding


class VelocityRule(MonitoringRule):
    """Structuring/smurfing heuristic: multiple transactions, each
    individually below the large-amount threshold, that cumulatively clear
    a lower threshold within a trailing window. Requires a minimum
    transaction count too -- structuring is inherently about *multiple*
    transactions, so a lone large transaction (caught by LargeAmountRule
    instead) or two coincidental payments shouldn't trip this.
    """

    code = "VELOCITY_STRUCTURING"

    def evaluate(self, ctx: RuleContext) -> RuleFinding | None:
        window_start = ctx.transaction.created_at - timedelta(hours=settings.monitoring_velocity_window_hours)
        large_amount_cutoff = Decimal(str(settings.monitoring_large_amount_threshold))
        amount_threshold = Decimal(str(settings.monitoring_velocity_amount_threshold))

        # No explicit tenant_id filter -- same load-bearing RLS idiom as
        # every other list_X/rule query in this codebase; ctx.db is already
        # pinned to the tenant.
        total, count = ctx.db.execute(
            select(func.sum(Transaction.amount), func.count(Transaction.id)).where(
                Transaction.customer_id == ctx.customer_id,
                Transaction.currency == ctx.transaction.currency,
                Transaction.amount < large_amount_cutoff,
                Transaction.created_at >= window_start,
                Transaction.created_at <= ctx.transaction.created_at,
            )
        ).one()

        if total is None or total < amount_threshold or count < settings.monitoring_velocity_min_transactions:
            return None

        return RuleFinding(
            rule_code=self.code,
            severity="high",
            detail={
                "window_hours": settings.monitoring_velocity_window_hours,
                "total_amount": float(total),
                "currency": ctx.transaction.currency,
                "transaction_count": count,
                "threshold": settings.monitoring_velocity_amount_threshold,
            },
        )
