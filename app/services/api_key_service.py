from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.api_key import ApiKey


def generate_api_key() -> str:
    # secrets, not the random/hashlib-seeded determinism used by the mock
    # providers elsewhere -- this must be genuinely unpredictable.
    return f"rtk_{secrets.token_urlsafe(32)}"


def hash_key(raw_key: str) -> str:
    # Bare SHA-256, not HMAC-peppered like identifier_hash -- see
    # app/models/api_key.py for why: the raw key already has 256 bits of
    # entropy, so a pepper adds no meaningful brute-force resistance here.
    return hashlib.sha256(raw_key.encode()).hexdigest()


def create_api_key(db: Session, tenant_id: uuid.UUID, label: str) -> tuple[ApiKey, str]:
    raw_key = generate_api_key()
    record = ApiKey(tenant_id=tenant_id, label=label, key_hash=hash_key(raw_key), key_last4=raw_key[-4:])
    db.add(record)
    db.flush()
    db.refresh(record)
    return record, raw_key


def authenticate(db: Session, raw_key: str) -> ApiKey | None:
    return db.execute(
        select(ApiKey).where(ApiKey.key_hash == hash_key(raw_key), ApiKey.revoked_at.is_(None))
    ).scalar_one_or_none()


def revoke_api_key(db: Session, key_id: uuid.UUID) -> None:
    key = db.get(ApiKey, key_id)
    if key is not None:
        key.revoked_at = datetime.now(timezone.utc)
        db.flush()
