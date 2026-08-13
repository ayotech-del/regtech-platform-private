import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.customer import CustomerCreate, CustomerRead
from app.services import customer_service

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("", response_model=CustomerRead, status_code=201)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)) -> CustomerRead:
    # tenant_id is injected server-side from get_db's tenant context, not
    # accepted from the request body -- a client can never write into
    # another tenant's rows even if it tries to pass one.
    customer = customer_service.create_customer(db, db.info["tenant_id"], payload)
    return CustomerRead.model_validate(customer)


@router.get("", response_model=list[CustomerRead])
def list_customers(db: Session = Depends(get_db)) -> list[CustomerRead]:
    return [CustomerRead.model_validate(c) for c in customer_service.list_customers(db)]


@router.get("/{customer_id}", response_model=CustomerRead)
def get_customer(customer_id: uuid.UUID, db: Session = Depends(get_db)) -> CustomerRead:
    customer = customer_service.get_customer(db, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    return CustomerRead.model_validate(customer)
