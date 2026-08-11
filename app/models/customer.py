from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Auditable, Base, TenantScopedMixin


class Customer(Base, TenantScopedMixin, Auditable):
    """Example tenant-scoped, audited table -- proves RLS isolation and
    hash-chained audit logging work together. Later modules (identity/KYC
    etc.) attach to a real customer table shaped like this one.
    """

    __tablename__ = "customers"

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
