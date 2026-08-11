# RegTech Platform — Foundational Layer

Multi-tenancy (Postgres Row-Level Security) and tamper-evident audit logging
(hash-chained, append-only) for the RegTech/compliance platform. This is the
foundation later modules (identity/KYC, transaction monitoring, sanctions
screening, case management, regulatory reporting) build on top of — see
`app/models/customer.py` and `app/models/transaction.py` for the pattern any
new tenant-scoped, audited table should follow.

## Design

- **Tenancy**: shared database/schema, `tenant_id` column on every
  tenant-scoped table, enforced by Postgres RLS policies
  (`app/db/rls.py`). The app connects only as `app_user`
  (`NOSUPERUSER NOBYPASSRLS`) — never as the migrations/owner role — so it's
  structurally incapable of bypassing RLS. `app/db/session.py` pins each
  request's transaction to a tenant via `set_config('app.current_tenant', ...)`;
  if that's ever skipped, RLS fails closed (zero rows), not open.
- **Audit**: every mutation on a model that mixes in `Auditable`
  (`app/db/base.py`) is captured automatically via a SQLAlchemy
  `before_flush` listener (`app/db/audit.py`) into a per-tenant, hash-chained
  `audit_log` table. The table is append-only at the database level
  (`REVOKE UPDATE/DELETE` + raising triggers) *and* independently verifiable
  via `verify_chain()`, which re-derives every hash from genesis — so
  tampering is provable even if DB grants were somehow bypassed.

Full design rationale: see `../../../.claude/plans/peppy-moseying-sifakis.md`
(or ask — it covers the threat model and the tradeoffs behind each choice).

## Prerequisites

- Docker (for Postgres)
- Python 3.11+

## Setup

```bash
cp .env.example .env
docker compose up -d
pip install -e .
alembic upgrade head
```

## Try it

```bash
# Create a tenant (runs as the migrations/owner role)
python -m app.cli create-tenant "Example Bank" example-bank

# Verify a tenant's audit chain (prints the tenant id from create-tenant above)
python -m app.cli verify-chain <tenant-id>

# Run the API
uvicorn app.main:app --reload
# then, e.g.: curl -H "X-Tenant-Slug: example-bank" http://localhost:8000/customers
```

## Verification

```bash
python scripts/smoke_test.py
```

Proves, end-to-end, against a real database:
1. Two tenants provisioned.
2. Tenant A writes a customer; Tenant B's query sees **zero** rows (isolation).
3. Tenant A's own query **does** see the row (RLS isn't over-blocking).
4. A direct `UPDATE` on `audit_log` as `app_user` is rejected.
5. The audit chain verifies clean.
6. A simulated DBA-level edit (via the superuser/migrations connection,
   bypassing `app_user`'s grants entirely) to a historical audit row is
   **detected** by `verify_chain` at the exact `seq` it occurred.

All steps must print `PASS`; the script exits non-zero otherwise, so it
doubles as a regression test for later changes.

## Scope

This pass is intentionally just the two foundations plus enough scaffolding
to prove them (two example tables: `customers`, `transactions`). Not
included yet, by design: identity/KYC, transaction monitoring, sanctions
screening, case management, regulatory reporting, real auth (see the stub
and comment in `app/api/deps.py:get_current_tenant`), and read-path
auditing (only mutations are audited in v1).
