from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CHAR, DateTime, ForeignKey, String, Uuid, event, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, attributes, mapped_column
from sqlalchemy.orm.base import PassiveFlag

from app.db.base import Auditable, Base


class AuditChainHead(Base):
    """Tracks the tip of each tenant's hash chain. RLS-protected; app_user
    gets SELECT/UPDATE only (no INSERT/DELETE -- the row is created once, at
    tenant provisioning, by the migrations/owner role).
    """

    __tablename__ = "audit_chain_head"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), primary_key=True
    )
    last_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AuditLog(Base):
    """Append-only. REVOKE UPDATE/DELETE/TRUNCATE + raising triggers are
    applied in migration 0003 -- this model only ever INSERTs.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False, index=True
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    table_name: Mapped[str] = mapped_column(String(100), nullable=False)
    record_id: Mapped[uuid.UUID] = mapped_column(Uuid(), nullable=False)
    old_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    prev_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    record_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)


def genesis_hash(tenant_id: uuid.UUID) -> str:
    return hashlib.sha256(str(tenant_id).encode()).hexdigest()


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))


def _serialize(obj: Any) -> dict[str, Any]:
    mapper = obj.__mapper__
    return {col.key: getattr(obj, col.key) for col in mapper.columns}


def _json_safe(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Round-trips through json.dumps(default=str) so UUID/datetime/Decimal
    values become JSON-serializable primitives -- both for storing in the
    JSONB old_values/new_values columns and for hashing, so the two always
    agree on what was recorded.
    """
    if payload is None:
        return None
    return json.loads(json.dumps(payload, default=str))


def _diff(obj: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    mapper = obj.__mapper__
    old: dict[str, Any] = {}
    new: dict[str, Any] = {}
    for col in mapper.columns:
        # sqlalchemy.orm.attributes.get_history is the public, stable API for
        # this -- calling the AttributeImpl directly (as this used to) reaches
        # into an internal method whose signature (state, dict_, passive=...)
        # isn't the same as the public wrapper's (obj, key, passive=...) and
        # breaks across SQLAlchemy versions. PASSIVE_NO_FETCH mirrors the
        # original passive=True intent: never emit extra SQL mid-flush.
        history = attributes.get_history(obj, col.key, passive=PassiveFlag.PASSIVE_NO_FETCH)
        if history.added or history.deleted:
            old[col.key] = history.deleted[0] if history.deleted else None
            new[col.key] = history.added[0] if history.added else getattr(obj, col.key)
    return old, new


def _append_to_chain(
    session: Session,
    obj: Any,
    action: str,
    *,
    old: dict[str, Any] | None = None,
    new: dict[str, Any] | None = None,
) -> None:
    tenant_id = obj.tenant_id
    actor_id = session.info.get("actor_id")
    actor_type = session.info.get("actor_type", "user")

    old = _json_safe(old)
    new = _json_safe(new)

    head = session.execute(
        select(AuditChainHead)
        .where(AuditChainHead.tenant_id == tenant_id)
        .with_for_update()
    ).scalar_one()

    payload = {
        "tenant_id": str(tenant_id),
        "action": action,
        "table_name": obj.__tablename__,
        "record_id": str(obj.id),
        "old_values": old,
        "new_values": new,
    }
    canonical = _canonical_json(payload)
    record_hash = hashlib.sha256((head.last_hash + canonical).encode()).hexdigest()

    entry = AuditLog(
        seq=head.last_seq + 1,
        tenant_id=tenant_id,
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        table_name=obj.__tablename__,
        record_id=obj.id,
        old_values=old,
        new_values=new,
        prev_hash=head.last_hash,
        record_hash=record_hash,
    )
    session.add(entry)

    head.last_seq += 1
    head.last_hash = record_hash


@event.listens_for(Session, "before_flush")
def capture_audit_entries(session: Session, flush_context, instances) -> None:
    for obj in session.new:
        if isinstance(obj, Auditable):
            if obj.id is None:
                # Column-level `default=uuid.uuid4` on TenantScopedMixin.id
                # is normally applied by the ORM while building the INSERT,
                # which happens *after* before_flush -- too late for us to
                # read obj.id. Assign it here instead; the mapper will see
                # the attribute already set and skip invoking its default.
                obj.id = uuid.uuid4()
            _append_to_chain(session, obj, "INSERT", new=_serialize(obj))
    for obj in session.dirty:
        if isinstance(obj, Auditable) and session.is_modified(obj, include_collections=False):
            old, new = _diff(obj)
            if old or new:
                _append_to_chain(session, obj, "UPDATE", old=old, new=new)
    for obj in session.deleted:
        if isinstance(obj, Auditable):
            _append_to_chain(session, obj, "DELETE", old=_serialize(obj))


class ChainVerificationResult:
    def __init__(self, valid: bool, length: int, failed_at_seq: int | None = None, reason: str = ""):
        self.valid = valid
        self.length = length
        self.failed_at_seq = failed_at_seq
        self.reason = reason

    def __repr__(self) -> str:
        if self.valid:
            return f"ChainVerificationResult(valid=True, length={self.length})"
        return (
            f"ChainVerificationResult(valid=False, failed_at_seq={self.failed_at_seq}, "
            f"reason={self.reason!r})"
        )


def verify_chain(session: Session, tenant_id: uuid.UUID) -> ChainVerificationResult:
    """Walks a tenant's audit_log from genesis, re-deriving each hash.
    Independent of DB grants/triggers -- this is what makes tampering
    provable rather than merely "blocked so far".
    """
    rows = session.execute(
        select(AuditLog).where(AuditLog.tenant_id == tenant_id).order_by(AuditLog.seq)
    ).scalars().all()

    running_hash = genesis_hash(tenant_id)
    for row in rows:
        if row.prev_hash != running_hash:
            return ChainVerificationResult(
                False, len(rows), row.seq,
                f"prev_hash mismatch: expected {running_hash}, got {row.prev_hash}",
            )
        payload = {
            "tenant_id": str(row.tenant_id),
            "action": row.action,
            "table_name": row.table_name,
            "record_id": str(row.record_id),
            "old_values": row.old_values,
            "new_values": row.new_values,
        }
        expected_hash = hashlib.sha256((running_hash + _canonical_json(payload)).encode()).hexdigest()
        if expected_hash != row.record_hash:
            return ChainVerificationResult(
                False, len(rows), row.seq,
                f"record_hash mismatch: expected {expected_hash}, got {row.record_hash} "
                "(content was altered after recording)",
            )
        running_hash = row.record_hash

    head = session.execute(
        select(AuditChainHead).where(AuditChainHead.tenant_id == tenant_id)
    ).scalar_one()
    if running_hash != head.last_hash:
        return ChainVerificationResult(
            False, len(rows), None,
            f"chain tip mismatch: recomputed {running_hash}, head says {head.last_hash} "
            "(rows may have been deleted from the tail)",
        )

    return ChainVerificationResult(True, len(rows))
