import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.schemas.customer import CustomerCreate


def create_customer(db: Session, tenant_id: uuid.UUID, payload: CustomerCreate) -> Customer:
    customer = Customer(tenant_id=tenant_id, full_name=payload.full_name, email=payload.email)
    db.add(customer)
    db.flush()
    db.refresh(customer)
    return customer


def list_customers(db: Session) -> list[Customer]:
    # No explicit tenant_id filter here on purpose: RLS enforces it. This is
    # the whole point of the mixin -- the query is trustworthy even if a
    # future call site forgets to filter, because the database won't return
    # another tenant's rows regardless of what this function does.
    return list(db.execute(select(Customer)).scalars().all())
