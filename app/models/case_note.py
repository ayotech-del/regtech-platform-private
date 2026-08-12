import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Auditable, Base, TenantScopedMixin


class CaseNote(Base, TenantScopedMixin, Auditable):
    """Investigator commentary on a case. Separate from audit_log, which
    only captures structured field diffs (old/new column values), not
    human-readable reasoning -- the reasoning is usually what matters most
    in a real investigation.
    """

    __tablename__ = "case_notes"

    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    # Text, not String(N) -- unlike every other free-text-ish column in this
    # codebase (error_detail, resolution_notes), which is provider/system-
    # generated and naturally short, this is unbounded human writing.
    body: Mapped[str] = mapped_column(Text, nullable=False)
