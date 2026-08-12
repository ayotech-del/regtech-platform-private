from fastapi import FastAPI

from app.api.routes.cases import router as cases_router
from app.api.routes.customers import router as customers_router
from app.api.routes.identity import router as identity_router
from app.api.routes.reports import router as reports_router
from app.api.routes.sanctions import router as sanctions_router
from app.api.routes.transactions import alerts_router as transaction_alerts_router
from app.api.routes.transactions import router as transactions_router

app = FastAPI(title="RegTech Platform")

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
