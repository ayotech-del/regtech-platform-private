from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401 -- registers every model on Base.metadata
# before any request can flush a row with a foreign key pointing at another
# table (e.g. every tenant-scoped table's tenant_id -> tenants.id). Must
# happen before route/service imports below execute a flush, not after.
from app.api.routes.cases import router as cases_router
from app.api.routes.customers import router as customers_router
from app.api.routes.identity import router as identity_router
from app.api.routes.reports import router as reports_router
from app.api.routes.sanctions import router as sanctions_router
from app.api.routes.transactions import alerts_router as transaction_alerts_router
from app.api.routes.transactions import router as transactions_router
from app.config import settings

app = FastAPI(title="RegTech Platform")

# allow_credentials=False -- auth is a Bearer header, not cookies, so there's
# no wildcard-origin-plus-credentials restriction to work around here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(customers_router)
app.include_router(identity_router)
app.include_router(sanctions_router)
app.include_router(transactions_router)
app.include_router(transaction_alerts_router)
app.include_router(cases_router)
app.include_router(reports_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
