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

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant
from app.config import settings
from app.db.audit import AuditChainHead, AuditLog, genesis_hash, verify_chain
from app.db.session import tenant_session_cm
from app.models.case import Case
from app.models.case_note import CaseNote
from app.models.customer import Customer
from app.models.identity_verification import IdentityVerification
from app.models.report import Report
from app.models.sanctions_screening import SanctionsScreening
from app.models.tenant import Tenant
from app.models.transaction_alert import TransactionAlert
from app.schemas.case import CaseNoteCreate, CaseUpdate
from app.schemas.identity_verification import IdentityVerificationCreate
from app.schemas.sanctions_screening import SanctionsScreeningCreate
from app.schemas.transaction import TransactionCreate
from app.services import (
    api_key_service,
    case_service,
    identity_service,
    report_service,
    sanctions_service,
    transaction_service,
)
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

    # 19. Transaction monitoring: an unremarkable transaction should not
    # trigger any rule.
    with tenant_session_cm(tenant_a) as db_a12:
        _, quiet_alerts = transaction_service.record_transaction(
            db_a12, tenant_a, customer_id, TransactionCreate(amount=123_456.78, currency="NGN"),
        )
    check("ordinary transaction triggers no monitoring alerts", quiet_alerts == [])

    # 20. Large-amount rule fires alone on a non-round amount above threshold.
    with tenant_session_cm(tenant_a) as db_a13:
        _, large_alerts = transaction_service.record_transaction(
            db_a13, tenant_a, customer_id, TransactionCreate(amount=5_432_109.33, currency="NGN"),
        )
    check(
        "large-amount rule fires alone above threshold",
        [a.rule_code for a in large_alerts] == ["LARGE_AMOUNT"],
        f"got {[a.rule_code for a in large_alerts]}",
    )

    # 21. Large-amount + round-amount both fire on one transaction that
    # clears both thresholds (proves multi-alert-per-transaction).
    with tenant_session_cm(tenant_a) as db_a14:
        _, round_alerts = transaction_service.record_transaction(
            db_a14, tenant_a, customer_id, TransactionCreate(amount=5_000_000.00, currency="NGN"),
        )
        round_alert_ids = [a.id for a in round_alerts]
    check(
        "large + round amount rules both fire on one transaction",
        {a.rule_code for a in round_alerts} == {"LARGE_AMOUNT", "ROUND_AMOUNT"},
        f"got {[a.rule_code for a in round_alerts]}",
    )

    # 22. A round amount below the minimum floor must not fire (false-positive guard).
    with tenant_session_cm(tenant_a) as db_a15:
        _, small_round_alerts = transaction_service.record_transaction(
            db_a15, tenant_a, customer_id, TransactionCreate(amount=200_000.00, currency="NGN"),
        )
    check("round amount below the minimum floor does not fire", small_round_alerts == [])

    # 23. Velocity/structuring: three sub-threshold transactions whose
    # cumulative sum clears the velocity threshold -- only the third call's
    # alerts should include it (count-floor + amount-threshold guard).
    structuring_amount = 1_150_050.75
    with tenant_session_cm(tenant_a) as db_a16:
        _, v1_alerts = transaction_service.record_transaction(
            db_a16, tenant_a, customer_id, TransactionCreate(amount=structuring_amount, currency="NGN"),
        )
    with tenant_session_cm(tenant_a) as db_a17:
        _, v2_alerts = transaction_service.record_transaction(
            db_a17, tenant_a, customer_id, TransactionCreate(amount=structuring_amount, currency="NGN"),
        )
    with tenant_session_cm(tenant_a) as db_a18:
        _, v3_alerts = transaction_service.record_transaction(
            db_a18, tenant_a, customer_id, TransactionCreate(amount=structuring_amount, currency="NGN"),
        )
    check(
        "velocity/structuring rule does not fire before the count/amount floor is met",
        "VELOCITY_STRUCTURING" not in [a.rule_code for a in v1_alerts]
        and "VELOCITY_STRUCTURING" not in [a.rule_code for a in v2_alerts],
    )
    check(
        "velocity/structuring rule fires once the cumulative window clears the threshold",
        "VELOCITY_STRUCTURING" in [a.rule_code for a in v3_alerts],
        f"got {[a.rule_code for a in v3_alerts]}",
    )

    # 24. The transaction_alerts inserts were captured in audit_log.
    with Session(migrations_engine) as db:
        audit_rows_ta = db.execute(
            select(AuditLog).where(
                AuditLog.tenant_id == tenant_a,
                AuditLog.table_name == "transaction_alerts",
                AuditLog.record_id.in_(round_alert_ids),
            )
        ).scalars().all()
    check("transaction_alerts inserts were captured in audit_log", len(audit_rows_ta) == len(round_alert_ids))

    # 25. Cross-tenant isolation applies to transaction_alerts too.
    with tenant_session_cm(tenant_b) as db_b4:
        rows_b_ta = db_b4.execute(select(TransactionAlert)).scalars().all()
    check("tenant B sees zero of tenant A's transaction alerts", len(rows_b_ta) == 0)
    with tenant_session_cm(tenant_a) as db_a19:
        rows_a_ta = db_a19.execute(select(TransactionAlert)).scalars().all()
    check(
        "tenant A sees its own transaction alerts",
        len(rows_a_ta) == 4,  # LARGE_AMOUNT, {LARGE_AMOUNT,ROUND_AMOUNT}, VELOCITY_STRUCTURING
        f"saw {len(rows_a_ta)}",
    )

    # 26. Case management: the sanctions 'potential_match' from step 15
    # should have auto-opened a case (unconditional on score); the 'clear'
    # from step 14 should not have.
    with tenant_session_cm(tenant_a) as db_a20:
        match_cases = db_a20.execute(
            select(Case).where(Case.source_type == "sanctions_screening", Case.source_id == match_id)
        ).scalars().all()
        clear_cases = db_a20.execute(
            select(Case).where(Case.source_type == "sanctions_screening", Case.source_id == clear_rec.id)
        ).scalars().all()
    check(
        "sanctions potential_match auto-opens a case",
        len(match_cases) == 1 and match_cases[0].priority == "high" and match_cases[0].status == "open"
        and match_cases[0].customer_id == customer_id,
        f"got {[(c.priority, c.status) for c in match_cases]}",
    )
    check("sanctions clear does not open a case", len(clear_cases) == 0)

    # 27. A second customer, isolated from the trailing-window state the
    # transaction-monitoring section above already accumulated for
    # customer_id, so these alert-triggered case scenarios stay clean.
    with tenant_session_cm(tenant_a) as db_a21:
        customer2 = Customer(tenant_id=tenant_a, full_name="Chinedu Balogun", email="chinedu@example.com")
        db_a21.add(customer2)
    customer2_id = customer2.id

    # 28. A high-severity transaction alert auto-opens a case.
    with tenant_session_cm(tenant_a) as db_a22:
        _, high_alerts = transaction_service.record_transaction(
            db_a22, tenant_a, customer2_id, TransactionCreate(amount=6_123_456.78, currency="NGN"),
        )
        high_alert_id = high_alerts[0].id
    check(
        "high-severity alert fires alone",
        [a.rule_code for a in high_alerts] == ["LARGE_AMOUNT"],
        f"got {[a.rule_code for a in high_alerts]}",
    )
    with tenant_session_cm(tenant_a) as db_a23:
        high_cases = db_a23.execute(
            select(Case).where(Case.source_type == "transaction_alert", Case.source_id == high_alert_id)
        ).scalars().all()
    check(
        "high-severity transaction alert auto-opens a case",
        len(high_cases) == 1 and high_cases[0].priority == "high",
        f"got {[(c.priority, c.status) for c in high_cases]}",
    )
    high_case_id = high_cases[0].id

    # 29. A low-severity-only alert (ROUND_AMOUNT alone -- first transaction
    # for customer2, so velocity can't also fire) must not auto-open a case
    # (false-positive guard on the severity floor).
    with tenant_session_cm(tenant_a) as db_a24:
        _, low_alerts = transaction_service.record_transaction(
            db_a24, tenant_a, customer2_id, TransactionCreate(amount=2_000_000.00, currency="NGN"),
        )
        low_alert_ids = [a.id for a in low_alerts]
    check(
        "low-severity round-amount rule fires alone",
        [a.rule_code for a in low_alerts] == ["ROUND_AMOUNT"],
        f"got {[a.rule_code for a in low_alerts]}",
    )
    with tenant_session_cm(tenant_a) as db_a25:
        low_cases = db_a25.execute(
            select(Case).where(Case.source_type == "transaction_alert", Case.source_id.in_(low_alert_ids))
        ).scalars().all()
    check("low-severity-only alert does not auto-open a case", len(low_cases) == 0)

    # 30. Case status workflow: open -> in_review -> resolved, with a
    # required resolution and resolved_at getting stamped.
    with tenant_session_cm(tenant_a) as db_a26:
        case = case_service.get_case(db_a26, high_case_id)
        case = case_service.update_case_status(db_a26, case, CaseUpdate(status="in_review"))
    check("case transitions open -> in_review", case.status == "in_review" and case.resolved_at is None)

    resolve_rejected = False
    try:
        with tenant_session_cm(tenant_a) as db_a27:
            case = case_service.get_case(db_a27, high_case_id)
            case_service.update_case_status(db_a27, case, CaseUpdate(status="resolved"))
    except ValueError:
        resolve_rejected = True
    check("resolving without a resolution is rejected", resolve_rejected)

    with tenant_session_cm(tenant_a) as db_a28:
        case = case_service.get_case(db_a28, high_case_id)
        case = case_service.update_case_status(
            db_a28, case,
            CaseUpdate(status="resolved", resolution="confirmed", resolution_notes="Confirmed large cash-equivalent transfer."),
        )
    check(
        "case resolves with an outcome and resolved_at set",
        case.status == "resolved" and case.resolution == "confirmed" and case.resolved_at is not None,
    )

    # 31. A CaseNote can be added and listed.
    with tenant_session_cm(tenant_a) as db_a29:
        note = case_service.add_case_note(
            db_a29, tenant_a, high_case_id,
            CaseNoteCreate(author="jane.investigator", body="Escalated to compliance lead."),
        )
        note_id = note.id
    with tenant_session_cm(tenant_a) as db_a30:
        notes = case_service.list_case_notes(db_a30, high_case_id)
    check(
        "case note is persisted and listed",
        len(notes) == 1 and notes[0].id == note_id and notes[0].author == "jane.investigator",
    )

    # 32. cases/case_notes inserts (and updates) were captured in audit_log:
    # 1 INSERT (open) + 2 UPDATEs (in_review, resolved) for the case.
    with Session(migrations_engine) as db:
        audit_rows_case = db.execute(
            select(AuditLog).where(
                AuditLog.tenant_id == tenant_a, AuditLog.table_name == "cases", AuditLog.record_id == high_case_id,
            )
        ).scalars().all()
        audit_rows_note = db.execute(
            select(AuditLog).where(
                AuditLog.tenant_id == tenant_a, AuditLog.table_name == "case_notes", AuditLog.record_id == note_id,
            )
        ).scalars().all()
    check(
        "case insert + status transitions were captured in audit_log",
        len(audit_rows_case) == 3, f"got {len(audit_rows_case)}",
    )
    check("case_notes insert was captured in audit_log", len(audit_rows_note) == 1)

    # 33. Cross-tenant isolation applies to cases and case_notes too.
    with tenant_session_cm(tenant_b) as db_b5:
        rows_b_cases = db_b5.execute(select(Case)).scalars().all()
        rows_b_notes = db_b5.execute(select(CaseNote)).scalars().all()
    check("tenant B sees zero of tenant A's cases", len(rows_b_cases) == 0)
    check("tenant B sees zero of tenant A's case notes", len(rows_b_notes) == 0)
    with tenant_session_cm(tenant_a) as db_a31:
        rows_a_cases_c2 = db_a31.execute(select(Case).where(Case.customer_id == customer2_id)).scalars().all()
    check(
        "tenant A sees its own cases for the second customer",
        len(rows_a_cases_c2) == 1 and rows_a_cases_c2[0].id == high_case_id,
        f"saw {len(rows_a_cases_c2)}",
    )

    # 34. Regulatory reporting: attempting to generate a report for a case
    # that is not yet resolved+confirmed is rejected. match_cases[0] (the
    # sanctions-triggered case from step 26) is still status=="open" here.
    match_case_id = match_cases[0].id
    report_gate_rejected = False
    try:
        with tenant_session_cm(tenant_a) as db_a32:
            open_case = case_service.get_case(db_a32, match_case_id)
            report_service.generate_report(db_a32, tenant_a, open_case, "STR")
    except ValueError:
        report_gate_rejected = True
    check("report generation is rejected for a case not resolved+confirmed", report_gate_rejected)

    # 35. Resolve that case using the mock provider's reserved error-trigger
    # phrase as the resolution note, then generate a report -- this should
    # clear the gate but fail at the provider (mock error path).
    with tenant_session_cm(tenant_a) as db_a33:
        case_to_resolve = case_service.get_case(db_a33, match_case_id)
        case_service.update_case_status(
            db_a33, case_to_resolve,
            CaseUpdate(status="resolved", resolution="confirmed", resolution_notes="Trigger Regulator Provider Error"),
        )
    with tenant_session_cm(tenant_a) as db_a34:
        resolved_case = case_service.get_case(db_a34, match_case_id)
        error_report = report_service.generate_report(db_a34, tenant_a, resolved_case, "STR")
    check(
        "regulator provider error path",
        error_report.status == "error" and error_report.provider_reference is None and bool(error_report.error_detail),
    )

    # 36. Generate a report for high_case_id (resolved/confirmed earlier
    # with ordinary resolution notes) -- the normal submitted path.
    with tenant_session_cm(tenant_a) as db_a35:
        confirmed_case = case_service.get_case(db_a35, high_case_id)
        submitted_report = report_service.generate_report(db_a35, tenant_a, confirmed_case, "STR")
        submitted_report_id = submitted_report.id
    check(
        "regulator submission succeeds for a resolved+confirmed case",
        submitted_report.status == "submitted" and submitted_report.provider_reference is not None
        and submitted_report.payload["case_id"] == str(high_case_id),
        f"got status={submitted_report.status}",
    )

    # 37. The submitted report insert was captured in audit_log.
    with Session(migrations_engine) as db:
        audit_rows_report = db.execute(
            select(AuditLog).where(
                AuditLog.tenant_id == tenant_a, AuditLog.table_name == "reports", AuditLog.record_id == submitted_report_id,
            )
        ).scalars().all()
    check("reports insert was captured in audit_log", len(audit_rows_report) == 1)

    # 38. Cross-tenant isolation applies to reports too.
    with tenant_session_cm(tenant_b) as db_b6:
        rows_b_reports = db_b6.execute(select(Report)).scalars().all()
    check("tenant B sees zero of tenant A's reports", len(rows_b_reports) == 0)
    with tenant_session_cm(tenant_a) as db_a36:
        rows_a_reports = db_a36.execute(select(Report).where(Report.case_id == high_case_id)).scalars().all()
    check(
        "tenant A sees its own report for the confirmed case",
        len(rows_a_reports) == 1 and rows_a_reports[0].id == submitted_report_id,
        f"saw {len(rows_a_reports)}",
    )

    # 39. API key auth: create a key for tenant A (root-level table, no RLS
    # -- same provisioning shape as provision_tenant() above).
    with Session(migrations_engine) as db:
        api_key_record, raw_key = api_key_service.create_api_key(db, tenant_a, "smoke-test-key")
        db.commit()
        api_key_id = api_key_record.id
    check(
        "created API key has correct last4 and stores only a hash, not the raw key",
        raw_key.endswith(api_key_record.key_last4)
        and api_key_record.key_hash != raw_key and len(api_key_record.key_hash) == 64,
    )

    # 40. authenticate() resolves the real key to the right tenant; a
    # garbage string resolves to nothing.
    with Session(migrations_engine) as db:
        authed = api_key_service.authenticate(db, raw_key)
        bogus = api_key_service.authenticate(db, "rtk_not-a-real-key")
    check("authenticate resolves a valid key to its tenant", authed is not None and authed.tenant_id == tenant_a)
    check("authenticate rejects a bogus key", bogus is None)

    # 41. get_current_tenant is the actual FastAPI dependency -- calling it
    # directly with an explicit `credentials` kwarg is exactly what FastAPI
    # does under the hood (via the HTTPBearer security scheme), just
    # without the HTTP round trip. Proves actor_id/actor_type now flow from
    # the key instead of always None/"user".
    def _creds(raw: str) -> HTTPAuthorizationCredentials:
        return HTTPAuthorizationCredentials(scheme="Bearer", credentials=raw)

    ctx = get_current_tenant(credentials=_creds(raw_key))
    check(
        "get_current_tenant resolves tenant + actor from a valid key",
        ctx.tenant_id == tenant_a and ctx.actor_id == api_key_id and ctx.actor_type == "api_key",
    )

    # 42. get_current_tenant rejects a missing credential and an unknown key.
    # (HTTPBearer itself, with auto_error=False, normalizes a missing or
    # non-Bearer Authorization header to credentials=None before
    # get_current_tenant ever runs -- that's the case being simulated here.)
    def _rejects_with_401(**kwargs) -> bool:
        try:
            get_current_tenant(**kwargs)
        except HTTPException as exc:
            return exc.status_code == 401
        return False

    check(
        "get_current_tenant rejects a missing/malformed credential",
        _rejects_with_401(credentials=None),
    )
    check(
        "get_current_tenant rejects an unknown key",
        _rejects_with_401(credentials=_creds("rtk_totally-made-up")),
    )

    # 43. Revoking a key blocks both authenticate() and get_current_tenant.
    with Session(migrations_engine) as db:
        api_key_service.revoke_api_key(db, api_key_id)
        db.commit()
    with Session(migrations_engine) as db:
        revoked_lookup = api_key_service.authenticate(db, raw_key)
    check("authenticate rejects a revoked key", revoked_lookup is None)
    check(
        "get_current_tenant rejects a revoked key",
        _rejects_with_401(credentials=_creds(raw_key)),
    )

    # 44. Cross-tenant key isolation: a tenant B key must not authenticate
    # as tenant A.
    with Session(migrations_engine) as db:
        _, tenant_b_raw_key = api_key_service.create_api_key(db, tenant_b, "tenant-b-key")
        db.commit()
    with Session(migrations_engine) as db:
        tenant_b_authed = api_key_service.authenticate(db, tenant_b_raw_key)
    check(
        "a tenant B key authenticates as tenant B, not tenant A",
        tenant_b_authed is not None and tenant_b_authed.tenant_id == tenant_b
        and tenant_b_authed.tenant_id != tenant_a,
    )

    print()
    if failures:
        print(f"{len(failures)} check(s) FAILED: {failures}")
        return 1
    print(f"All checks passed. Chain length before tamper test: {chain_length_before}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
