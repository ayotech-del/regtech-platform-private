"""End-to-end proof that the foundational layer works: tenant isolation via
RLS, and tamper-evident audit logging via the hash chain. Exercises the real
app code paths (app.db.session, app.cli's provisioning logic), not raw
psycopg. Exits non-zero on any failure so this doubles as a regression test.

Run after `docker compose up -d` and `alembic upgrade head`:
    python scripts/smoke_test.py
"""
from __future__ import annotations

import json
import sys
import uuid

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.db.audit import AuditChainHead, AuditLog, genesis_hash, verify_chain
from app.db.session import tenant_session_cm
from app.models.customer import Customer
from app.models.identity_verification import IdentityVerification
from app.models.sanctions_screening import SanctionsScreening
from app.models.tenant import Tenant
from app.schemas.identity_verification import IdentityVerificationCreate
from app.schemas.sanctions_screening import SanctionsScreeningCreate
from app.services import identity_service, sanctions_service
from app.services.identity.providers.mock import MockIdentityProvider

migrations_engine = create_engine(settings.database_url_migrations)

failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f" -- {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(label)


def provision_tenant(name: str, slug: str) -> uuid.UUID:
    with Session(migrations_engine) as db:
        tenant = Tenant(id=uuid.uuid4(), name=name, slug=slug)
        db.add(tenant)
        db.flush()
        db.add(AuditChainHead(tenant_id=tenant.id, last_seq=0, last_hash=genesis_hash(tenant.id)))
        db.commit()
        return tenant.id


def main() -> int:
    suffix = uuid.uuid4().hex[:8]

    # 1. Provision two tenants.
    tenant_a = provision_tenant(f"Institution A {suffix}", f"inst-a-{suffix}")
    tenant_b = provision_tenant(f"Institution B {suffix}", f"inst-b-{suffix}")
    check("provisioned two tenants", True)

    # 2. As Tenant A: insert a customer through the normal tenant-scoped session.
    with tenant_session_cm(tenant_a) as db_a:
        customer = Customer(tenant_id=tenant_a, full_name="Ada Okafor", email="ada@example.com")
        db_a.add(customer)
    customer_id = customer.id

    # 3. As Tenant B: must see zero rows (negative isolation proof).
    with tenant_session_cm(tenant_b) as db_b:
        rows_b = db_b.execute(select(Customer)).scalars().all()
    check("tenant B sees zero of tenant A's customers", len(rows_b) == 0, f"saw {len(rows_b)} rows")

    # 4. As Tenant A: the row must be visible (RLS isn't over-blocking).
    with tenant_session_cm(tenant_a) as db_a2:
        rows_a = db_a2.execute(select(Customer)).scalars().all()
    check("tenant A sees its own customer", len(rows_a) == 1 and rows_a[0].id == customer_id)

    # 5. As Tenant A, via the normal app_user connection: direct UPDATE on
    # audit_log must be rejected (REVOKE + trigger).
    blocked = False
    try:
        with tenant_session_cm(tenant_a) as db_a3:
            db_a3.execute(text("UPDATE audit_log SET new_values = '{}'::jsonb WHERE tenant_id = :t"), {"t": str(tenant_a)})
    except Exception:
        blocked = True
    check("direct UPDATE on audit_log as app_user is rejected", blocked)

    # 6. Chain must verify clean so far.
    with Session(migrations_engine) as db:
        result = verify_chain(db, tenant_a)
    check("audit chain verifies before tampering", result.valid, result.reason)
    chain_length_before = result.length

    # 7. Tamper test: the append-only trigger fires for every role, including
    # the migrations/superuser role -- REVOKE and RLS can be bypassed by a
    # superuser, but a BEFORE UPDATE trigger cannot. So to simulate a
    # determined DBA-level edit, explicitly disable the trigger first (which
    # a superuser/table-owner *can* do), tamper, then re-enable it. This is
    # exactly the scenario hash-chaining exists for: proving tampering even
    # when DB-level protections were deliberately defeated.
    with Session(migrations_engine) as db:
        db.execute(text("ALTER TABLE audit_log DISABLE TRIGGER audit_log_no_update"))
        row = db.execute(
            select(AuditLog).where(AuditLog.tenant_id == tenant_a).order_by(AuditLog.seq)
        ).scalars().first()
        row.new_values = {"full_name": "TAMPERED", "email": "tampered@example.com"}
        db.flush()
        tampered_seq = row.seq
        db.execute(text("ALTER TABLE audit_log ENABLE TRIGGER audit_log_no_update"))
        db.commit()

    with Session(migrations_engine) as db:
        result_after = verify_chain(db, tenant_a)
    check(
        "tampering with audit_log content is detected",
        not result_after.valid and result_after.failed_at_seq == tampered_seq,
        f"got valid={result_after.valid}, failed_at_seq={result_after.failed_at_seq}",
    )

    # 8. Identity verification: "verified" path, as Tenant A, against the
    # customer from step 2.
    sample_bvn = "22233344455"
    with tenant_session_cm(tenant_a) as db_a4:
        verified_record = identity_service.create_identity_verification(
            db_a4, tenant_a, customer_id,
            IdentityVerificationCreate(identifier_type="BVN", identifier=sample_bvn),
        )
        verified_id, verified_hash = verified_record.id, verified_record.identifier_hash
    check(
        "mock provider 'verified' path persists a matched record",
        verified_record.status == "verified" and verified_record.matched is True
        and verified_record.identifier_last4 == sample_bvn[-4:]
        and set(verified_record.profile_data) >= {"full_name", "date_of_birth", "phone_number"},
    )

    # 9. Mock provider determinism: same identifier always yields the same
    # fake profile.
    provider = MockIdentityProvider()
    r1, r2 = provider.verify_bvn(sample_bvn), provider.verify_bvn(sample_bvn)
    check(
        "mock provider is deterministic for the same identifier",
        r1.profile == r2.profile and r1.provider_reference == r2.provider_reference,
    )

    # 10. "no_match" path (reserved test value: 11 zeros).
    with tenant_session_cm(tenant_a) as db_a5:
        no_match = identity_service.create_identity_verification(
            db_a5, tenant_a, customer_id,
            IdentityVerificationCreate(identifier_type="BVN", identifier="0" * 11),
        )
    check("mock provider 'no_match' path", no_match.status == "no_match" and no_match.matched is False)

    # 11. "error" path (reserved test value: 11 nines).
    with tenant_session_cm(tenant_a) as db_a6:
        error_rec = identity_service.create_identity_verification(
            db_a6, tenant_a, customer_id,
            IdentityVerificationCreate(identifier_type="BVN", identifier="9" * 11),
        )
    check(
        "mock provider 'error' path",
        error_rec.status == "error" and error_rec.matched is False and bool(error_rec.error_detail),
    )

    # 12. The property that matters most: the raw BVN must appear nowhere
    # persisted -- not in profile_data, and not in the audit_log snapshot of
    # this row (the whole reason identifier_hash/last4 exist instead of the
    # raw value). The HMAC hash, on the other hand, should be present.
    check(
        "raw identifier absent from persisted profile_data",
        sample_bvn not in json.dumps(verified_record.profile_data),
    )
    with Session(migrations_engine) as db:
        audit_rows = db.execute(
            select(AuditLog).where(
                AuditLog.tenant_id == tenant_a,
                AuditLog.table_name == "identity_verifications",
                AuditLog.record_id == verified_id,
            )
        ).scalars().all()
    check("identity_verifications insert was captured in audit_log", len(audit_rows) == 1)
    dumped = json.dumps([r.new_values for r in audit_rows])
    check("raw identifier absent from audit_log for this record", sample_bvn not in dumped)
    check("audit_log captured the hash instead", verified_hash in dumped)

    # 13. Cross-tenant isolation applies to identity_verifications too.
    with tenant_session_cm(tenant_b) as db_b2:
        rows_b_iv = db_b2.execute(select(IdentityVerification)).scalars().all()
    check("tenant B sees zero of tenant A's identity verifications", len(rows_b_iv) == 0)
    with tenant_session_cm(tenant_a) as db_a7:
        rows_a_iv = db_a7.execute(select(IdentityVerification)).scalars().all()
    check("tenant A sees its own identity verifications", len(rows_a_iv) == 3)

    # 14. Sanctions screening: "clear" path against a name unrelated to the
    # mock's embedded watchlist.
    with tenant_session_cm(tenant_a) as db_a8:
        clear_rec = sanctions_service.create_sanctions_screening(
            db_a8, tenant_a, customer_id, "Ada Okafor",
            SanctionsScreeningCreate(name_override="Zephyrine Quokkafield Bramblewood"),
        )
    check(
        "sanctions screening 'clear' path",
        clear_rec.status == "clear" and clear_rec.hits == [] and clear_rec.highest_score is not None
        and clear_rec.highest_score < settings.sanctions_match_threshold,
    )

    # 15. Sanctions screening: "potential_match" path against a name close
    # to an embedded watchlist entry.
    with tenant_session_cm(tenant_a) as db_a9:
        match_rec = sanctions_service.create_sanctions_screening(
            db_a9, tenant_a, customer_id, "Ada Okafor",
            SanctionsScreeningCreate(name_override="Boris Yevgenyevich Volkoff"),
        )
        match_id = match_rec.id
    check(
        "sanctions screening 'potential_match' path",
        match_rec.status == "potential_match"
        and match_rec.highest_score is not None
        and match_rec.highest_score >= settings.sanctions_match_threshold
        and any(h["matched_name"] == "Boris Yevgenyevich Volkov" and h["list_name"] == "OFAC-SDN" for h in match_rec.hits),
    )

    # 16. "error" path (reserved sentinel input).
    with tenant_session_cm(tenant_a) as db_a10:
        error_scr = sanctions_service.create_sanctions_screening(
            db_a10, tenant_a, customer_id, "Ada Okafor",
            SanctionsScreeningCreate(name_override="Trigger Sanctions Provider Error"),
        )
    check(
        "sanctions screening 'error' path",
        error_scr.status == "error" and error_scr.hits == [] and error_scr.highest_score is None
        and bool(error_scr.error_detail),
    )

    # 17. The screening record is captured in audit_log.
    with Session(migrations_engine) as db:
        audit_rows_ss = db.execute(
            select(AuditLog).where(
                AuditLog.tenant_id == tenant_a,
                AuditLog.table_name == "sanctions_screenings",
                AuditLog.record_id == match_id,
            )
        ).scalars().all()
    check("sanctions_screenings insert was captured in audit_log", len(audit_rows_ss) == 1)

    # 18. Cross-tenant isolation applies to sanctions_screenings too.
    with tenant_session_cm(tenant_b) as db_b3:
        rows_b_ss = db_b3.execute(select(SanctionsScreening)).scalars().all()
    check("tenant B sees zero of tenant A's sanctions screenings", len(rows_b_ss) == 0)
    with tenant_session_cm(tenant_a) as db_a11:
        rows_a_ss = db_a11.execute(select(SanctionsScreening)).scalars().all()
    check("tenant A sees its own sanctions screenings", len(rows_a_ss) == 3)

    print()
    if failures:
        print(f"{len(failures)} check(s) FAILED: {failures}")
        return 1
    print(f"All checks passed. Chain length before tamper test: {chain_length_before}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
