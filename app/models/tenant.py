import uuid
from datetime import datetime

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Tenant(Base):
    """The root directory of institutions. Deliberately NOT RLS-filtered:
    it must be readable (by slug/id) before any tenant context exists, which
    would be circular under RLS. app_user only ever gets SELECT on this
    table; all writes go through app.cli create-tenant as the migrations
    role.
    """

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
