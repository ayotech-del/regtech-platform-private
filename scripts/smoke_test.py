"""End-to-end proof that the foundational layer works: tenant isolation via
RLS, and tamper-evident audit logging via the hash chain. Exercises the real
app code paths (app.db.session, app.cli's provisioning logic), not raw
psycopg. Exits non-zero on any failure so this doubles as a regression test.

Run after `docker compose up -d` and `alembic upgrade head`:
    python scripts/smoke_test.py
"""
from __future__ import annotations

import sys
import uuid

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.db.audit import AuditChainHead, AuditLog, genesis_hash, verify_chain
from app.db.session import tenant_session_cm
from app.models.customer import Customer
from app.models.tenant import Tenant

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

    print()
    if failures:
        print(f"{len(failures)} check(s) FAILED: {failures}")
        return 1
    print(f"All checks passed. Chain length before tamper test: {chain_length_before}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
