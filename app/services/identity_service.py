from __future__ import annotations

import hashlib
import hmac
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.identity_verification import IdentityVerification
from app.schemas.identity_verification import IdentityVerificationCreate
from app.services.identity.factory import get_identity_provider


def hash_identifier(value: str) -> str:
    """HMAC-SHA256 keyed by identity_hash_pepper, not a bare SHA-256 -- an
    11-digit identifier has low enough entropy that a bare hash would be
    brute-forceable from a DB/audit_log dump. Deterministic given the same
    pepper, so it still supports its purpose: detecting a repeat check of
    the same identifier without ever storing or recovering it.
    """
    return hmac.new(settings.identity_hash_pepper.encode(), value.encode(), hashlib.sha256).hexdigest()


def create_identity_verification(
    db: Session, tenant_id: uuid.UUID, customer_id: uuid.UUID, payload: IdentityVerificationCreate
) -> IdentityVerification:
    provider = get_identity_provider()
    identifier = payload.identifier  # raw value: local only, never persisted

    result = (
        provider.verify_bvn(identifier)
        if payload.identifier_type == "BVN"
        else provider.verify_nin(identifier)
    )

    record = IdentityVerification(
        tenant_id=tenant_id,
        customer_id=customer_id,
        identifier_type=payload.identifier_type,
        identifier_last4=identifier[-4:],
        identifier_hash=hash_identifier(identifier),
        provider_name=settings.identity_provider,
        status=result.status,
        matched=result.matched,
        provider_reference=result.provider_reference,
        profile_data=result.profile or None,
        error_detail=result.error_detail,
    )
    db.add(record)
    db.flush()
    db.refresh(record)
    return record
    # `identifier` / `payload.identifier` fall out of scope here.


def list_identity_verifications(db: Session, customer_id: uuid.UUID) -> list[IdentityVerification]:
    # No tenant_id filter -- same rationale as customer_service: RLS makes
    # this correct even if this function forgot.
    return list(
        db.execute(
            select(IdentityVerification)
            .where(IdentityVerification.customer_id == customer_id)
            .order_by(IdentityVerification.checked_at.desc())
        ).scalars().all()
    )
