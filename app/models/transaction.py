import uuid

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Auditable, Base, TenantScopedMixin


class Transaction(Base, TenantScopedMixin, Auditable):
    """Example tenant-scoped, audited table. Placeholder for the real
    transaction-monitoring data model built in a later module.
    """

    __tablename__ = "transactions"

    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="NGN")
